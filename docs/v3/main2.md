# PDF Form Field Identification - Multi-Level Architecture Implementation

## Overview

Refactor the `FIELD_IDENTIFICATION` module of the PDF form autofill system.
Replace the current center-distance-based label matching in ProximityFieldEnricher with a multi-stage fallback strategy (StructuralResolver -> LLMFieldEnricher) + async First Action pattern.

## Background & Constraints

### Current Problems
- AcroForm field_ids are meaningless sequential names like "Text1", "Text2"
- ProximityFieldEnricher (center-distance-based) uses a fixed `_MAX_LABEL_DISTANCE=150pt` threshold, making accuracy dependent on form layout
- `_select_relevant_fields()` partitions fields into relevant/rest by matching label_candidates against data source keys — when labels are wrong, fields fall to compact one-liner format and LLM cannot identify them
- Non-directional Euclidean proximity search misidentifies text blocks below a field as labels
- **Output token bottleneck**: FillPlanner LLM call produces ~9,500 output tokens for 189 fields (input is only ~3,000 tokens). Output token generation is the dominant latency factor. Null/unfilled fields in the output act as Chain-of-Thought — removing them naively drops accuracy

### Goals
- First response to user within 3-5 seconds
- Maintain or improve field label identification accuracy
- Keep generality (support forms without table structure)

## As-Is / To-Be Matrix

| Area | As-Is (Current) | To-Be (Target) |
|---|---|---|
| **Output Tokens (bottleneck)** | ~9,500 tokens for 189 fields in single LLM call (~70s) | StructuralResolver eliminates 80% of fields from LLM; remaining use `field_id:label` one-line format per page (~50 tokens/page, ~5-10s parallel) |
| **Label Detection** | `ProximityFieldEnricher` — center-distance, fixed `_MAX_LABEL_DISTANCE=150pt` | `DirectionalFieldEnricher` — directional (left/above/right), no fixed radius |
| **Structural Analysis** | None — all fields processed by proximity only | `StructuralResolver` (`structural_resolver.py`) — table structure + field_id semantics, Python-only (0.1s) |
| **LLM Label Identification** | `LLMFieldEnricher` — all fields at once or page-parallel, compact JSON | `LLMFieldEnricher` — only StructuralResolver unresolved fields (reduced count), with nearby hints |
| **Label -> Field Classification** | `_select_relevant_fields()` — label_candidates vs ds_keys match -> mismatch demoted to compact one-liner | StructuralResolver resolved fields get semantic `label` set -> easier ds_keys match -> higher relevant rate |
| **First Response Speed** | ~111s (full pipeline) -> ~40s after Fix #2,#3 | 3-5s (StructuralResolver + immediate question generation) |
| **First Action Pattern** | None — no response until all steps complete | Quick: StructuralResolver -> immediate response / Precise: StructuralResolver -> immediate questions + LLM enrichment in background |
| **Diff Correction** | `CorrectionTracker` — records manual user corrections only | Extended: auto diff-correction after LLM enrichment completes |
| **PDF Library** | PyMuPDF (fitz) | PyMuPDF (fitz) — no change |
| **LLM Client** | `LiteLLMClient` + Instructor | `LiteLLMClient` + Instructor — no change |
| **FieldEnricher Protocol** | `FieldEnricher(Protocol)` — `ProximityFieldEnricher`, `LLMFieldEnricher` | `FieldEnricher(Protocol)` — `DirectionalFieldEnricher`, `LLMFieldEnricher`, `StructuralResolverEnricher` |
| **FormContextBuilder** | `enricher: FieldEnricher` injected, no branching | No change — enricher swap only |
| **Text Block Extraction** | `DocumentService.extract_text_blocks_for_page()` — per-page cached | No change |
| **Prompts** | `AUTOFILL_SYSTEM_PROMPT`, `DETAILED_MODE_SYSTEM_PROMPT`, `FIELD_IDENTIFICATION_SYSTEM_PROMPT` (compact JSON) | No change (LLMFieldEnricher prompt output format changes to `field_id:label` one-line format) |
| **Tests** | `test_label_enrichment.py`, `test_protocol_compliance.py` | Add: `test_directional_enrichment.py`, `test_structural_resolver.py` |

