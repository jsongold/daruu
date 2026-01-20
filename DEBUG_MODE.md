# Debug Mode Documentation

This document explains how to use the comprehensive debug mode in Daru PDF's analysis pipeline.

## Enabling Debug Mode

Set the `DEBUG` environment variable to `true` before starting the API:

```bash
DEBUG=true python -m uvicorn app.main:app --reload
```

Or with environment file:
```bash
export DEBUG=true
```

## What Gets Logged

When debug mode is enabled, the system outputs:

1. **Detailed Console Logs** - Enhanced logging with timestamps and full exception traces
2. **JSON Debug Files** - Detailed data at each pipeline stage written to `/tmp`
3. **LLM Interaction Data** - All prompts, responses, and errors from API calls
4. **Intermediate Data** - Extracted text, visual anchors, parsed results

## Debug Files Generated

All debug files are written to `/tmp` with numbered prefixes indicating pipeline stage:

### Pipeline Stage Files (Sequential Order)

| Stage | File Pattern | Content |
|-------|-------------|---------|
| 0. Start | `00_pipeline_start.json` | Strategy, PDF size, timestamp |
| 1. AcroForm Check | `01_acroform_check.json` | PDF pages, AcroForm detection results |
| 2. AcroForm Extract | `02_acroform_extracted_template.json` | Extracted AcroForm fields |
| 2. AcroForm Error | `02_acroform_error.json` | Extraction errors if any |
| 3. Visual Structure | `03_visual_structure_analysis.json` | Visual anchors found, page dimensions |
| 3. Classification | `04_classification_result.json` | Form/non-form classification result |
| 5. Vision Extraction Start | `05_vision_extraction_start.json` | Strategy, pages info |
| 5. Vision Extraction Complete | `05_vision_extraction_complete.json` | Final extracted fields |
| 6. Enrichment Complete | `06_enrichment_complete.json` | AcroForm enriched with labels |
| 6. Enrichment Error | `06_enrichment_error.json` | Enrichment errors if any |
| 6. Final Template | `06_final_template.json` | Final response template |

### Strategy-Specific Files

#### HybridStrategy
- `hybrid_strategy_start.json` - Analysis start with page info
- `hybrid_page_{N}_extraction.json` - LLM response for page N
- `hybrid_page_{N}_parsed_items.json` - Parsed field items from page N
- `hybrid_page_{N}_error.json` - Extraction errors for page N
- `hybrid_strategy_snap_results.json` - Field snapping to visual anchors
- `hybrid_strategy_final_fields.json` - All extracted fields with positions
- `hybrid_strategy_rejected.json` - Document rejected (non-form)

#### VisionLowResStrategy
- `vision_lowres_strategy_start.json` - Analysis start with page info
- `vision_lowres_page_{N}_response.json` - LLM response for page N
- `vision_lowres_page_{N}_parsed.json` - Parsed fields from page N
- `vision_lowres_page_{N}_error.json` - Extraction errors for page N
- `vision_lowres_page_{N}_parse_error.json` - JSON parsing errors
- `vision_lowres_strategy_final.json` - All extracted fields with positions

#### LLM Communication
- `llm_request_payload.json` - Request sent to OpenAI (prompt, images count, model)
- `llm_response_{N}.json` - Response from OpenAI on attempt N (status, duration, content)
- `llm_error_attempt_{N}.json` - Error details from attempt N
- `llm_classification_result.json` - Form classification LLM response
- `llm_classification_error.json` - Classification errors

#### AcroForm Enrichment
- `acroform_enrichment_input_page{N}_{timestamp}.json` - Input fields for enrichment
- `acroform_enrichment_response_page{N}_{timestamp}.json` - Raw LLM response
- `acroform_enrichment_final_page{N}_{timestamp}.json` - Enriched fields with labels

## Example File Contents

### 00_pipeline_start.json
```json
{
  "strategy": "auto",
  "pdf_size_bytes": 245789,
  "timestamp": "2025-01-20T10:30:45.123456"
}
```

### 01_acroform_check.json
```json
{
  "step": "AcroForm Check",
  "pdf_size_bytes": 245789,
  "num_pages": 3,
  "has_acroform": true,
  "raw_fields_count": 15,
  "field_names": ["field1", "field2", ...]
}
```

### 03_visual_structure_analysis.json
```json
{
  "step": "Visual Structure Check",
  "num_pages": 3,
  "first_page_analysis": {
    "page_index": 0,
    "width": 612.0,
    "height": 792.0,
    "visual_anchors_count": 24,
    "visual_anchors": [
      {
        "x0": 50.0,
        "y0": 100.0,
        "x1": 200.0,
        "y1": 120.0,
        "type": "rect"
      }
    ]
  }
}
```

### hybrid_page_0_extraction.json
```json
{
  "page_index": 0,
  "page_size": { "width": 612.0, "height": 792.0 },
  "llm_response": "[{\"label\": \"Name\", \"x\": 50, \"y\": 100, \"width\": 200, \"height\": 20, \"type\": \"text\"}, ...]"
}
```

### hybrid_strategy_final_fields.json
```json
{
  "total_fields": 15,
  "fields": [
    {
      "id": "field_1",
      "label": "Full Name",
      "placement": {
        "page_index": 0,
        "x": 50.0,
        "y": 100.0,
        "max_width": 200.0,
        "height": 20.0
      }
    }
  ]
}
```

