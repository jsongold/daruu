# Debug Mode - Quick Start Guide

## Enable Debug Output

```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
```

Then run the API:
```bash
python -m uvicorn app.main:app --reload
```

Or in one command:
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app --reload
```

## What Happens

When you make an `/analyze` request with debug enabled:

1. **Console logs** show detailed information at each pipeline stage
2. **LLM interactions** are fully logged (requests, responses, timings)
3. **Field extraction** details are displayed for each page
4. **Errors and warnings** include full context

## Quick Example

### Terminal 1: Start API with Debug
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app --reload
```

You'll see:
```
DEBUG mode enabled - detailed output will be generated
```

### Terminal 2: Analyze a PDF
```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@form.pdf" \
  | jq '.schema_json | {name, fields_count: (.fields | length)}'
```

### Terminal 1: See Debug Output

```
DEBUG - Pipeline start: strategy=auto, pdf_size=245789 bytes
DEBUG - AcroForm Check: pdf_size=245789, pages=3, has_acroform=true, field_count=15
DEBUG - AcroForm extracted template: {...}
DEBUG - Attempting to enrich AcroForm fields...
DEBUG - LLM Classification result: is_form=true, page_index=0
DEBUG - Final template: {...}
```

## Key Debug Messages

| Message | Meaning |
|---------|---------|
| `AcroForm Check: ... has_acroform=true` | PDF has native form fields |
| `AcroForm Check: ... has_acroform=false` | No native fields, continuing to vision |
| `LLM Classification result: is_form=true` | Document classified as a form |
| `LLM Classification result: is_form=false` | Document rejected (not a form) |
| `HybridStrategy: Processing page X` | Extracting fields from page X |
| `Extracted N fields from page X` | N fields found on page X |
| `Snapped X fields to anchors` | X fields adjusted to visual structure |
| `LLM request success: ... duration=2.5s` | LLM request completed in 2.5 seconds |

## Filtering Output

### See only errors
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep -i error
```

### See only LLM interactions
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep -i "llm\|openai"
```

### See only field extraction
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep -i "extraction\|extracted\|fields"
```

### Save all output to file
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app > debug.log 2>&1
tail -f debug.log  # Watch in real-time
```

## Common Questions

### How do I see what LLM was sent?

Look for logs with `llm_request_payload`:
```bash
grep "llm_request_payload" debug.log
```

### How do I see what LLM returned?

Look for logs with `llm_response`:
```bash
grep "llm_response" debug.log
```

### How do I check if fields were snapped?

Look for logs with `snap`:
```bash
grep "Snapped\|snap_results" debug.log
```

### How long did the LLM call take?

Look for timing in LLM responses:
```bash
grep "LLM request success" debug.log
```

### How many fields were extracted?

Look for the final count:
```bash
grep "fields_count\|Extracted.*fields" debug.log
```

## Environment Setup

### Quick Test
```bash
# Start in one terminal
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app --reload

# In another terminal, test
curl -X POST http://localhost:8000/analyze \
  -F "file=@test.pdf" \
  | jq '.schema_json.fields | length'
```

### Save Logs
```bash
# Capture all output
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app &> full_debug.log &

# Make requests
curl -X POST http://localhost:8000/analyze -F "file=@test.pdf"

# View logs
cat full_debug.log | grep DEBUG
```

### With Docker
```bash
# If running in Docker
docker run -e DEBUG=true -e LOG_LEVEL=DEBUG my-app:latest
```

## Troubleshooting

### No debug output?

Check DEBUG is set:
```bash
DEBUG=true python -c "print('DEBUG is set')"
```

### Output is truncated?

The logs might be very long. Try filtering:
```bash
# Just show field counts
grep -o "fields_count=[0-9]*\|Extracted [0-9]*" debug.log

# Just show errors
grep "error\|Error\|ERROR" debug.log
```

### Too much output?

Reduce log level:
```bash
# Only info level
python -m uvicorn app.main:app --log-level info
```

## Log Levels

```bash
export LOG_LEVEL=DEBUG      # Most verbose (all debug messages)
export LOG_LEVEL=INFO       # Normal (default)
export LOG_LEVEL=WARNING    # Warnings and errors only
export LOG_LEVEL=ERROR      # Errors only
```

## Next Steps

1. **Enable**: `DEBUG=true LOG_LEVEL=DEBUG`
2. **Run**: `python -m uvicorn app.main:app --reload`
3. **Test**: `curl -X POST http://localhost:8000/analyze -F "file=@form.pdf"`
4. **Monitor**: Watch the debug output in console
5. **Analyze**: Review logs to understand extraction behavior

For detailed information, see [DEBUG_MODE.md](DEBUG_MODE.md)