## Architecture

### Overall Flow

```
PDF Arrives
  |
  +-> Python Preprocessing (0.1s)
  |     +- DocumentService.get_acroform_fields() — AcroForm field extraction
  |     +- DocumentService.extract_text_blocks_for_page() — text block extraction
  |     +- DirectionalFieldEnricher.enrich() — nearby_labels generation
  |
  +-> StructuralResolver (Python, 0.1s)
  |     +- field_id semantics check
  |     +- find_tables() -> row x column header mapping
  |     +- Result: resolved / unresolved field classification
  |
  +-> [async] Question Generation (3s) <- triggered by StructuralResolver result
  |
  +-> [async] LLMFieldEnricher: Vision + Per-Page LLM (10-25s) <- unresolved only
        +- LLM enrichment complete or user answer arrives -> high-accuracy mapping
```

### First Action Pattern (2 Modes)

```python
# Quick Mode: StructuralResolver + immediate questions, skip FIELD_ID
# Precise Mode: StructuralResolver + immediate questions + LLMFieldEnricher in background

# If user answer arrives before LLM enrichment completes:
#   -> provisional mapping with nearby_labels -> diff correction after LLM enrichment
```

## Implementation Spec

### Module 1: `document_service.py` — Python Preprocessing

Extract fields and text from PDF using PyMuPDF (fitz).
**Use existing `DocumentService` class as-is.**

#### Existing: `get_acroform_fields(document_id) -> AcroFormFieldsResponse`

```python
# apps/api/app/services/document_service.py (existing)
# Returns BBox(x, y, width, height, page) for each field
# Extracts AcroForm fields via PyMuPDF page.widgets()
# PDF coords -> screen coords already transformed
```

#### Existing: `extract_text_blocks_for_page(document_id, page) -> list[dict]`

```python
# apps/api/app/services/document_service.py (existing)
# Per-page text block extraction (cached)
# Each block: {"id", "text", "page", "bbox": [x, y, width, height], "font_name", "font_size"}
# Uses PyMuPDF page.get_text("dict") -> spans
```

#### New: `generate_nearby_labels` -> `DirectionalFieldEnricher`

```python
# apps/api/app/services/form_context/enricher.py (new FieldEnricher implementation)
@dataclass
class NearbyLabel:
    text: str
    direction: str  # "left" | "above" | "right"
    distance: float  # pt
```

For each field:
1. Only consider text blocks on the same page (`extract_text_blocks_for_page`)
2. Search by direction:
   - **Left**: text right edge <= field left edge, Y-center diff < 15pt, distance < 50pt
   - **Above**: text bottom edge <= field top edge, X-center diff < 80pt, distance < 50pt
   - **Right**: text left edge >= field right edge, Y-center diff < 15pt, distance < 50pt
3. Sort by distance, return top 3-5 candidates
4. Exclude single-character text blocks

**Note**: Replaces the center-distance approach in `ProximityFieldEnricher`. Uses directional matching instead of fixed distance threshold (`_MAX_LABEL_DISTANCE=150`).

### Module 2: `structural_resolver.py` — StructuralResolver

Resolve field semantics using Python only — no LLM calls.

**File**: `apps/api/app/services/form_context/structural_resolver.py` (new)

#### Function: `resolve_field_ids(fields: tuple[FormFieldSpec, ...]) -> dict[str, str]`

Check if field_id has semantic meaning:
- Split by `_` or camelCase, check if 2+ English words are present
- Example: `employee_name`, `dateOfBirth`, `address_line1` -> semantic
- Example: `Text1`, `Field_3`, `CheckBox2` -> non-semantic

#### Function: `resolve_by_table_structure(document_id, fields, document_service) -> StructuralResult`

```python
@dataclass
class StructuralResult:
    resolved: dict[str, str]      # field_id -> semantic_label
    unresolved: list[str]         # field_ids that could not be resolved
    confidence: dict[str, float]  # field_id -> confidence score
```

Implementation steps:

