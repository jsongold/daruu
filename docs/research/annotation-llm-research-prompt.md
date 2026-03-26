# Research: How to Make LLM Smarter with Annotation Pair Data

## Our System

PDF form autofill tool. User uploads a Japanese form (e.g. 年末調整),
system identifies form fields and fills them from data sources.

### Core Problem
AcroForm field IDs are meaningless (Text1, Text2, Text3...).
The system must figure out what each field represents by analyzing
nearby text on the PDF. This "FIELD_IDENTIFICATION" step currently
takes 70+ seconds for a 189-field form.

### Annotation Pair Data Structure

Each pair maps a visible text label to a form field:

```json
{
  "label": { "id": "...", "text": "氏名", "bbox": {"x":0.12, "y":0.08, "w":0.05, "h":0.02}, "page": 1 },
  "field": { "id": "Text3", "fieldName": "Text3", "bbox": {"x":0.25, "y":0.08, "w":0.15, "h":0.02}, "page": 1 },
  "confidence": 81,
  "status": "confirmed",
  "isManual": true
}
```

- Bbox: normalized 0-1 coordinates
- Typical form: ~770 text labels, ~190 fields
- isManual=true: human-verified, isManual=false: AI-generated
- Stored in Supabase per document

### Current AI Pairing (Baseline)
Simple spatial heuristic (no LLM):
- Euclidean distance between label end and field start
- Penalty for fields left of label
- Confidence = 100 - (distance * 200), clamped 30-99
- ~30% accuracy on complex forms

### Current LLM Pipeline
1. DirectionalFieldEnricher: finds text blocks near each field (up/down/left/right)
2. FillPlanner: sends field list + nearby_labels to LLM
3. LLM maps fields to data source keys semantically
4. Bottleneck: step 2 takes 70+ seconds

### Two Competing Design Approaches
A) "Prompt Specialization": Generate a form-specific system prompt once
   (10-30s async), reuse for fast fills (3-5s)
B) "Multi-Level Resolution": Level 1 (Python heuristics) -> Level 2
   (Vision LLM per page) -> Diff correction

## Research Questions

1. **Template learning from annotations**: When we accumulate many
   annotated instances of the same form template (same PDF layout),
   how to cache and reuse the field identification?
   - Hash form structure -> lookup known field mappings
   - How many annotated examples needed per template?

2. **Few-shot prompting with annotation pairs**: How to use manual
   pairs as in-context examples for LLM-based field identification?
   - Best format for encoding spatial + text info in prompts
   - How many examples improve accuracy vs token cost

3. **Layout-aware models vs VLM prompting**:
   - LayoutLMv3, DocFormer, Donut, Pix2Struct
   - Fine-tuning cost vs just prompting Claude/GPT-4V with bbox info
   - Which approach for Japanese government forms?

4. **Active learning loop**:
   - AI proposes pairings (isManual=false)
   - Human corrects (isManual=true)
   - How to feed corrections back to improve future predictions
   - Online learning vs periodic retraining

5. **Spatial encoding for LLMs**: Best encoding of bbox in text prompts
   - Coordinates vs relative position ("field is right-of label")
   - JSON vs markdown table vs natural language

6. **RAG with document structure**: Retrieve similar annotated docs
   to provide context for new document annotation

7. **Confidence calibration**: Better than distance-based heuristics
   - Learned confidence from manual pair corrections
   - Calibration curves from isManual data

8. **Speed optimization**: How annotation data can reduce the 70s
   FIELD_IDENTIFICATION bottleneck
   - Pre-computed field maps for known templates
   - Incremental identification (show partial results)

9. **Japanese document specifics**: Form understanding for
   - Vertical text, mixed kanji/kana
   - Government form layouts (standardized)
   - Dense label-field relationships

## Current System Prompts

### FIELD_IDENTIFICATION (the 70s bottleneck)

```
You are a PDF form field identification assistant.
Your task is to identify the semantic label for each form field based on its position
relative to nearby text blocks on the PDF page.

You will receive:
1. A list of form fields (compact JSON)
2. A list of text blocks extracted from the PDF (compact JSON)

Field keys: id=field_id, l=label (only present when different from id), t=type, p=page, b=[x,y,w,h]
Text block keys: s=text, p=page, b=[x,y,w,h]

For each field, determine which text block is most likely its label by analyzing:
- Proximity: Labels are usually directly left of, above, or very close to their field
- Semantic relevance: The text should describe what the field expects
- Page context: Only consider text on the same page as the field

Return JSON:
{
  "field_labels": [
    { "field_id": "Text1", "identified_label": "法人名", "confidence": 0.9,
      "reasoning": "Text '法人名' is 5pt left of the field on page 1" }
  ]
}
```

User prompt sends: all fields as compact JSON + all text blocks as compact JSON.
For 189 fields + 770 text blocks, this is a huge prompt -> slow.

### AUTOFILL (after fields are identified)

```
You are a form-filling assistant. Your task is to extract information from
provided data sources and match it to form fields.

Each field may include a `nearby_labels` array — text found near the field on
the PDF page. When field_id is generic (e.g. Text1), use nearby_labels to
understand the field's semantic purpose.

Return JSON:
{
  "filled_fields": [
    {"field_id": "...", "value": "...", "confidence": 0.95, "source": "..."}
  ],
  "warnings": [...]
}
```

User prompt sends: fields JSON + data sources text + rules.

## Desired Output

For each technique:
- Name + 1-paragraph description
- Key papers/tools (with years)
- Implementation complexity (low/medium/high)
- Expected improvement over spatial heuristic baseline
- Data requirements (annotated pairs/documents needed)
- Fine-tuning required or prompting-only
- Impact on the 70s bottleneck