### llm_request_payload.json
```json
{
  "model": "gpt-4o",
  "detail": "high",
  "images_count": 1,
  "prompt_length": 425,
  "prompt": "You are a form field extraction engine...",
  "pages_info": [
    {
      "index": 0,
      "width": 612.0,
      "height": 792.0
    }
  ]
}
```

### llm_response_1.json
```json
{
  "attempt": 1,
  "status": 200,
  "duration": 2.456,
  "response_length": 1245,
  "response": "[{\"label\": \"Name\", ...}]"
}
```

## Analyzing Results

### Check Pipeline Flow
1. Start with `00_pipeline_start.json` to see the strategy chosen
2. Look for `01_acroform_check.json`, `03_visual_structure_analysis.json`, `04_classification_result.json` in order
3. Find the extraction stage: `05_vision_extraction_*.json` or `02_acroform_*.json`
4. End with `06_final_template.json`

### Check Extracted Fields
- View `hybrid_strategy_final_fields.json` or `vision_lowres_strategy_final.json` for all fields
- For each field, check:
  - Label correctness
  - Position (x, y) accuracy
  - Width and height appropriateness

### Check LLM Quality
1. Review `llm_request_payload.json` - what was sent to the LLM
2. Review `llm_response_*.json` - what the LLM returned
3. Check duration - how long did the request take
4. Look for retries - were there multiple attempts?

### Check Field Snapping
- View `hybrid_strategy_snap_results.json` for fields adjusted to visual anchors
- See old vs new positions to validate snapping accuracy

### Check Enrichment (AcroForm)
1. `acroform_enrichment_input_page*.json` - original field positions
2. `acroform_enrichment_response_page*.json` - LLM's enrichment response
3. `acroform_enrichment_final_page*.json` - enriched fields with labels

## Response Format

The `/analyze` endpoint includes `debug_info` in the response when DEBUG=true:

```json
{
  "schema_json": { ... },
  "debug_info": {
    "enabled": true,
    "strategy": "auto",
    "filename": "form.pdf",
    "pdf_size_bytes": 245789,
    "duration_seconds": 15.34,
    "fields_extracted": 15,
    "note": "Check /tmp directory for detailed debug files",
    "debug_files_pattern": "*.json in /tmp"
  }
}
```

## Common Debug Scenarios

### No Fields Extracted
1. Check `01_acroform_check.json` - does PDF have AcroForm?
2. Check `03_visual_structure_analysis.json` - how many visual anchors?
3. Check `04_classification_result.json` - was it classified as a form?
4. Check `llm_response_*.json` - what did LLM extract?

### Incorrect Field Positions
1. Check `hybrid_page_*_extraction.json` - what LLM coordinates were
2. Check `hybrid_strategy_snap_results.json` - were fields snapped?
3. Check visual anchors vs extracted positions in debug files

### LLM Errors or Retries
1. Check `llm_error_attempt_*.json` for each failed attempt
2. Check `llm_response_*.json` to see which attempt succeeded
3. Look at duration to identify timeouts

### AcroForm Enrichment Issues
1. Check `acroform_enrichment_input_page*.json` - input fields
2. Check `acroform_enrichment_response_page*.json` - LLM's response
3. Check `06_enrichment_error.json` if enrichment failed

## Performance Analysis

Use the debug files to analyze performance:
- `00_pipeline_start.json` + `06_final_template.json` timestamps show total time
- `llm_response_*.json` shows LLM request duration
- Number of stages and retries impact overall speed

## Cleaning Up

Debug files accumulate in `/tmp`. Clean them up periodically:

```bash
# Remove all daru-pdf debug files
rm -f /tmp/*acroform*.json /tmp/0*.json /tmp/llm*.json /tmp/hybrid*.json /tmp/vision*.json

# Or remove all JSON files in /tmp (careful!)
rm -f /tmp/*.json
```

## Integration with Tests

For testing, enable debug mode and verify:
1. Expected number of files created
2. File contents match expected schema
3. Pipeline stages execute in correct order
4. LLM responses are valid JSON

Example test pattern:
```python
import os
import json
from pathlib import Path

os.environ["DEBUG"] = "true"
# ... run analysis ...
debug_files = list(Path("/tmp").glob("*.json"))
assert len(debug_files) > 0, "No debug files created"
```

## Environment Variables

- `DEBUG=true` - Enable debug mode (default: false)
- `LOG_LEVEL=DEBUG` - Enable verbose logging (default: INFO)
- `OPENAI_API_KEY` - Required for LLM analysis
- `OPENAI_MODEL` - LLM model (default: gpt-4o)

## Troubleshooting

**No debug files created:**
- Verify `DEBUG=true` is set before starting the API
- Check that `/tmp` is writable
- Check logs for "DEBUG mode enabled" message

**Files not appearing in /tmp:**
- On Windows, `/tmp` might be different (use `echo $TMPDIR`)
- Some container environments might have different temp paths
- Check file permissions on `/tmp`

**Too many files:**
- Debug mode creates one file per step
- Multiple pages create multiple extraction files
- Clean up periodically to avoid disk space issues
