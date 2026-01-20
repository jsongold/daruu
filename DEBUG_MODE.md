# Debug Mode Documentation

This document explains how to use the debug mode in Daru PDF's analysis pipeline.

## Enabling Debug Mode

Set the `DEBUG` environment variable to `true` before starting the API:

```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
python -m uvicorn app.main:app --reload
```

Or in one command:
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app --reload
```

## What Gets Logged

When debug mode is enabled, the system outputs detailed debug messages to stdout/logs:

1. **Pipeline Execution** - Each step (AcroForm check → visual structure → classification → extraction)
2. **PDF Analysis** - PDF structure, pages, AcroForm fields, visual anchors
3. **Field Extraction** - LLM prompts, responses, parsed field data
4. **Coordinate Processing** - Field adjustments, snapping to visual anchors
5. **LLM Interactions** - Request timing, response status, retry attempts
6. **Error Details** - Full exception information with types and messages

## Console Output Format

Debug messages appear in the console with this format:

```
[timestamp] - [module] - DEBUG - [message]
```

Example:
```
2025-01-20 10:30:45,123 - app.services.analysis.pipeline - DEBUG - AcroForm Check: pdf_size=245789, pages=3, has_acroform=true, field_count=15, fields=['field1', 'field2', ...]
```

## Debug Log Categories

### Pipeline Stages

When `DEBUG=true`, you'll see logs for each pipeline stage:

```
Pipeline start: strategy=auto, pdf_size=245789 bytes
AcroForm Check: pdf_size=245789, pages=3, has_acroform=true, field_count=15
AcroForm extracted template: [full template JSON]
Visual structure analysis: pages=3, page_0_size=(612.0x792.0), anchors=24
LLM Classification result: is_form=true, page_index=0
Vision extraction start: strategy=hybrid, pages=[page_0(612x792,text_blocks=5,anchors=24)]
Vision extraction complete: fields_count=15, template=[template JSON]
Final template: [complete template with all fields]
```

### LLM Communication

```
LLM request start: attempt=1, model=gpt-4o, detail=high, images=1
llm_request_payload: {"model": "gpt-4o", ...}
LLM request success: attempt=1, status=200, duration=2.456
llm_response_1: {"attempt": 1, "status": 200, "duration": 2.456, ...}
```

### Field Extraction (per page)

```
HybridStrategy: Processing page 0
hybrid_page_0_extraction: [LLM response]
hybrid_page_0_parsed_items: items_count=12, items=[...]
hybrid_page_0: Extracted 12 fields from page 0
HybridStrategy: Snapped fields to anchors - 10 fields snapped
HybridStrategy: Analysis complete - 15 fields
```

### AcroForm Enrichment

```
Attempting to enrich AcroForm fields...
acroform_enrichment_input_page0_*: page_index=0, field_count=15, fields=[...]
acroform_enrichment_response_page0_*: [LLM enrichment response]
acroform_enrichment_final_page0_*: [enriched fields with labels]
AcroForm enrichment successful
```

## Example Usage

### Basic Debug Output

```bash
# Terminal 1: Start API with debug enabled
export DEBUG=true
export LOG_LEVEL=DEBUG
python -m uvicorn app.main:app --reload
```

You'll see:
```
DEBUG mode enabled - detailed output will be generated
```

### Analyze a PDF

```bash
# Terminal 2: Send a request
curl -X POST http://localhost:8000/analyze \
  -F "file=@form.pdf" \
  -F "strategy=auto" \
  | jq '.schema_json.fields | length'
```

### View Debug Output

In Terminal 1, you'll see debug logs like:

```
DEBUG - Pipeline start: strategy=auto, pdf_size=245789 bytes
DEBUG - AcroForm Check: pdf_size=245789, pages=3, has_acroform=true, field_count=15
DEBUG - AcroForm extracted template: {...}
DEBUG - Attempting to enrich AcroForm fields...
DEBUG - LLM Classification result: is_form=true, page_index=0
DEBUG - Final template: {...}
```

## Parsing Debug Output

The debug messages include JSON data. You can pipe to `jq` or other tools to parse:

```bash
# Capture logs to file
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app &> debug.log

# Search for specific patterns
grep "fields_count" debug.log
grep "LLM Classification" debug.log
grep "error\|Error\|ERROR" debug.log

