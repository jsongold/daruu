# Debug Mode - Quick Start Guide

## Enable Debug Output

```bash
export DEBUG=true
```

Then run the API:
```bash
python -m uvicorn app.main:app --reload
```

Or in one command:
```bash
DEBUG=true python -m uvicorn app.main:app --reload
```

## What Happens

When you make an `/analyze` request with `DEBUG=true`:

1. **Console logs** become more detailed with timestamps
2. **JSON files** are created in `/tmp` showing:
   - Each pipeline stage execution
   - PDF structure (pages, AcroForm fields, visual anchors)
   - LLM prompts sent and responses received
   - Field extraction results from each stage
   - Final template with all extracted fields

3. **Response includes** `debug_info` with:
   - Strategy used
   - Filename and PDF size
   - Duration and fields extracted
   - Note about debug files location

## Finding Debug Files

All files go to `/tmp` (organized by pipeline stage):

```bash
# View all debug files
ls -la /tmp/*.json | head -20

# Watch files being created in real-time
watch 'ls -la /tmp/*.json | tail -20'

# Search for specific files
ls /tmp/*pipeline* /tmp/*extraction* /tmp/*llm*

# Clean up (optional)
rm -f /tmp/*.json
```

## Understanding the Files

Files are numbered by pipeline stage:

```
00_*.json      → Pipeline start
01_*.json      → AcroForm check
02_*.json      → AcroForm extraction/enrichment
03_*.json      → Visual structure detection
04_*.json      → LLM classification
05_*.json      → Vision field extraction
06_*.json      → Final results
llm_*.json     → LLM request/response details
hybrid_*.json  → HybridStrategy specific
vision_*.json  → VisionLowResStrategy specific
```

## Example Usage

```bash
# Start API with debug
DEBUG=true python -m uvicorn app.main:app --reload

# In another terminal, analyze a PDF
curl -X POST http://localhost:8000/analyze \
  -F "file=@form.pdf" \
  -F "strategy=auto" \
  | jq '.debug_info'

# View debug files
cat /tmp/06_final_template.json | jq '.fields[] | {id, label, placement}'

# View what LLM was asked
cat /tmp/llm_request_payload.json | jq '.prompt'

# View LLM response
cat /tmp/llm_response_1.json | jq '.response'
```

## Key Files to Check

| Want to know... | Check this file |
|-----------------|-----------------|
| Did extraction work? | `06_final_template.json` |
| What fields were found? | `hybrid_strategy_final_fields.json` or `vision_lowres_strategy_final.json` |
| What did LLM extract? | `hybrid_page_*_extraction.json` |
| Did LLM get retried? | `llm_error_attempt_*.json` (if exists) |
| How long did it take? | `llm_response_*.json` (check duration) |
| What was sent to LLM? | `llm_request_payload.json` |
| Were fields snapped? | `hybrid_strategy_snap_results.json` |
| Was it a form? | `04_classification_result.json` |

## Analyzing Field Extraction

Check final fields with proper coordinates:

```bash
# Pretty print final fields
python3 -c "
import json
with open('/tmp/06_final_template.json') as f:
    data = json.load(f)
    for field in data.get('fields', []):
        print(f\"{field['label']:30} @ ({field['placement']['x']:6.1f}, {field['placement']['y']:6.1f})\")
"
```

## Troubleshooting

### No debug files appear
```bash
# Check if DEBUG is set
echo $DEBUG

# Check if /tmp exists and is writable
touch /tmp/test.json
ls /tmp/test.json
rm /tmp/test.json
```

### Logs not showing timestamps
Set both `DEBUG` and `LOG_LEVEL`:
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app --reload
```

### Too many files in /tmp
Clean them up:
```bash
# Remove all debug files
rm -f /tmp/*acroform* /tmp/0* /tmp/1* /tmp/2* /tmp/3* /tmp/4* /tmp/5* /tmp/6* /tmp/llm* /tmp/hybrid* /tmp/vision*

# Or more aggressive
rm -f /tmp/*.json
```

## Full Documentation

See [DEBUG_MODE.md](DEBUG_MODE.md) for comprehensive documentation including:
- All possible debug files
- File content examples
- Advanced analysis techniques
- Performance profiling
- Integration with tests

## What Gets Logged

### Pipeline Execution
- Each step (AcroForm check → visual structure → classification → extraction)
- Success/failure of each step
- Reason for skipping steps

### Extracted Data
- Number of pages
- Number of visual anchors per page
- Text blocks detected
- Fields extracted per page
- Field positions and dimensions

### LLM Interactions
- Model, temperature, max tokens
- Request/response timestamps
- Response content and errors
- Retry attempts and reasons

### Processing Details
- Page-by-page extraction results
- Field snapping to visual anchors
- AcroForm enrichment with labels
- Final template structure

## Performance Monitoring

Check how fast extraction is:

```bash
# Extract timing info
python3 -c "
import json, time
from datetime import datetime

with open('/tmp/00_pipeline_start.json') as f:
    start = datetime.fromisoformat(json.load(f)['timestamp'])

with open('/tmp/06_final_template.json') as f:
    data = json.load(f)

print(f'Analysis took approximately {time.time() - start.timestamp():.2f}s')
"

# Check LLM speed
cat /tmp/llm_response_1.json | jq '.duration'
```

## Next Steps

1. **Enable debug mode**: `export DEBUG=true`
2. **Run your analysis**: Upload a PDF to `/analyze`
3. **Check debug files**: `ls -la /tmp/*.json`
4. **Review results**: View `06_final_template.json` for extracted fields
5. **Refine prompts**: Look at LLM interactions to improve extraction quality

For more details, see [DEBUG_MODE.md](DEBUG_MODE.md)
