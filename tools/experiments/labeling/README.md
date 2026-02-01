# Label Linking Test Tool

A standalone script for testing and tuning the label linking prompts used by the FieldLabellingAgent.

## Features

- **Load PDF data**: Extracts AcroForm fields (boxes) and text blocks (labels)
- **Run label linking**: Calls the FieldLabellingAgent with extracted data
- **Display results**: Shows linkages, confidence scores, and LLM rationale
- **Prompt variations**: Test different prompt versions
- **Compare prompts**: Run two prompt versions and compare results
- **Dry run mode**: Preview prompts without calling LLM

## Usage

From the repository root:

```bash
# Basic usage with a PDF
python tools/experiments/labeling/main.py --pdf /path/to/test.pdf

# Use alternative prompt version
python tools/experiments/labeling/main.py --pdf /path/to/test.pdf --prompt v2

# Compare two prompt versions
python tools/experiments/labeling/main.py --pdf /path/to/test.pdf --compare default v2

# Process specific page only
python tools/experiments/labeling/main.py --pdf /path/to/test.pdf --page 1

# Dry run (show prompts without calling LLM)
python tools/experiments/labeling/main.py --pdf /path/to/test.pdf --dry-run

# Verbose output with rationales
python tools/experiments/labeling/main.py --pdf /path/to/test.pdf --verbose

# Save results to JSON
python tools/experiments/labeling/main.py --pdf /path/to/test.pdf --output results.json

# List available prompt versions
python tools/experiments/labeling/main.py --list-prompts
```

## Prompt Versions

- **default**: Current production prompts from FieldLabellingAgent
- **v2**: Experimental prompts with enhanced Japanese support and stricter confidence thresholds

## Adding New Prompts

To add a new prompt version:

1. Create a new file in `prompts/` (e.g., `v3.py`)
2. Define `name`, `description`, `system_prompt`, and `user_prompt_template`
3. Add the version name to `get_available_prompts()` in `prompts/__init__.py`
4. Add the import case in `get_prompt_set()` in `prompts/__init__.py`

## Output Format

The script outputs:
- Summary of loaded data (boxes, labels, pages)
- Per-page linkage results
- Confidence scores with visual bars
- Field names and types
- LLM rationale for each linkage (with --verbose)
- List of unlinked boxes

JSON output includes:
- All linkage details
- Label and box bounding boxes
- Processing time per page
