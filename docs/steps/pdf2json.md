For “PDF → JSON” where the **document format varies**, the best-performing approach in production is **not** “LLM finds everything end-to-end.” It is:

**(1) Deterministic field-region detection (boxes/lines/checkboxes)
→ (2) LLM only for semantics (labeling + typing)
→ (3) Human adjustment UI (optional)
→ (4) Deterministic replay**

This matches your operating principle and is the most reliable way to generalize across arbitrary layouts.

---

## 0) Always start by checking if the PDF already contains form fields

Many PDFs are **fillable** and already have an AcroForm structure.

### If AcroForm exists (best case)

* Extract fields via `pypdf` (or similar):

  * field name
  * type (text/checkbox/radio)
  * rect coordinates (in PDF points)
* This is near-perfect accuracy and requires no vision.

If **no form objects exist**, proceed to “scanned / flattened PDF” path below.

---

## 1) Best general strategy for arbitrary formats (flattened PDFs)

### Recommended pipeline (high accuracy)

**A. Render each page to a high-resolution PNG**

* Width: **2000–3000 px**
* PNG, no resizing after render
* One page per request / processing unit

**B. Detect “writable regions” using deterministic vision (no LLM yet)**
Detect:

* text-entry boxes (rectangles)
* underlines (for handwriting)
* checkboxes (small squares)
* date digit boxes
* table cells likely used for input

**C. Use OCR to get nearby printed text**

* OCR provides the candidate labels around each detected box.

**D. Use an LLM to “bind” labels to boxes + classify types**
The LLM does *association* and *typing*, not raw detection:

* “This box corresponds to label X”
* “This is checkbox / date / number / multi-line”
* “This is a table: expand row-by-row”

This division of labor is what makes the system robust across formats.

---

## 2) How to detect input boxes reliably (without training a new model)

You have three practical options; in production you often combine them.

### Option 1 (strong baseline): Classical CV + morphology (OpenCV)

Works surprisingly well for Japanese forms because they rely on strong lines and boxes.

* Convert to grayscale
* Adaptive threshold
* Morphological operations to isolate horizontal/vertical lines
* Find rectangles / contours
* Filter by:

  * aspect ratio
  * area
  * border thickness
  * “empty interior” ratio

Pros:

* Deterministic, fast, cheap
* Easy to debug
* Good on crisp PDFs

Cons:

* Struggles if scans are noisy, skewed, low contrast

### Option 2: Layout models (best robustness)

Use a pretrained document layout detector for:

* tables
* form fields
* key-value regions
* checkboxes

Pros:

* Much better on messy scans
* Better generalization

Cons:

* Adds model dependency; needs GPU for speed (sometimes)

### Option 3: Vision LLM detects boxes directly (simple, but least stable)

Send the page image and ask the LLM to output all boxes + labels.

Pros:

* Minimal engineering

Cons:

* Most sensitive to resolution and prompt
* Higher hallucination risk
* Harder to guarantee recall

**Best practice:** Use LLM detection only as a fallback, not your primary extractor.

---

## 3) The “best” architecture for variable formats (what I recommend you build)

### Two-stage extraction (most reliable)

#### Stage 1: Field candidates (deterministic)

Output only geometry + primitive type guess:

```json
[
  {"id":"f1","page":0,"x":123,"y":456,"w":210,"h":28,"kind":"box"},
  {"id":"f2","page":0,"x":380,"y":455,"w":22,"h":22,"kind":"checkbox"},
  {"id":"f3","page":0,"x":100,"y":620,"w":300,"h":4,"kind":"underline"}
]
```

#### Stage 2: Semantics binding (LLM + OCR text)

Provide:

* the list of candidate boxes
* OCR text with bounding boxes
* instruction: “assign nearest correct label; no invention”

Output:

```json
[
  {"id":"f1","label":"氏名","type":"text"},
  {"id":"f2","label":"同意する","type":"checkbox"},
  {"id":"f3","label":"住所","type":"text"}
]
```

This dramatically reduces hallucination because the LLM is not “inventing geometry.”

---

## 4) Handling tables (the hardest part)

Tables need special handling because “cells” may be writable or not.

Practical approach:

1. Detect table region (layout model or line detection)
2. Extract grid lines → infer cells
3. Decide which cells are input:

   * empty cells
   * cells under headers like “氏名 / 金額 / 日付”
4. Use LLM to expand “row-by-row” only after you’ve identified the grid.

---

## 5) Critical implementation detail: map image coordinates back to PDF coordinates

Your UI and field detection are in **image pixels**, but PDF writing uses **PDF points**.

You need a stable transform per page:

* `pdf_w_pt`, `pdf_h_pt` from PDF page
* `img_w_px`, `img_h_px` from rendered image

Convert:

* `x_pt = x_px * (pdf_w_pt / img_w_px)`
* `y_pt = (img_h_px - (y_px + h_px)) * (pdf_h_pt / img_h_px)`
  (because PDF origin is typically bottom-left)

If this mapping is wrong, your “accuracy” will look terrible even if detection is correct.

---

## 6) Practical “best next step” for your app

If your current Vision-API accuracy is low, implement this order:

1. **AcroForm extraction first** (if present)
2. If not present:

   * render higher-res
   * run deterministic box detection
   * OCR for nearby labels
   * LLM only for label binding + typing
3. Add quality gates:

   * minimum field count thresholds
   * bounds checks
   * retry ladder (higher render scale / detail)

---

## If you paste one sample PDF (or your render output) I can be concrete

If you share:

* one page PNG you actually send to the API, and
* your current output JSON (even if wrong),

I will tell you exactly which extractor path is appropriate (AcroForm vs raster), and propose the detection filters/types you should implement first (checkbox/date/table/text) for maximum coverage.
