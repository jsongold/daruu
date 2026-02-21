# Error Recovery Documentation

This document describes the error recovery mechanisms in the daru-pdf system, a PDF auto-filling AI system with deterministic baseline and agentic fallback.

## Table of Contents

1. [OCR Failure Handling](#1-ocr-failure-handling)
2. [LLM Timeout Handling](#2-llm-timeout-handling)
3. [Partial Success Scenarios](#3-partial-success-scenarios)
4. [Decision Engine Recovery](#4-decision-engine-recovery)
5. [Infrastructure Failures](#5-infrastructure-failures)

---

## 1. OCR Failure Handling

### Overview

The Extract Service implements a multi-tier text extraction approach where OCR serves as a fallback when native PDF text extraction fails or returns insufficient results.

### What Triggers OCR Fallback

OCR is triggered when:
- Native PDF text extraction returns empty or insufficient text
- The extracted text confidence is below the threshold
- The document contains scanned images instead of text layers

**Code Reference:** `apps/api/app/services/extract/service.py`

```python
# Step 1: Try native PDF text extraction
native_result = await self._try_native_extraction(
    document_ref=document_ref,
    field=field,
)

# Step 2: Try OCR if enabled and native extraction insufficient
if use_ocr and len(candidates) == 0:
    ocr_result = await self._try_ocr_extraction(
        field=field,
        artifacts_by_page=artifacts_by_page,
    )
```

### Retry Strategy

The system uses a progressive fallback strategy rather than blind retries:

| Priority | Method | Confidence | Speed |
|----------|--------|------------|-------|
| 1 | Native PDF text extraction | 0.95 | Fastest |
| 2 | OCR extraction | Variable (avg_confidence) | Medium |
| 3 | LLM-assisted extraction | 0.85 | Slowest |

```python
# Native text gets high confidence
if native_result.full_text.strip():
    candidates.append(
        ValueCandidate(
            value=native_result.full_text.strip(),
            confidence=0.95,
            rationale="Extracted from native PDF text layer",
            evidence_refs=(native_evidence.id,),
        )
    )

# OCR result uses its own confidence
if ocr_result.full_text.strip():
    candidates.append(
        ValueCandidate(
            value=ocr_result.full_text.strip(),
            confidence=ocr_result.avg_confidence,
            rationale=f"Extracted via OCR ({ocr_result.engine})",
            evidence_refs=(ocr_evidence.id,),
        )
    )
```

### Graceful Degradation

When OCR fails completely, the system:

1. Records an OCR request for later processing
2. Generates a follow-up question for user input
3. Marks the extraction as needing review

```python
elif field.bbox is not None:
    # Request OCR for this region
    ocr_requests.append(
        OcrRequest(
            field_id=field.field_id,
            page=field.page,
            bbox=field.bbox,
            reason="Native text extraction found no content",
        )
    )

# If still no candidates, generate followup question
if len(candidates) == 0:
    if use_llm and self._extraction_agent is not None:
        question = await self._extraction_agent.generate_question(
            field=field,
            reason="No text found in specified region",
            candidates=None,
        )
        followup_questions.append(question)
```

---

## 2. LLM Timeout Handling

### Overview

The system implements configurable timeout thresholds and retry mechanisms with exponential backoff for LLM operations.

### Timeout Thresholds

Configuration in `apps/api/app/config.py`:

```python
# LLM Configuration
openai_timeout_seconds: int = 120
openai_max_concurrent_requests: int = 5
```

Strategy-level timeout configuration in `apps/api/app/models/processing_strategy.py`:

```python
@dataclass(frozen=True)
class StrategyConfig:
    """Configuration for a processing strategy."""

    llm_timeout_seconds: int = 30
    max_llm_retries: int = 2
    fallback_on_llm_error: bool = True
```

### Retry with Backoff

The system supports multiple retry strategies:

**Default Strategy (HYBRID):**
```python
DEFAULT_STRATEGY = StrategyConfig(strategy=ProcessingStrategy.HYBRID)
```

**Full LLM Strategy (with extended timeout):**
```python
FULL_LLM_STRATEGY = StrategyConfig(
    strategy=ProcessingStrategy.LLM_ONLY,
    skip_llm_on_high_confidence=False,
    llm_timeout_seconds=60,
    max_llm_retries=3,
)
```

**Resilient Strategy (with fallback):**
```python
RESILIENT_STRATEGY = StrategyConfig(
    strategy=ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK,
    fallback_on_llm_error=True,
    llm_timeout_seconds=30,
    max_llm_retries=2,
)
```

### Fallback to Deterministic Processing

When LLM times out or fails, the system falls back to deterministic processing:

**Code Reference:** `apps/api/app/services/extract/service.py`

```python
# For LLM-first strategies, try LLM extraction first
if effective_strategy.is_llm_first() and self._extraction_agent is not None:
    try:
        return await self._extract_field_llm_first(...)
    except Exception as e:
        if effective_strategy.should_fallback_on_error():
            logger.warning(f"LLM extraction failed, falling back to local: {e}")
            # Continue with local extraction below
        else:
            raise
```

**Code Reference:** `apps/api/app/services/mapping/service.py`

```python
try:
    # Try batch inference with LLM
    inferred = await self._mapping_agent.infer_mappings_batch(
        source_fields=unmapped_sources,
        target_fields=available_targets,
        existing_mappings=(),
    )
    mappings.extend(inferred)
except Exception as e:
    if strategy.should_fallback_on_error():
        logger.warning(f"LLM batch inference failed, falling back: {e}")
        return await self._process_local_first(
            unmapped_sources=unmapped_sources,
            available_targets=available_targets,
            request=request,
            strategy=StrategyConfig(strategy=ProcessingStrategy.LOCAL_ONLY),
        )
    else:
        raise
```

### Fallback Decision Logic

```python
def should_fallback_on_error(self) -> bool:
    """Check if fallback is enabled on LLM error."""
    return (
        self.fallback_on_llm_error
        and self.strategy == ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK
    )
```

---

## 3. Partial Success Scenarios

### Overview

The pipeline is designed to handle partial successes gracefully, allowing processing to continue even when some fields fail extraction.

### How Pipeline Handles Partial Field Extraction

**Code Reference:** `apps/api/app/services/extract/service.py`

```python
for field in request.fields:
    try:
        result = await self._extract_field(
            document_ref=request.document_ref,
            field=field,
            artifacts_by_page=artifacts_by_page,
            use_ocr=use_ocr,
            use_llm=use_llm,
            confidence_threshold=request.confidence_threshold,
            strategy=effective_strategy,
        )

        if result.extraction is not None:
            extractions.append(result.extraction)
        all_evidence.extend(result.evidence)
        ocr_requests.extend(result.ocr_requests)
        followup_questions.extend(result.followup_questions)
        if result.error is not None:
            errors.append(result.error)

    except Exception as e:
        errors.append(
            ExtractError(
                field_id=field.field_id,
                code=ExtractErrorCode.INVALID_FIELD,
                message=f"Extraction failed: {str(e)}",
            )
        )
```

### Confidence Scoring for Partial Results

Confidence is tracked at multiple levels:

**Field-level confidence:**
```python
extraction = Extraction(
    field_id=field.field_id,
    value=best.value,
    normalized_value=normalized_value if normalized_value != best.value else None,
    confidence=best.confidence,
    source=source,
    evidence=tuple(evidence),
    needs_review=best.confidence < confidence_threshold or conflict_detected,
    conflict_detected=conflict_detected,
)
```

**Partial success in Ingest Service:**

**Code Reference:** `apps/api/app/services/ingest/service.py`

```python
def _create_success_result(
    self,
    document_id: str,
    document_meta: DocumentMeta,
    artifacts: tuple[RenderedPage, ...],
    errors: tuple[IngestError, ...],
) -> IngestResult:
    """Create a success result.

    Note: Success can have partial errors (e.g., some pages failed to render).
    """
    has_artifacts = len(artifacts) > 0
    has_critical_errors = any(
        e.code in (IngestErrorCode.CORRUPTED_FILE, IngestErrorCode.PASSWORD_PROTECTED)
        for e in errors
    )

    success = has_artifacts and not has_critical_errors

    return IngestResult(
        document_id=document_id,
        success=success,
        meta=document_meta,
        artifacts=artifacts,
        errors=errors,
    )
```

### User Intervention Triggers

The system triggers user intervention when:

1. **Confidence below threshold:**
```python
# Check if review is needed
needs_review = (
    best.confidence < confidence_threshold or conflict_detected
)
```

2. **Conflicts detected between sources:**
```python
if use_llm and len(candidates) > 1 and self._extraction_agent is not None:
    conflict_detected, _ = await self._extraction_agent.detect_conflicts(
        field=field,
        candidates=tuple(candidates),
    )
```

3. **No value found:**
```python
if len(candidates) == 0:
    if use_llm and self._extraction_agent is not None:
        question = await self._extraction_agent.generate_question(
            field=field,
            reason="No text found in specified region",
            candidates=None,
        )
        followup_questions.append(question)
```

---

## 4. Decision Engine Recovery

### Overview

The Decision Engine (`apps/api/app/services/orchestrator/decision_engine.py`) implements comprehensive loop control and stagnation detection to prevent infinite loops and escalate appropriately.

### Max Iteration Limits

**Configuration:**
```python
class OrchestratorConfig(BaseModel):
    max_iterations: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of retry iterations to prevent infinite loops",
    )
    max_steps_per_run: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum steps to execute in a single run_until_blocked call",
    )
```

**Enforcement:**
```python
def decide_next_action(
    self,
    job: JobContext,
    stage_result: StageResult | None,
    previous_issues: list[Issue] | None = None,
) -> NextAction:
    # 2. Check max iterations to prevent infinite loops
    if job.iteration_count >= self._config.max_iterations:
        return NextAction(
            action="blocked",
            reason=f"Maximum iterations ({self._config.max_iterations}) reached",
            field_ids=self._get_issue_field_ids(job.issues),
        )
```

### Stagnation Detection

The system detects when retries are not making progress:

**Code Reference:** `apps/api/app/services/orchestrator/domain/rules.py`

```python
def calculate_improvement_rate(
    previous_issues: list[Issue],
    current_issues: list[Issue],
) -> float:
    """Calculate improvement rate between iterations.

    Improvement is measured by:
    1. Reduction in total issue count
    2. Reduction in weighted issue score (severity-weighted)

    Returns:
        Improvement rate between 0.0 and 1.0.
    """
    if not previous_issues:
        return 1.0 if not current_issues else 0.0

    # Calculate count-based improvement
    prev_count = len(previous_issues)
    curr_count = len(current_issues)
    count_improvement = (prev_count - curr_count) / prev_count if prev_count > 0 else 0.0

    # Calculate score-based improvement (weighted by severity)
    prev_score = calculate_issue_score(previous_issues)
    curr_score = calculate_issue_score(current_issues)
    score_improvement = (prev_score - curr_score) / prev_score if prev_score > 0 else 0.0

    # Average of both metrics, clamped to [0, 1]
    improvement = (count_improvement + score_improvement) / 2.0
    return max(0.0, min(1.0, improvement))
```

**Issue Scoring by Severity:**
```python
def calculate_issue_score(issues: Sequence[Issue]) -> float:
    """Calculate total weighted score for a list of issues."""
    severity_weights = {
        IssueSeverity.CRITICAL: 10.0,
        IssueSeverity.HIGH: 5.0,
        IssueSeverity.ERROR: 5.0,
        IssueSeverity.WARNING: 2.0,
        IssueSeverity.INFO: 1.0,
    }

    return sum(
        severity_weights.get(issue.severity, 1.0)
        for issue in issues
    )
```

**Stagnation Handling:**
```python
def _check_improvement_rate(
    self,
    job: JobContext,
    previous_issues: list[Issue],
) -> NextAction | None:
    improvement = calculate_improvement_rate(
        previous_issues,
        list(job.issues),
    )

    if improvement < self._config.min_improvement_rate:
        return NextAction(
            action="ask",
            reason=f"Improvement rate too low ({improvement:.2%}), unable to resolve automatically",
            field_ids=[issue.field_id for issue in job.issues],
        )

    return None
```

### Escalation to Manual Review

The Decision Engine escalates to manual review based on issue severity:

```python
def _check_high_severity_issues(self, job: JobContext) -> NextAction | None:
    """Check for severity >= high issues.

    Per PRD: issues.severity >= high -> Ask or Manual (blocked)
    """
    if not self._config.high_severity_requires_user:
        return None

    high_severity_issues = [
        issue for issue in job.issues
        if issue.severity in (IssueSeverity.CRITICAL, IssueSeverity.HIGH, IssueSeverity.ERROR)
    ]

    if not high_severity_issues:
        return None

    field_ids = [issue.field_id for issue in high_severity_issues]
    first_issue = high_severity_issues[0]

    # CRITICAL issues require manual intervention (blocked)
    if first_issue.severity == IssueSeverity.CRITICAL:
        return NextAction(
            action="manual",
            reason=f"Critical issue requires manual intervention: {first_issue.message}",
            field_ids=field_ids,
        )

    # HIGH/ERROR issues ask for user input (blocked per PRD)
    return NextAction(
        action="ask",
        reason=f"High severity issue requires user input: {first_issue.message}",
        field_ids=field_ids,
    )
```

### Permanent vs. Transient Errors

The system distinguishes between errors that should and should not be retried:

```python
def _is_permanent_error(self, error_message: str) -> bool:
    """Check if an error is permanent and should not be retried.

    Permanent errors are those that won't be resolved by retrying:
    - Corrupted or invalid PDF files
    - Missing required files
    - Invalid file formats
    - Authentication/authorization errors
    """
    error_lower = error_message.lower()

    permanent_indicators = [
        "corrupted", "corrupt",
        "invalid pdf", "not a valid pdf",
        "missing root object", "no /root object",
        "pdf file is corrupted", "pdf file is invalid",
        "cannot open pdf", "pdf is password protected",
        "file not found", "file does not exist",
        "invalid file format", "unsupported format",
        "authentication failed", "unauthorized",
        "forbidden", "permission denied",
    ]

    return any(indicator in error_lower for indicator in permanent_indicators)
```

---

## 5. Infrastructure Failures

### Overview

The system handles various infrastructure failures including storage unavailability, database connection loss, and external service failures.

### Storage Unavailable

**PDF Error Classification:** `apps/api/app/services/ingest/domain/rules.py`

```python
def classify_pdf_error(error_message: str) -> tuple[IngestErrorCode, str]:
    """Classify a PDF library error into an IngestErrorCode."""
    error_lower = error_message.lower()

    # Password protection errors
    password_keywords = ["password", "encrypted", "decryption", "permission", "secured"]
    if any(kw in error_lower for kw in password_keywords):
        return (
            IngestErrorCode.PASSWORD_PROTECTED,
            "PDF is password-protected and cannot be processed",
        )

    # Corruption errors
    corruption_keywords = [
        "corrupt", "damaged", "invalid", "malformed",
        "truncated", "broken", "bad", "cannot read",
        "cannot open", "failed to open",
    ]
    if any(kw in error_lower for kw in corruption_keywords):
        return (
            IngestErrorCode.CORRUPTED_FILE,
            "PDF file appears to be corrupted or damaged",
        )

    # Format errors
    format_keywords = ["not a pdf", "format not supported", "unsupported", "unrecognized"]
    if any(kw in error_lower for kw in format_keywords):
        return (
            IngestErrorCode.UNSUPPORTED_FORMAT,
            "File format is not supported",
        )

    # Default to invalid PDF
    return (
        IngestErrorCode.INVALID_PDF,
        f"Failed to process PDF: {error_message}",
    )
```

### Per-Page Error Handling

When rendering pages, failures are isolated to individual pages:

```python
def _render_and_store_pages(
    self,
    context: IngestContext,
    document_meta: DocumentMeta,
    pages_to_render: tuple[int, ...],
) -> tuple[tuple[RenderedPage, ...], tuple[IngestError, ...]]:
    """Render pages and store as artifacts."""
    artifacts: list[RenderedPage] = []
    errors: list[IngestError] = []

    for page_num in pages_to_render:
        try:
            image_data = self._pdf_reader.render_page(
                context.document_ref,
                page_num,
                context.render_config.dpi,
            )
            # ... process successful render
            artifacts.append(rendered_page)

        except Exception as e:
            # Record error but continue with other pages
            error_code, error_message = classify_pdf_error(str(e))
            errors.append(
                IngestError(
                    code=error_code,
                    message=error_message,
                    page_number=page_num,
                )
            )

    return tuple(artifacts), tuple(errors)
```

### Database Connection Loss

The system uses repository pattern for data access, which allows for:

1. **Connection pooling** - Managed at the repository level
2. **Retry logic** - Can be implemented in repository adapters
3. **Graceful degradation** - Job state preserved before operations

### External Service Failures

**Service Client Pattern:**

The `ServiceClient` wraps all service calls, providing a central point for error handling:

**Code Reference:** `apps/api/app/services/orchestrator/service_client.py`

Stage execution with error handling:

```python
async def execute_stage(
    self,
    stage: PipelineStage,
    job: JobContext,
) -> StageResult:
    """Execute a pipeline stage."""
    # Service calls are wrapped with try/catch
    # Failures are converted to StageResult with success=False
```

**Stage Failure Handling:**

```python
def _handle_stage_failure(
    self,
    job: JobContext,
    stage_result: StageResult,
) -> NextAction:
    """Handle a failed stage execution."""
    error_msg = stage_result.error_message or "Unknown error"

    # Check if this is a permanent error that shouldn't be retried
    if self._is_permanent_error(error_msg):
        return NextAction(
            action="blocked",
            reason=f"Stage {stage_result.stage.value} failed with permanent error: {error_msg}",
            field_ids=self._get_issue_field_ids(stage_result.issues),
        )

    # Check if we should retry the same stage (if not at max iterations)
    if job.iteration_count < self._config.max_iterations - 1:
        return NextAction(
            action="retry",
            stage=stage_result.stage,
            reason=f"Stage {stage_result.stage.value} failed: {error_msg}",
            field_ids=self._get_issue_field_ids(stage_result.issues),
        )

    return NextAction(
        action="blocked",
        reason=f"Stage {stage_result.stage.value} failed after max retries: {error_msg}",
        field_ids=self._get_issue_field_ids(stage_result.issues),
    )
```

---

## Error Recovery Flow Summary

```
                              +----------------+
                              |   Start Job    |
                              +-------+--------+
                                      |
                                      v
                              +-------+--------+
                              |  Execute Stage |
                              +-------+--------+
                                      |
                         +------------+------------+
                         |                         |
                    Success?                   Failure?
                         |                         |
                         v                         v
                +--------+--------+       +--------+--------+
                | Check Issues    |       | Is Permanent?   |
                +--------+--------+       +--------+--------+
                         |                    |         |
            +------------+------------+   Yes |         | No
            |            |            |       |         |
       No Issues    Low Conf     High Sev    |         v
            |            |            |       |    +----+----+
            v            v            v       |    |  Retry  |
        +---+---+   +----+----+  +----+----+  |    | Allowed?|
        | Done  |   |  Ask    |  | Manual  |  |    +----+----+
        +-------+   +---------+  +---------+  |         |
                                              |    +----+----+
                                              +--->| Blocked |
                                                   +---------+
```

## Configuration Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_iterations` | 10 | Max retry loops before blocking |
| `confidence_threshold` | 0.7 | Minimum confidence for acceptance |
| `max_steps_per_run` | 100 | Max steps in a single run |
| `min_improvement_rate` | 0.1 | Min improvement to continue retrying |
| `llm_timeout_seconds` | 30 | LLM operation timeout |
| `max_llm_retries` | 2 | LLM retry attempts |
| `fallback_on_llm_error` | true | Fall back to local on LLM failure |
| `high_severity_requires_user` | true | Require user input for high severity |

## Best Practices

1. **Always set appropriate timeouts** - Configure `llm_timeout_seconds` based on expected response times
2. **Use HYBRID strategy** for production - Balances speed and quality with fallback
3. **Monitor improvement rate** - Low improvement rate indicates systematic issues
4. **Handle partial success** - Design UIs to show partial results with confidence
5. **Log all errors** - Ensure error classification is logged for debugging
6. **Test infrastructure failures** - Include chaos testing for storage/database failures