1. **Table detection**: Detect tables via PyMuPDF `page.find_tables()`
2. **Field -> cell mapping**: Determine which cell each field's bbox center falls in
3. **Header extraction**: Take first 1-3 rows of `table.extract()` as headers
4. **Row section identification**: Get section name from row header (leftmost column text)
5. **Column header identification**: Use header row cell text as column meaning
6. **Structured label generation**: `{row_section} > {column_header}` format

Field -> cell check:
```python
def field_in_cell(field: FormFieldSpec, cell_bbox: tuple) -> bool:
    fx = field.x + field.width / 2
    fy = field.y + field.height / 2
    return cell_bbox[0] <= fx <= cell_bbox[2] and cell_bbox[1] <= fy <= cell_bbox[3]
```

Confidence criteria:
- Row header + column header both present -> 0.9
- Column header only -> 0.7
- Belongs to cell but no header extracted -> 0.5
- Not in any table -> unresolved

#### Function: `resolve(document_id, fields, document_service) -> StructuralResolverResult`

```python
@dataclass
class StructuralResolverResult:
    field_labels: dict[str, str]       # field_id -> semantic_label (resolved)
    unresolved_fields: list[FormFieldSpec]  # fields to pass to LLMFieldEnricher
    nearby_labels: dict[str, list[NearbyLabel]]  # nearby_labels for all fields
    form_title: str | None             # form title (if detected)
```

Processing order:
1. `get_acroform_fields()` + `extract_text_blocks_for_page()` (existing)
2. `resolve_field_ids()` -> add semantic field_ids to resolved
3. `resolve_by_table_structure()` -> add table-resolved fields
4. `DirectionalFieldEnricher.enrich()` -> generate directional labels for all fields
5. Form title detection: largest text block near page top (y < 50pt)

### Module 3: `LLMFieldEnricher` — Vision + Per-Page LLM Fallback

Identify fields that StructuralResolver could not resolve using Vision LLM.
**Extend existing `LLMFieldEnricher` class.**

**File**: `apps/api/app/services/form_context/enricher.py` (existing)

#### `LLMFieldEnricher.enrich()` Extension

Per-page processing (already implemented — page-parallel via `asyncio.gather()`):
1. Group unresolved fields by page
2. For each page:
   a. Get blocks via `extract_text_blocks_for_page()`
   b. Pre-filter to nearby blocks via `_prefilter_blocks()`
   c. Include nearby_labels candidates in prompt (LLM hint)
   d. LLM call (compact JSON format)

Prompt design (per-page):
```
System: You are a PDF form field identification assistant.
You will see a list of form fields with their positions and nearby text candidates.
For each field, identify its semantic label based on the spatial layout.

User:
Fields on this page:
- Text23: b=[577,165,682,199], nearby=["Address(L,3pt)", "Transfer Date(A,2pt)"]
- Text24: b=[683,165,750,199], nearby=["Transfer Date and Reason(A,0pt)"]

Respond in compact format:
field_id:label
(Only include fields you can identify with confidence >= 0.5)
```

Key design decisions:
- Pass nearby_labels as candidates (serves as LLM hint, speeds up output)
- **Output is `field_id:label` one-line format** (not JSON — reduces output tokens)
- Fewer unresolved fields per page means faster LLM calls

### Module 4: `AutofillPipelineService` — Async Orchestration

**Extend existing `AutofillPipelineService`.**

**File**: `apps/api/app/services/autofill_pipeline/service.py` (existing)

#### `FieldIdentificationResult` (new data model)

```python
# apps/api/app/domain/models/field_identification.py (new)
@dataclass(frozen=True)
class FieldIdentificationResult:
    field_labels: dict[str, str]         # field_id -> semantic_label
    confidence: dict[str, float]         # field_id -> confidence
    resolution_method: dict[str, str]    # field_id -> "field_id" | "table" | "vision" | "nearby"
    nearby_labels: dict[str, list[NearbyLabel]]  # for autofill prompt
    form_title: str | None
```

#### Quick Mode (extend existing `autofill()`)

