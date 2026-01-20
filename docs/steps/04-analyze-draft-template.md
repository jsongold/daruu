# Step 04: Analyze (LLM generates DraftTemplate)

## Goal
Introduce the LLM-based structure understanding phase:
PDF -> DraftTemplate (fields + initial placement guesses) that can be refined in the Adjust UI.

## Scope
- Backend endpoint: `POST /analyze`
  - Input: template PDF (upload or GCS URL)
  - Preprocess:
    - Render each page to PNG using PyMuPDF
    - Extract page size and (optional) text blocks
  - LLM call:
    - Provide page images + page sizes
    - Request JSON output conforming to DraftTemplate schema
    - Must output:
      - ~10-20 key fields
      - placement guesses (x/y/max_width) per field
      - field types and required flags
  - Output: `schema_json` (DraftTemplate)
- Add robust validation:
  - strict JSON schema validation
  - retry with “repair prompt” on invalid JSON (bounded retries)
- Minimal safety:
  - never include user-entered PII in prompt beyond the PDF itself
  - ensure timeouts/retries

## Out of Scope
- Learning logs (v3)
- Auto-QA vision validation pipeline (later)
- DB persistence of templates (Step 05 can persist analyze output)
- Advanced anchors/relative placement (optional later)

## Files/Dirs to touch
- `apps/api/app/routes/analyze.py`
- `apps/api/app/services/pdf_render.py`
- `apps/api/app/services/llm_analyze.py`
- `apps/api/app/models/template_schema.py`
- `apps/api/tests/test_analyze.py`

## Prompting Notes (must be implemented)
- Output MUST be valid JSON only (no markdown).
- Enforce schema:
  - `fields[].id`, `fields[].label`, `fields[].type`
  - `fields[].placement.page_index`, `x`, `y`, `max_width`
- Ask for conservative defaults:
  - font_policy: max=10, min=6
  - align=left

## Done Criteria (Acceptance)
- `/analyze` returns a DraftTemplate JSON for a sample PDF.
- JSON validates against schema without manual fixes.
- The DraftTemplate can be loaded into the Adjust UI and edited.
- `make check-api` passes.

## Commands
- `make check-api`
