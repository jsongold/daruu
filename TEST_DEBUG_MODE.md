# Testing Debug Mode

This guide shows how to test the debug mode functionality.

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
# Using curl with a sample PDF
curl -X POST http://localhost:8000/analyze \
  -F "file=@path/to/form.pdf" \
  -F "strategy=auto" \
  | jq '.'
```

Or with Python:
```python
import requests

with open('form.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/analyze',
        files={'file': f},
        data={'strategy': 'auto'}
    )

print(response.json()['debug_info'])
```

### 4. Check Debug Files
```bash
# List all created files
ls -lht /tmp/*.json | head -20

# View the final template
jq . /tmp/06_final_template.json

# View extracted fields
jq '.fields[] | {id, label, placement}' /tmp/06_final_template.json

# View LLM request
cat /tmp/llm_request_payload.json | jq .

# View LLM response
cat /tmp/llm_response_1.json | jq '.response | fromjson'
```

## Comprehensive Test Checklist

### Pipeline Execution
- [ ] Check `00_pipeline_start.json` exists with correct strategy
- [ ] Verify correct pipeline stage files based on strategy
- [ ] Confirm `06_final_template.json` is created
- [ ] Check all files are valid JSON

### AcroForm Processing (if applicable)
- [ ] `01_acroform_check.json` shows PDF structure
- [ ] `02_acroform_extracted_template.json` contains field data
- [ ] Field count matches PDF form fields

### Visual Structure
- [ ] `03_visual_structure_analysis.json` contains visual anchors
- [ ] Anchor count is greater than minimum threshold

### Classification
- [ ] `04_classification_result.json` shows form decision
- [ ] Classification matches expected result

### Vision Extraction
- [ ] `hybrid_page_*_extraction.json` or `vision_lowres_page_*_response.json` present
- [ ] LLM responses contain valid JSON
- [ ] Field count in final template is reasonable

### LLM Communication
- [ ] `llm_request_payload.json` contains prompt and metadata
- [ ] `llm_response_*.json` contains LLM response
- [ ] Response includes duration timing
- [ ] No `llm_error_*.json` files (unless retries expected)

### Final Output
- [ ] `06_final_template.json` is complete template
- [ ] Fields have correct structure
- [ ] Field placements have valid coordinates
- [ ] API response includes `debug_info`

## Test with Different Strategies

### Test AcroForm Strategy
```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@form_with_acroform.pdf" \
  -F "strategy=acroform_only"
```

Expected files:
- `01_acroform_check.json`
- `02_acroform_extracted_template.json`
- `06_enrichment_complete.json` (or error)
- `06_final_template.json`

### Test Vision Strategy
```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@scanned_form.pdf" \
  -F "strategy=vision_only"
```

Expected files:
- `05_vision_extraction_start.json`
- `hybrid_strategy_*.json` files
- `06_final_template.json`

### Test Auto Strategy
```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@any_form.pdf" \
  -F "strategy=auto"
```

Expected files:
- `00_pipeline_start.json`
- Files from whichever stage succeeds first
- `06_final_template.json`

## Debug File Content Verification

### Verify AcroForm Check
```bash
python3 << 'EOF'
import json

with open('/tmp/01_acroform_check.json') as f:
    data = json.load(f)

print(f"Step: {data['step']}")
print(f"PDF Size: {data['pdf_size_bytes']} bytes")
print(f"Pages: {data['num_pages']}")
print(f"Has AcroForm: {data['has_acroform']}")
print(f"Field Count: {data['raw_fields_count']}")
if data['field_names']:
    print(f"Fields: {', '.join(data['field_names'][:5])}...")
EOF
```

### Verify Extracted Fields
```bash
python3 << 'EOF'
import json

with open('/tmp/06_final_template.json') as f:
    template = json.load(f)

print(f"Template: {template['name']}")
print(f"Version: {template['version']}")
print(f"Total Fields: {len(template['fields'])}")
print("\nFirst 5 fields:")
for field in template['fields'][:5]:
    p = field['placement']
    print(f"  {field['label']:30} @ ({p['x']:6.1f}, {p['y']:6.1f})")
EOF
```

### Verify LLM Communication
```bash
python3 << 'EOF'
import json

# Check request
with open('/tmp/llm_request_payload.json') as f:
    request = json.load(f)
    print(f"LLM Request:")
    print(f"  Model: {request['model']}")
    print(f"  Detail: {request['detail']}")
    print(f"  Images: {request['images_count']}")
    print(f"  Prompt length: {request['prompt_length']}")
    print(f"  Prompt preview: {request['prompt'][:100]}...")

# Check response
with open('/tmp/llm_response_1.json') as f:
    response = json.load(f)
    print(f"\nLLM Response:")
    print(f"  Status: {response['status']}")
    print(f"  Duration: {response['duration']:.2f}s")
    print(f"  Response length: {response['response_length']}")
    print(f"  Response preview: {response['response'][:100]}...")
EOF
```

## Performance Testing

### Measure Total Time
```bash
python3 << 'EOF'
import json
from datetime import datetime
import time

# Get start time
with open('/tmp/00_pipeline_start.json') as f:
    start = datetime.fromisoformat(json.load(f)['timestamp'])

# Get end time (approximate from file creation)
with open('/tmp/06_final_template.json') as f:
    data = json.load(f)

start_ts = start.timestamp()
import os
end_ts = os.path.getmtime('/tmp/06_final_template.json')

duration = end_ts - start_ts
print(f"Total analysis time: {duration:.2f}s")
EOF
```

### Measure LLM Time
```bash
python3 << 'EOF'
import json
import glob

total_llm_time = 0
responses = glob.glob('/tmp/llm_response_*.json')

for resp_file in sorted(responses):
    with open(resp_file) as f:
        data = json.load(f)
        duration = data['duration']
        total_llm_time += duration
        print(f"{resp_file}: {duration:.2f}s")

print(f"\nTotal LLM time: {total_llm_time:.2f}s")
EOF
```

## Cleanup

After testing, clean up debug files:
```bash
# Remove all debug files
rm -f /tmp/*.json
rm -f /tmp/*acroform*
rm -f /tmp/*hybrid*
rm -f /tmp/*vision*

# Verify cleanup
ls /tmp/*.json 2>/dev/null | wc -l  # Should be 0
```

## Automation Test

Create a test script to verify debug mode:

```python
#!/usr/bin/env python3
"""Test debug mode functionality."""

import os
import json
import asyncio
from pathlib import Path
from app.services.analysis.pipeline import analyze_pdf

# Enable debug mode
os.environ['DEBUG'] = 'true'

async def test_debug_mode():
    """Test that debug files are created."""

    # Read a test PDF
    pdf_path = Path('test.pdf')  # Replace with actual test PDF
    if not pdf_path.exists():
        print("Error: test.pdf not found")
        return False

    pdf_bytes = pdf_path.read_bytes()

    # Analyze
    print("Running analysis with DEBUG=true...")
    result = await analyze_pdf(pdf_bytes, strategy='auto')

    # Check debug files
    debug_files = list(Path('/tmp').glob('*.json'))

    if not debug_files:
        print("ERROR: No debug files created!")
        return False

    print(f"✓ Created {len(debug_files)} debug files")

    # Check critical files
    critical_files = [
        '/tmp/00_pipeline_start.json',
        '/tmp/06_final_template.json'
    ]

    for filename in critical_files:
        if Path(filename).exists():
            with open(filename) as f:
                data = json.load(f)
            print(f"✓ {filename} - valid JSON")
        else:
            print(f"✗ {filename} - missing!")
            return False

    # Verify template
    if result.get('fields'):
        print(f"✓ Extracted {len(result['fields'])} fields")
    else:
        print("⚠ No fields extracted (may be expected)")

    print("\nAll tests passed!")
    return True

if __name__ == '__main__':
    success = asyncio.run(test_debug_mode())
    exit(0 if success else 1)
```

Run the test:
```bash
DEBUG=true python test_debug_mode.py
```

## Troubleshooting Tests

### Debug files not created
```bash
# Check DEBUG is set
echo $DEBUG  # Should be: true

# Check /tmp is writable
touch /tmp/test.json && rm /tmp/test.json

# Check logs for errors
grep -i error /tmp/*.json
```

### Invalid JSON files
```bash
# Validate JSON
python3 -c "import json; json.load(open('/tmp/06_final_template.json'))"

# Check file is not empty
wc -c /tmp/*.json | grep -v " 0 "
```

### Missing expected files
```bash
# List actual files
ls -1 /tmp/*.json | wc -l

# Check which stage failed
ls /tmp/0*.json /tmp/1*.json /tmp/2*.json 2>/dev/null | tail -1
```

## Success Criteria

A successful debug mode test should:

1. ✓ Create debug files in `/tmp` when `DEBUG=true`
2. ✓ All files are valid JSON
3. ✓ Sequential numbering matches pipeline stages
4. ✓ Final template is complete and valid
5. ✓ LLM interaction files contain expected data
6. ✓ No debug files when `DEBUG=false`
7. ✓ No performance regression when `DEBUG=false`