```python
async def autofill(self, ...):
    # Phase 1: StructuralResolver (0.1s)
    resolved = structural_resolver.resolve(document_id, fields, document_service)

    # Skip LLM enrichment — use top nearby_labels candidate as label
    enriched_fields = apply_resolved_labels(fields, resolved)

    # Phase 2: existing pipeline (context_build -> plan -> render)
    ...
```

#### Precise Mode (extend existing `autofill_turn()`)

```python
async def autofill_turn(self, ...):
    # Phase 1: StructuralResolver (0.1s)
    resolved = structural_resolver.resolve(document_id, fields, document_service)

    if not resolved.unresolved_fields:
        # All resolved -> immediate fill plan
        ...

    # Phase 2: Launch LLMFieldEnricher async (runs in background)
    llm_task = asyncio.create_task(
        llm_enricher.enrich(document_id, tuple(resolved.unresolved_fields))
    )

    # Phase 3: Generate questions immediately from StructuralResolver result (3s)
    turn_result = await self._fill_planner.plan_turn(context, ...)

    # Phase 4: User answer or LLM enrichment complete -> high-accuracy mapping
    ...
```

### Module 5: `CorrectionTracker` — Diff Correction

**Extend existing `CorrectionTracker`.**

**File**: `apps/api/app/services/correction_tracker/tracker.py` (existing)

Correct provisional mapping after LLM enrichment completes.

#### Function: `async correct_mapping(preliminary, level2_labels) -> list[CorrectionRecord]`

```python
# apps/api/app/domain/models/correction_record.py (use existing model)
```

Logic:
1. Compare preliminary field_labels with level2_labels
2. Identify fields where labels differ
3. Re-evaluate whether mapped values are correct for changed labels
4. Return only fields that need value changes as CorrectionRecords

Important: Only pass diffs to LLM (do not re-map all fields).

## Integration with Existing System

### FieldEnricher Protocol (existing)

```python
# apps/api/app/services/form_context/enricher.py (existing)
class FieldEnricher(Protocol):
    async def enrich(
        self, document_id: str, fields: tuple[FormFieldSpec, ...],
    ) -> tuple[FormFieldSpec, ...]: ...

# Existing implementations:
# - ProximityFieldEnricher: center-distance based (to be replaced)
# - LLMFieldEnricher: LLM + compact JSON + page-parallel

# New implementations:
# - DirectionalFieldEnricher: directional (left/above/right)
# - StructuralResolverEnricher: StructuralResolver + DirectionalFieldEnricher fallback
```

### FormContextBuilder (existing)

```python
# apps/api/app/services/form_context/builder.py (existing)
class FormContextBuilder:
    def __init__(self, data_source_repo, extraction_service, enricher: FieldEnricher):
        self._enricher = enricher  # <- FieldEnricher injected

    async def _enrich_fields_async(self, document_id, fields):
        return await self._enricher.enrich(document_id, fields)  # no branching
```

### Prompt Structure (existing)

```
AUTOFILL_SYSTEM_PROMPT      -> used by autofill (quick mode) — no change
DETAILED_MODE_SYSTEM_PROMPT -> used by autofill_turn (detailed mode) — no change
FIELD_IDENTIFICATION_SYSTEM_PROMPT -> used by LLMFieldEnricher Vision prompt (compact JSON)
```

### FillPlanner Improvement

Current `_select_relevant_fields()` partitions fields by matching label_candidates against data source keys. With StructuralResolver, resolved fields have semantic `label` set, greatly improving match accuracy:

```
Before:
  {"id": "Text1", "nearby_labels": ["Tax Office", "Salary Payer"]}
  -> if ds_keys has no "Salary Payer" match -> falls to rest -> compact one-liner

After:
  {"id": "Text1", "label": "Salary Payer Name", "resolved_by": "table"}
  -> label is semantic so ds_keys match more easily -> classified as relevant
```

### Output Token Optimization Strategy

**The bottleneck**: FillPlanner output is ~9,500 tokens for 189 fields. Output token generation speed is the dominant latency — much slower than input processing. Naively removing unfilled fields from output drops accuracy because they serve as implicit Chain-of-Thought.

**Why reducing tokens doesn't lose accuracy — the key insight**:

