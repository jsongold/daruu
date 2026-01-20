# Testing PyMuPDF Extraction Results

This guide shows various methods to test and debug PyMuPDF extraction from `pdf_render.py`.

## Quick Start

### 1. Basic Inspection Tool

Use `test_pymupdf_extraction.py` to get a detailed text-based report:

```bash
cd apps/api
python test_pymupdf_extraction.py path/to/your.pdf
```

**Example output:**
```
📄 Total Pages: 1

PAGE 1
  Dimensions: 595.0 x 842.0 points
  Visual Anchors: 42
  Text Blocks: 15

📐 Visual Anchors (Lines/Rectangles):
  1. Type=rect     Pos=(50.0, 100.0) Size=200.0x30.0
  2. Type=stroke   Pos=(50.0, 135.0) Size=200.0x1.0
  ...

📝 Text Blocks:
  1. Pos=(55.0, 105.0) Text="Name:"
  2. Pos=(270.0, 105.0) Text="Date of Birth:"
  ...

💡 Classification Hint:
  ✓ First page has 42 anchors → Would trigger LLM classification
```

### 2. JSON Output

Get machine-readable JSON output:

```bash
python test_pymupdf_extraction.py path/to/your.pdf --json
```

### 3. Visual Debugging

Create an annotated image showing extracted elements:

```bash
python visualize_extraction.py path/to/your.pdf output.png
```

This creates an image with:
- **🔴 Red boxes** = Visual anchors (lines, rectangles)
- **🔵 Blue boxes** = Text blocks

---

## What Gets Extracted

### Visual Anchors (`page.visual_anchors`)

Extracted from `page.get_drawings()` - includes:
- **Lines** (horizontal/vertical dividers, underlines)
- **Rectangles** (input field borders, checkboxes)
- **Grid cells** (table borders)

Each anchor has:
```python
{
    "x0": float,  # Top-left X
    "y0": float,  # Top-left Y
    "x1": float,  # Bottom-right X
    "y1": float,  # Bottom-right Y
    "type": str   # "rect" or "stroke"
}
```

**Filtering rules** (in `pdf_render.py`):
- Filters out tiny elements (< 5pt width/height)
- Keeps thin horizontal lines (> 20pt wide, < 5pt tall)
- Keeps thin vertical lines (> 20pt tall, < 5pt wide)

### Text Blocks (`page.text_blocks`)

Extracted from `page.get_text("blocks")` - includes:
- All text content grouped by visual blocks
- Coordinates of each text region

Each block has:
```python
{
    "x0": float,
    "y0": float,
    "x1": float,
    "y1": float,
    "text": str
}
```

---

## Testing in Code

### Unit Test Example

```python
import pytest
from app.services.pdf_render import render_pdf_pages

def test_extraction_has_content():
    with open("path/to/form.pdf", "rb") as f:
        pdf_bytes = f.read()
    
    pages = render_pdf_pages(pdf_bytes, dpi=150)
    
    assert len(pages) > 0
    assert pages[0].visual_anchors is not None
    assert pages[0].text_blocks is not None
    assert len(pages[0].visual_anchors) >= 15  # Should trigger classification
```

### Integration Test Example

```python
def test_classification_pipeline():
    from app.services.analysis.strategies import DocumentClassifier
    
    with open("path/to/form.pdf", "rb") as f:
        pages = render_pdf_pages(f.read())
    
    classifier = DocumentClassifier()
    is_form = classifier.classify(pages[0])
    
    # Verify classification logic
    anchor_count = len(pages[0].visual_anchors or [])
    if anchor_count < 15:
        assert not is_form  # Should reject without LLM
    else:
        # LLM was called
        assert isinstance(is_form, bool)
```

---

## Common Issues

### No Visual Anchors Found

**Possible causes:**
1. PDF doesn't contain vector graphics (scanned images)
2. Forms use background images instead of vector lines
3. PyMuPDF version issue

**Debug:**
```bash
python -c "import fitz; print(fitz.__doc__)"  # Check version
python visualize_extraction.py your.pdf      # Visual inspection
```

### No Text Blocks

**Possible causes:**
1. PDF uses images of text (OCR needed)
2. Text is in non-standard encoding
3. Text extraction disabled

**Debug:**
```python
import fitz
doc = fitz.open("your.pdf")
page = doc[0]
print(page.get_text())  # Raw text extraction
```

---

## Tips for Testing Different PDF Types

### Forms with Grid Structure
- ✓ Should have **many** visual anchors (30-100+)
- ✓ Should have moderate text blocks (field labels)

### Text Documents
- ✗ Few visual anchors (0-20)
- ✓ Many text blocks

### Scanned PDFs
- ✗ Almost no visual anchors
- ✗ No text blocks (unless OCR applied)

---

## Sample Test Suite Files

The project has existing tests in `apps/api/tests/`:
- `test_analyze.py` - End-to-end API testing
- Use `assets/templates/sample-template.pdf` as test fixture

Add your own PDF fixtures to `apps/api/assets/` for testing different document types.
