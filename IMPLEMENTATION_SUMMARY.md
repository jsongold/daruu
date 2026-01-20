# Debug Mode Implementation Summary

## Overview

Comprehensive debug output has been added to the Daru PDF analysis pipeline. When `DEBUG=true` is set with `LOG_LEVEL=DEBUG`, all parsed and extracted data is logged to stdout/console with detailed information about each pipeline stage.

## Changes Made

### 1. Core Pipeline (`apps/api/app/services/analysis/pipeline.py`)

**Added debug logging at each pipeline stage:**
- Pipeline initialization (strategy, PDF size)
- AcroForm detection and extraction
- Visual structure analysis (page count, anchor detection)
- LLM classification (form vs non-form decision)
- Vision field extraction (per-page results)
- Final template output

**Debug output format:**
```
DEBUG - Pipeline start: strategy=auto, pdf_size=245789 bytes
DEBUG - AcroForm Check: pdf_size=245789, pages=3, has_acroform=true, field_count=15
DEBUG - Visual structure analysis: pages=3, page_0_size=(612.0x792.0), anchors=24
DEBUG - LLM Classification result: is_form=true, page_index=0
DEBUG - Vision extraction complete: fields_count=15, template={...}
DEBUG - Final template: {complete template JSON}
```

### 2. Analysis Strategies (`apps/api/app/services/analysis/strategies.py`)

**Enhanced debug logging in:**
- `BaseAnalysisStrategy._call_openai()` - LLM request payloads and responses
- `DocumentClassifier._llm_classify()` - Classification decisions
- `HybridStrategy.analyze()` - Page-by-page extraction details
- `HybridStrategy._snap_fields_to_anchors()` - Field coordinate adjustments
- `VisionLowResStrategy.analyze()` - Low-res extraction details

**Debug output includes:**
```
DEBUG - LLM request start: attempt=1, model=gpt-4o, detail=high, images=1
DEBUG - LLM request payload: {model, detail, images_count, prompt_length, prompt, pages_info}
DEBUG - LLM request success: attempt=1, status=200, duration=2.456s
DEBUG - llm_response_1: {attempt, status, duration, response_length, response}
DEBUG - HybridStrategy: Processing page 0
DEBUG - hybrid_page_0_extraction: {page_index, page_size, llm_response}
DEBUG - Snapped field 'Name': (50.0, 100.0) -> (52.1, 101.5) [dist=2.1]
```

### 3. Main Application (`apps/api/app/main.py`)

**Enhanced logging configuration:**
- Better logging format with timestamps when DEBUG=true
- Startup message indicating debug mode is enabled
- More detailed error traces

### 4. Analyze Route (`apps/api/app/routes/analyze.py`)

**Added debug summary:**
- Logs strategy, filename, PDF size, duration, fields extracted
- Notifies user about debug output in console

## Debug Information Available

### Pipeline Execution
- Which strategy was chosen (auto, vision_only, acroform_only, vision_low_res)
- Success/failure at each stage
- Reasons for rejecting documents or skipping steps
- Total execution time

### PDF Analysis
- PDF size and structure (pages, mediabox)
- AcroForm field count and names
- Visual elements (anchors, lines, rectangles count)
- Text blocks and positions

### Field Extraction
- LLM prompts sent (with model, detail level, coordinate system)
- LLM responses (raw JSON, timing)
- Parsed field data per page
- Fields extracted per page
- Field position adjustments (snapping to visual anchors)

### LLM Interactions
- Request attempt count and model
- Response status codes and timing
- Response duration in seconds
- Retry attempts and error details
- Full error types and messages

### AcroForm Enrichment (if applicable)
- Input fields to enrichment
- LLM enrichment responses
- Enriched labels and sections
- Final enriched template

## Enabling Debug Mode

```bash
# Enable both DEBUG and detailed logging
export DEBUG=true
export LOG_LEVEL=DEBUG
python -m uvicorn app.main:app --reload
```