Currently the FillPlanner LLM does TWO jobs in a single call:
1. **Field identification**: figure out what "Text1" means from nearby_labels
2. **Value matching**: match the identified label to a data source value

The unfilled fields in the output are Chain-of-Thought for job #1 — the LLM reasons through each field's identity even when it can't fill it. Removing them naively drops accuracy because job #1 loses its thinking space.

StructuralResolver **eliminates job #1 before the LLM is called**. When the FillPlanner receives `{"id": "Text1", "label": "Salary Payer Name"}` instead of `{"id": "Text1", "nearby_labels": ["Tax Office", "Salary Payer"]}`, the LLM only needs to do job #2 (straightforward key-value matching). The CoT that was embedded in the output is now done by Python (0 tokens, 0.1s).

```
Before (single LLM call does both jobs):
  Input:  "Text1" + nearby_labels  ->  LLM must identify + match
  Output: ALL 189 fields (filled + unfilled as CoT) = ~9,500 tokens

After (StructuralResolver handles job #1):
  Python: "Text1" -> "Salary Payer Name"  (0 tokens, 0.1s)
  Input:  "Salary Payer Name"  ->  LLM only matches to data source
  Output: only filled_fields = ~2,000 tokens (no CoT needed)
```

**Multi-layered reduction approach**:

| Strategy | Output Token Reduction | How |
|---|---|---|
| **StructuralResolver pre-resolution** | -40~80% fields sent to LLM | Fields resolved by table structure / field_id semantics never enter LLM prompt — zero output tokens for them |
| **Eliminate CoT need** | -50% of remaining output | With semantic labels pre-set, LLM doesn't need unfilled fields as thinking space — output only `filled_fields` without accuracy loss |
| **`field_id:label` one-line format** (LLMFieldEnricher) | ~70% reduction vs JSON | `Text23:Address` instead of `{"field_id":"Text23","label":"Address","confidence":0.9}` |
| **Per-page parallel calls** | Latency /N (N=pages) | Each page produces ~950 tokens instead of 9,500. Wall-clock = slowest page, not sum |
| **Relevant/rest split** (FillPlanner) | -30~60% output tokens | StructuralResolver improves relevant classification -> more fields get semantic labels -> `_select_relevant_fields()` puts fewer fields in "rest" compact section -> LLM skips them in output |

**Expected combined effect** (189-field form):
```
Current:  189 fields -> 1 LLM call -> ~9,500 output tokens -> ~70s
          (LLM does field identification + value matching together)

Target:   StructuralResolver resolves 80% (151 fields) in Python (0 tokens, 0.1s)
          FillPlanner receives semantic labels -> only value matching needed
          -> LLM outputs only filled_fields (~60 fields) = ~2,000 tokens
          -> ~15-20s for FillPlanner call

          LLMFieldEnricher (for 38 unresolved fields across ~5 pages):
          -> 5 parallel calls, ~8 fields each
          -> ~50 output tokens/page (field_id:label format)
          -> ~5-10s (parallel, limited by slowest page)
```

## Test Strategy

### Unit Tests

```
apps/api/tests/
  test_label_enrichment.py         # existing — ProximityFieldEnricher tests
  test_directional_enrichment.py   # new — DirectionalFieldEnricher tests
  test_structural_resolver.py      # new — StructuralResolver tests
  test_protocol_compliance.py      # existing — FieldEnricher Protocol compliance tests
```

1. `DirectionalFieldEnricher`:
   - Directional label detection accuracy (left/above/right)
   - Distance and Y-center diff filtering
   - Single-character text exclusion
   - Page boundary handling

2. `StructuralResolver`:
   - Table detection -> cell -> field mapping accuracy
   - field_id semantics check correctness
   - Header row recognition accuracy

3. `AutofillPipelineService`:
   - Quick/Precise mode switching
   - LLM enrichment incomplete fallback behavior
   - Diff correction accuracy

### Integration Tests