# Extract JSON parts (if logging full JSON)
grep "Final template" debug.log | sed 's/.*Final template: //'
```

## Common Debug Scenarios

### Check if PDF has AcroForm fields

Look for these debug messages:

```
AcroForm Check: ... has_acroform=true, field_count=15
AcroForm extracted template: {...}
```

If `has_acroform=false`, the pipeline continues to vision extraction.

### Check visual structure detection

Look for:

```
Visual structure analysis: anchors=24
LLM Classification result: is_form=true
```

If `anchors < 15` or `is_form=false`, extraction is rejected.

### Check field extraction details

Look for per-page extraction:

```
HybridStrategy: Processing page 0
hybrid_page_0_extracted: 12 fields from page 0
hybrid_page_0: Snapped X fields to anchors
```

Or for vision low-res:

```
VisionLowResStrategy: Processing page 0
vision_lowres_page_0_response: [LLM response]
VisionLowResStrategy: Extracted 12 fields from page 0
```

### Check LLM requests and responses

Look for:

```
LLM request start: attempt=1, model=gpt-4o
LLM request success: attempt=1, status=200, duration=2.456s
llm_request_payload: [request data]
llm_response_1: [response data]
```

Check for retries:

```
LLM request failed on attempt 1: timeout
llm_error_attempt_1: [error details]
LLM request start: attempt=2, model=gpt-4o
LLM request success: attempt=2, status=200, duration=3.123s
```

### Troubleshoot field positions

Look for snapping information:

```
hybrid_strategy_snap_results: total_snapped=10, snaps=[
  {field_id: "field_1", old_position: {x: 50, y: 100}, new_position: {x: 52, y: 102}, snap_distance: 2.8}
]
```

## Performance Monitoring

Check timing in the logs:

```bash
# Get request timing
grep "Analyze completed" debug.log

# Get LLM timing
grep "LLM request success" debug.log | awk '{print $NF}'

# Get overall pipeline timing from start to finish
grep "Pipeline start\|Final template" debug.log
```

## Filtering Debug Output

Since debug logs are verbose, you can filter by module:

```bash
# Only pipeline logs
grep "pipeline" debug.log | grep DEBUG

# Only LLM logs
grep "llm\|LLM" debug.log | grep DEBUG

# Only strategy logs
grep "Strategy\|strategy" debug.log | grep DEBUG
```

## Log Levels

| Level | Description | Usage |
|-------|-------------|-------|
| INFO | Normal operation flow | Default for analysis operations |
| DEBUG | Detailed debug information | Set `LOG_LEVEL=DEBUG` for this |
| WARNING | Potentially problematic situations | Non-critical errors |
| ERROR | Serious problems | Critical failures with stack traces |

## Environment Variables

```bash
# Enable debug output
DEBUG=true

# Set log level (default: INFO)
LOG_LEVEL=DEBUG

# Combine for full debug output
DEBUG=true LOG_LEVEL=DEBUG
```

## Output Control

The logging output goes to:
- **Console (stdout/stderr)** - By default, via `logging.basicConfig()`
- **Both console and file** - If configured with additional handlers

To capture to a file:

```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | tee analysis.log
```

## Redirecting Output

Separate logs by type:

```bash
# Save only DEBUG messages
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep DEBUG > debug.log

# Save only errors
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep ERROR > errors.log

# Save everything
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app > full.log 2>&1
```

## Integration with Tests

For testing, enable debug mode and capture output:

```python
import os
import logging

os.environ["DEBUG"] = "true"
os.environ["LOG_LEVEL"] = "DEBUG"

# Configure logging to capture
logging.basicConfig(level=logging.DEBUG)

# Your test code here
result = await analyze_pdf(pdf_bytes, strategy="auto")
```

## Troubleshooting

### No debug output appears

1. Check `DEBUG=true` is set:
   ```bash
   echo $DEBUG
   ```

2. Check `LOG_LEVEL=DEBUG` is set:
   ```bash
   echo $LOG_LEVEL
   ```

3. Restart the API after setting environment variables:
   ```bash
   DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app --reload
   ```

### Too much output

Filter to specific components:

```bash
# Only show errors and above
LOG_LEVEL=ERROR python -m uvicorn app.main:app

# Only show warnings and above
LOG_LEVEL=WARNING python -m uvicorn app.main:app

# Only show info (default)
LOG_LEVEL=INFO python -m uvicorn app.main:app
```

### Logs are truncated

Some JSON in debug logs may be very long. Use tools to parse:

```bash
# Extract just field counts
grep -o "fields_count=[0-9]*" debug.log

# Extract error messages
grep "error\|Error\|ERROR" debug.log | cut -d':' -f3-
```

## Next Steps

1. **Enable debug mode**: `export DEBUG=true LOG_LEVEL=DEBUG`
2. **Run your analysis**: Upload a PDF to `/analyze`
3. **Monitor console output**: Watch for debug messages
4. **Analyze results**: Review the logs and template output
5. **Refine prompts**: Based on LLM behavior visible in logs
