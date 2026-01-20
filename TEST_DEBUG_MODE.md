# Testing Debug Mode

This guide shows how to test and verify the debug mode functionality.

## Quick Test

### 1. Enable Debug Mode
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
```

### 2. Start the API
```bash
cd /Users/yasumasa_takemura/projects/daru-pdf/apps/api
python -m uvicorn app.main:app --reload
```

You should see in logs:
```
DEBUG mode enabled - detailed output will be generated
```

### 3. Analyze a PDF in Another Terminal
```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@path/to/form.pdf" \
  -F "strategy=auto" \
  | jq '.schema_json.fields | length'
```

### 4. Check Console Output

In Terminal 1, you should see debug messages:
```
DEBUG - Pipeline start: strategy=auto, pdf_size=245789 bytes
DEBUG - AcroForm Check: ...
DEBUG - Final template: ...
```

## Comprehensive Test Checklist

### Pipeline Execution
- [ ] See "Pipeline start" message with strategy
- [ ] Pipeline stages execute in correct order
- [ ] See "Final template" message with extracted data

### AcroForm Processing (if applicable)
- [ ] See "AcroForm Check" with detection results
- [ ] See "AcroForm extracted template" with field data
- [ ] Field count matches PDF form fields

### Visual Structure
- [ ] See "Visual structure analysis" with anchor count
- [ ] Anchor count is reasonable for the PDF

### Classification
- [ ] See "LLM Classification result" with form decision
- [ ] Classification matches expected result (true/false)

### Vision Extraction
- [ ] See "HybridStrategy: Processing page X" messages
- [ ] See extraction results for each page
- [ ] See "Extracted N fields" counts

### LLM Communication
- [ ] See "LLM request start" messages
- [ ] See "LLM request success" with timing
- [ ] Duration is reasonable (typically 1-5 seconds)
- [ ] No "LLM request failed" messages (unless retries expected)

### Final Output
- [ ] See "Final template" with complete structure
- [ ] Response contains extracted fields
- [ ] Field count is reasonable

## Test with Different Strategies

### Test AcroForm Strategy
```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@form_with_acroform.pdf" \
  -F "strategy=acroform_only"
```

Expected logs:
```
DEBUG - Pipeline start: strategy=acroform_only
DEBUG - AcroForm Check: ...
DEBUG - AcroForm extracted template: ...
```

### Test Vision Strategy
```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@scanned_form.pdf" \
  -F "strategy=vision_only"
```

Expected logs:
```
DEBUG - Pipeline start: strategy=vision_only
DEBUG - Vision extraction start: strategy=hybrid
DEBUG - HybridStrategy: Processing page 0
DEBUG - HybridStrategy: Analysis complete
```

### Test Auto Strategy (Full Pipeline)
```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@any_form.pdf" \
  -F "strategy=auto"
```

Expected logs:
```
DEBUG - Pipeline start: strategy=auto
DEBUG - AcroForm Check: ...
[Other stages...]
DEBUG - Final template: ...
```

## Analyzing Debug Output

### Extract Specific Information

**Field count:**
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep -oP 'fields_count=\K[0-9]+' | head -1
```

**Pages processed:**
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep -oP 'pages=\K[0-9]+'
```

**LLM timing:**
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep "duration" | head -5
```

**Errors:**
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep -i "error\|failed\|exception"
```

### Count Debug Messages

```bash
# Total debug messages
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep "DEBUG -" | wc -l

# By stage
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep "Pipeline\|AcroForm\|Visual\|Classification\|extraction" | wc -l
```

## Verify Field Extraction

### Check Extracted Fields

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@form.pdf" \
  | jq '.schema_json.fields[] | {id, label, placement: {x: .placement.x, y: .placement.y}}'
```

Expected output:
```json
{
  "id": "field_1",
  "label": "Full Name",
  "placement": {
    "x": 50.0,
    "y": 100.0
  }
}
```

## Test Enrichment (AcroForm)

If using AcroForm strategy, check enrichment logs:

```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep -i "enrich"
```

Should show:
```
DEBUG - Attempting to enrich AcroForm fields...
DEBUG - acroform_enrichment_input_page0_*: ...
DEBUG - acroform_enrichment_response_page0_*: ...
DEBUG - acroform_enrichment_final_page0_*: ...
DEBUG - AcroForm enrichment successful
```

## Test Error Handling

### Missing File
```bash
curl -X POST http://localhost:8000/analyze \
  -F "strategy=auto"
```

Should see error logs about missing file.

### Invalid PDF
```bash
echo "not a pdf" > fake.pdf
curl -X POST http://localhost:8000/analyze \
  -F "file=@fake.pdf" \
  -F "strategy=auto"
```

Should see debug logs about extraction failure.

## Performance Testing

### Measure Total Time