Prepare 3 types of test PDFs:
1. Japanese government form (with table structure) -> expect StructuralResolver resolves 80%+
2. US/EU Tax Form (partial tables) -> StructuralResolver resolves 50-60%, LLMFieldEnricher handles rest
3. Free-layout PDF -> StructuralResolver low resolution rate, LLMFieldEnricher primary

### Performance Measurement

Use existing `StopWatch`:
```python
# apps/api/app/infrastructure/observability/stopwatch.py (existing)
sw = StopWatch()
with sw.lap("structural_resolve"):
    resolved = structural_resolver.resolve(...)
with sw.lap("llm_enrich"):
    enriched = await llm_enricher.enrich(...)

# Record in PipelineStepLog (existing step_logs pattern)
```

## File Structure

```
apps/api/app/
  services/
    form_context/
      __init__.py                     # existing — exports
      builder.py                      # existing — FormContextBuilder
      enricher.py                     # existing — FieldEnricher Protocol + implementations
                                      #   ProximityFieldEnricher -> DirectionalFieldEnricher (replace)
                                      #   LLMFieldEnricher (existing)
      structural_resolver.py           # new — StructuralResolver (table + field_id semantics)
    document_service.py               # existing — PDF preprocessing (PyMuPDF)
    autofill_pipeline/
      service.py                      # existing — AutofillPipelineService
      models.py                       # existing — AutofillPipelineResult
      step_log.py                     # existing — PipelineStepLog
    correction_tracker/
      tracker.py                      # existing — CorrectionTracker
    fill_planner/
      planner.py                      # existing — FillPlanner
      schemas.py                      # existing — Pydantic schemas
    vision_autofill/
      prompts.py                      # existing — LLM prompt definitions
    llm/
      client.py                       # existing — LiteLLMClient
  domain/
    models/
      form_context.py                 # existing — FormFieldSpec, LabelCandidate, FormContext
      field_identification.py         # new — FieldIdentificationResult
      correction_record.py            # existing — CorrectionRecord
    protocols/
      form_context_builder.py         # existing — FormContextBuilderProtocol
  models/
    common.py                         # existing — BBox
    acroform.py                       # existing — AcroFormFieldInfo, AcroFormFieldsResponse
  routes/
    autofill_pipeline.py              # existing — DI wiring

apps/api/tests/
  test_label_enrichment.py            # existing
  test_directional_enrichment.py      # new
  test_structural_resolver.py         # new
  test_protocol_compliance.py         # existing
```

## Dependencies

```
PyMuPDF (fitz)      # PDF parsing, text extraction, table detection (existing)
litellm             # LLM calls (existing)
instructor          # structured output (existing)
pydantic            # data models (existing)
asyncio             # async processing (stdlib)
```

**Note**: `pdfplumber` is NOT used. All PDF processing is unified on `PyMuPDF (fitz)`.

## Implementation Order

1. `DirectionalFieldEnricher` — directional label detection (add to `enricher.py`)
2. `structural_resolver.py` — StructuralResolver (independently testable module)
3. `field_identification.py` — FieldIdentificationResult data model
4. `AutofillPipelineService` extension — StructuralResolver / LLMFieldEnricher integration + async control
5. `CorrectionTracker` extension — diff correction
6. Existing FillPlanner `_select_relevant_fields()` improvement
7. Tests

## Notes

- PyMuPDF's `page.find_tables()` does not work on all PDFs. When rules are not vector-based, it returns an empty list. In that case, StructuralResolver table analysis gracefully skips and passes all fields as unresolved to LLMFieldEnricher.
- LLMFieldEnricher output uses **`field_id:label` one-line format, not JSON**. Output token reduction directly improves speed.
- Diff correction only targets fields where "label changed" AND "mapped value is affected". Most fields need no correction.
- `DirectionalFieldEnricher` does not depend on a fixed distance threshold. Per-direction thresholds (left: 50pt/Y-diff 15pt, above: 50pt/X-diff 80pt, right: 50pt/Y-diff 15pt) are reasonable defaults based on typical form layouts, but can be changed to font-height-based dynamic thresholds in the future.
- The existing `FieldEnricher` Protocol is unchanged. `DirectionalFieldEnricher` implements the same `enrich()` interface, so switching only requires a DI wiring change.
