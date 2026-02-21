# Pipeline Architecture

## Overview

`pipeline.py` implements a **functional pipeline** for PDF form field extraction using pure functions.

## Pipeline Flow

```
PDF bytes
  ↓
Step 1: check_acroform()
  ├─ Has AcroForm? → Extract fields → DONE ✅
  └─ No AcroForm → Continue
  ↓
Step 2: check_visual_structure()
  ├─ Has lines/boxes? → Continue
  └─ Plain text → REJECT ❌
  ↓
Step 3: classify_with_llm()
  ├─ LLM says "form"? → Continue
  └─ LLM says "not form" → REJECT ❌
  ↓
Step 4: extract_fields_vision()
  └─ Extract with LLM vision → DONE ✅
```

## Design Principles

1. **Functional** - No classes, just pure functions
2. **Independent** - Minimal dependencies on services
3. **Readable** - Each step is explicit and traceable
4. **Composable** - Easy to add/remove/reorder steps

## Usage

### Basic Usage

```python
from app.services.analysis.pipeline import analyze_pdf

with open("form.pdf", "rb") as f:
    pdf_bytes = f.read()

template = analyze_pdf(pdf_bytes, strategy="auto")
print(f"Found {len(template['fields'])} fields")
```

### Strategies

```python
# Full pipeline (recommended)
template = analyze_pdf(pdf_bytes, strategy="auto")

# Only try AcroForm extraction
template = analyze_pdf(pdf_bytes, strategy="acroform_only")

# Skip AcroForm, use vision only
template = analyze_pdf(pdf_bytes, strategy="vision_only")

# Use low-res vision (faster, less accurate)
template = analyze_pdf(pdf_bytes, strategy="vision_low_res")
```

### Command Line

```bash
cd apps/api
python example_pipeline.py path/to/form.pdf auto
```

## Step Details

### Step 1: `check_acroform(pdf_bytes)`

**Purpose**: Extract fields from PDF AcroForm (interactive form fields)

**Returns**:
- ✅ Success + template if AcroForm found (stops pipeline)
- ❌ Continue if no AcroForm

**Advantages**:
- Fastest (no LLM calls)
- Most accurate (exact field positions)
- Free (no API cost)

**Example**: Japanese government forms (like 2026bun_01_input.pdf)

---

### Step 2: `check_visual_structure(pdf_bytes)`

**Purpose**: Detect if PDF has visual form elements (lines, boxes, grids)

**Returns**:
- ✅ Continue if has visual structure
- ❌ Reject if no visual structure (plain text document)

**Threshold**: 15 visual anchors minimum

**Example**: 
- Form with grid: 50+ anchors → Continue ✅
- Plain text doc: 5 anchors → Reject ❌

---

### Step 3: `classify_with_llm(pdf_bytes)`

**Purpose**: Use LLM to determine if document is a form

**Returns**:
- ✅ Continue if LLM says "form"
- ❌ Reject if LLM says "not form"

**Use Case**: PDFs with complex layouts (tables, diagrams) that aren't forms

**Example**:
- Research paper with tables: Has visual structure but LLM rejects ✅
- Form with minimal structure: LLM accepts ✅

---

### Step 4: `extract_fields_vision(pdf_bytes)`

**Purpose**: Extract field positions using LLM vision analysis

**Returns**:
- ✅ Template with extracted fields (always succeeds)

**Strategies**:
- `hybrid`: High-res images + text blocks (more accurate, slower)
- `vision_low_res`: Low-res images only (faster, less accurate)

---

## Adding New Steps

To add a new pipeline step:

```python
def my_custom_step(pdf_bytes: bytes) -> PipelineResult:
    """Step description."""
    
    # Your logic here
    if should_stop:
        return PipelineResult(
            success=True,
            template=my_template,
            reason="Found what we need",
            should_continue=False  # Stop pipeline
        )
    
    # Continue to next step
    return PipelineResult(
        success=False,
        reason="Need more analysis",
        should_continue=True
    )
```

Then add to `analyze_pdf()`:

```python
steps = [
    ("AcroForm", check_acroform),
    ("My Custom Step", my_custom_step),  # ← Add here
    ("Visual Check", check_visual_structure),
    # ...
]
```

## Performance

**Test: 2026bun_01_input.pdf (Japanese form, 2 pages)**

| Strategy | Steps Run | Time | Fields | Cost |
|----------|-----------|------|--------|------|
| auto | 1/4 (AcroForm only) | <1s | 193 | $0 |
| vision_only | 1/1 (Vision) | ~20s | 14 | ~$0.05 |

**Recommendation**: Always use `auto` strategy for best results.

## Testing

```bash
# Test different PDFs
python example_pipeline.py form_with_acroform.pdf auto
python example_pipeline.py scanned_form.pdf vision_only
python example_pipeline.py plain_text.pdf auto  # Should reject
```

## Integration

To use in the API:

```python
# In app/routes/analyze.py
from app.services.analysis.pipeline import analyze_pdf

@router.post("/analyze")
async def analyze(file: UploadFile):
    pdf_bytes = await file.read()
    template = analyze_pdf(pdf_bytes, strategy="auto")
    return {"schema_json": template}
```