```bash
# Single request timing
time curl -X POST http://localhost:8000/analyze \
  -F "file=@form.pdf" \
  -F "strategy=auto" > /dev/null
```

Check "real" time in output.

### Compare Strategies

```bash
# Auto strategy
time curl -X POST http://localhost:8000/analyze \
  -F "file=@form.pdf" \
  -F "strategy=auto" > /dev/null

# Vision only
time curl -X POST http://localhost:8000/analyze \
  -F "file=@form.pdf" \
  -F "strategy=vision_only" > /dev/null

# AcroForm only
time curl -X POST http://localhost:8000/analyze \
  -F "file=@form.pdf" \
  -F "strategy=acroform_only" > /dev/null
```

Compare execution times.

## Automated Test Script

Create a test script:

```bash
#!/bin/bash

# colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

test_count=0
pass_count=0

run_test() {
    local name=$1
    local cmd=$2

    ((test_count++))
    echo -n "Test $test_count: $name ... "

    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        ((pass_count++))
    else
        echo -e "${RED}FAIL${NC}"
    fi
}

# Start API with debug
export DEBUG=true
export LOG_LEVEL=DEBUG

# Run tests
run_test "API health check" "curl http://localhost:8000/health"
run_test "Analyze with auto strategy" "curl -X POST http://localhost:8000/analyze -F 'file=@test.pdf' -F 'strategy=auto' | jq '.schema_json'"
run_test "Analyze with acroform strategy" "curl -X POST http://localhost:8000/analyze -F 'file=@test.pdf' -F 'strategy=acroform_only' | jq '.schema_json'"
run_test "Analyze with vision strategy" "curl -X POST http://localhost:8000/analyze -F 'file=@test.pdf' -F 'strategy=vision_only' | jq '.schema_json'"

echo ""
echo "Tests passed: $pass_count/$test_count"
```

## Python Test Script

```python
#!/usr/bin/env python3
"""Test debug mode functionality."""

import os
import asyncio
import json
from pathlib import Path

os.environ['DEBUG'] = 'true'
os.environ['LOG_LEVEL'] = 'DEBUG'

async def test_debug_mode():
    """Test that debug logging works."""

    from app.services.analysis.pipeline import analyze_pdf

    # Read test PDF
    pdf_path = Path('test.pdf')
    if not pdf_path.exists():
        print("Error: test.pdf not found")
        return False

    pdf_bytes = pdf_path.read_bytes()

    print("Running analysis with DEBUG=true...")
    print("=" * 60)

    result = await analyze_pdf(pdf_bytes, strategy='auto')

    print("=" * 60)
    print(f"\nAnalysis complete!")
    print(f"Template name: {result['name']}")
    print(f"Fields extracted: {len(result['fields'])}")

    if result['fields']:
        print(f"\nFirst field:")
        field = result['fields'][0]
        print(f"  ID: {field['id']}")
        print(f"  Label: {field['label']}")
        print(f"  Position: ({field['placement']['x']:.1f}, {field['placement']['y']:.1f})")

    return True

if __name__ == '__main__':
    success = asyncio.run(test_debug_mode())
    exit(0 if success else 1)
```

Run it:
```bash
DEBUG=true LOG_LEVEL=DEBUG python test_debug.py
```

## Monitoring Real-Time Output

### Watch logs as they happen
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app --reload | grep DEBUG
```

### In another terminal, make requests
```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@form.pdf" \
  | jq .
```

Watch the debug logs appear in real-time.

## Troubleshooting Tests

### No debug output?

1. Verify DEBUG is set:
   ```bash
   echo $DEBUG  # Should be: true
   ```

2. Verify LOG_LEVEL is set:
   ```bash
   echo $LOG_LEVEL  # Should be: DEBUG
   ```

3. Check logs are going to stdout:
   ```bash
   DEBUG=true LOG_LEVEL=DEBUG python -c "import logging; logging.debug('test')"
   ```

### Debug logs mixed with other output?

Filter to just DEBUG:
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn app.main:app 2>&1 | grep DEBUG
```

### JSON parsing errors?

Some debug messages contain JSON. Use tools to parse:
```bash
grep "Final template" debug.log | sed 's/.*Final template: //' | jq .
```

## Success Criteria

A successful debug mode test should:

1. ✓ Show debug messages in console when `DEBUG=true LOG_LEVEL=DEBUG`
2. ✓ Messages appear for each pipeline stage
3. ✓ LLM interactions are logged with timing
4. ✓ Final template is complete and valid
5. ✓ No debug output when `DEBUG=false` (default)
6. ✓ No performance regression in normal mode
7. ✓ All messages are readable and useful

## Next Steps

1. **Enable debug mode** on your test/dev environment
2. **Run sample PDFs** through the analysis pipeline
3. **Monitor console output** for debug messages
4. **Verify extraction quality** by reviewing logged data
5. **Optimize prompts** based on LLM behavior visible in logs