Or in one command:
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app --reload
```

## Console Output

All debug information is logged to console using Python's `logging` module:

```
[timestamp] - [module_name] - DEBUG - [message]
[timestamp] - [module_name] - INFO - [message]
[timestamp] - [module_name] - ERROR - [message]
```

Example output:
```
2025-01-20 10:30:45,123 - app.services.analysis.pipeline - DEBUG - Pipeline start: strategy=auto, pdf_size=245789 bytes
2025-01-20 10:30:45,200 - app.services.analysis.pipeline - DEBUG - AcroForm Check: pdf_size=245789, pages=3, has_acroform=true, field_count=15, fields=['field1', 'field2', 'field3']
2025-01-20 10:30:45,300 - app.services.analysis.strategies - DEBUG - LLM request start: attempt=1, model=gpt-4o, detail=high, images=1
2025-01-20 10:30:47,800 - app.services.analysis.strategies - DEBUG - LLM request success: attempt=1, status=200, duration=2.456
2025-01-20 10:30:48,100 - app.services.analysis.pipeline - DEBUG - Final template: {name: "acroform-import", version: "v1", fields: [...]}
2025-01-20 10:30:48,150 - app.routes.analyze - INFO - Analyze completed in 3.15s
2025-01-20 10:30:48,150 - app.routes.analyze - DEBUG - DEBUG summary: strategy=auto, filename=form.pdf, pdf_size=245789, duration=3.15s, fields_extracted=15
```

## Files Modified

1. **[apps/api/app/main.py](apps/api/app/main.py)** - Enhanced logging configuration for debug mode
2. **[apps/api/app/routes/analyze.py](apps/api/app/routes/analyze.py)** - Added debug summary to logs
3. **[apps/api/app/services/analysis/pipeline.py](apps/api/app/services/analysis/pipeline.py)** - Debug logging at each pipeline stage
4. **[apps/api/app/services/analysis/strategies.py](apps/api/app/services/analysis/strategies.py)** - Debug logging throughout all strategies

## Documentation Created

1. **[DEBUG_MODE.md](DEBUG_MODE.md)** - Comprehensive debug reference with all output types and filtering
2. **[DEBUG_QUICK_START.md](DEBUG_QUICK_START.md)** - Quick start guide for immediate use

## Benefits

1. **Full Transparency** - See exactly what data is being extracted at each stage
2. **Easy Debugging** - Identify where extraction goes wrong with detailed logs
3. **Performance Analysis** - Track timing for each LLM request
4. **Quality Assessment** - Review LLM responses and decisions in real-time
5. **Optimization** - Find bottlenecks and improve prompts based on visible behavior
6. **Integration** - Test and validate extraction results with readable output

## Backward Compatibility

- **Debug mode is disabled by default** (DEBUG=false)
- When disabled: **zero performance impact**, no extra logging
- Response format is **unchanged** whether DEBUG is true or false
- All existing tests **continue to pass**
- **No external dependencies** added

## Performance Impact

- **Disabled (default)**: No impact
- **Enabled**:
  - Minimal overhead from logger.debug() calls (typically < 1%)
  - No disk I/O (output goes to console only)
  - Slight string formatting overhead
  - Generally negligible compared to LLM request time

## Usage Examples

### Basic Debug Output

```bash
# Start with debug
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app --reload

# In another terminal, analyze
curl -X POST http://localhost:8000/analyze \
  -F "file=@form.pdf" \
  | jq '.schema_json.fields | length'
```

Console will show:
```
DEBUG - Pipeline start: strategy=auto, pdf_size=245789 bytes
DEBUG - AcroForm Check: ...
DEBUG - Final template: ...
```

### Filter to Specific Information

```bash
# Only show errors
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep ERROR

# Only show LLM interactions
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep -i llm

# Only show field extraction
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep -i extraction
```

### Save to File for Analysis

```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app > debug.log 2>&1 &
# ... run your requests ...
grep "DEBUG" debug.log  # View all debug messages
```

## What Gets Logged

### When DEBUG=true

✓ Each pipeline stage execution
✓ PDF structure analysis (pages, fields, anchors)
✓ LLM classification decisions
✓ Field extraction details (per page, per field)
✓ LLM prompts and responses
✓ Field coordinate adjustments
✓ Error details with full context
✓ Final template structure

### NOT logged (for privacy/security)

✗ Full image data (referenced but not logged)
✗ API keys (just mentioned as configured)
✗ Large binary data

## Testing Debug Mode

To verify debug mode works:

```python
import os
os.environ["DEBUG"] = "true"

# Run analysis - debug logs will appear in console
result = await analyze_pdf(pdf_bytes, strategy="auto")

# Check result
assert len(result["fields"]) > 0
```

## Summary

This implementation provides complete visibility into the PDF analysis pipeline through console logging. When `DEBUG=true` and `LOG_LEVEL=DEBUG` are set:

- **All** data parsed and extracted is logged
- **Pipeline flow** is clearly visible
- **LLM interactions** are fully documented
- **Performance metrics** are available
- **Errors** include full context

All without any performance impact when debug mode is disabled (the default).
