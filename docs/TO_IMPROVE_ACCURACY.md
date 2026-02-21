# Improving Autofill Accuracy: What to Send to the LLM

## Problem

The "vision autofill" service sends **no images** and **minimal context**
to the LLM. The model receives a flat JSON list of field labels and a
flat text dump of key:value pairs. It has no visual understanding of
the form layout, no awareness of field groupings, and no language hints.
This causes unrelated fields to get swapped values.

## What the LLM Receives Today

```
messages = [
    { role: "system", content: generic English instructions },
    { role: "user",   content: fields_json + data_sources_text },
]
```

| Data | Format | Problem |
|------|--------|---------|
| Field list | `[{field_id, label, type, x, y, w, h, page}, ...]` | Raw numbers, no visual context |
| Source data | `"- Name: Tanaka\n- Phone: 03-xxxx"` | Flat key:value, no structure |
| Instructions | English-only, no examples | No language awareness |
| Images | **None** | "Vision" autofill with no vision |
| AcroForm names | **Not sent** | Internal IDs like `applicant_name` are discarded |
| Page structure | **Not sent** | Section headers, groupings are lost |
| User profile | **Not sent** | Known user data not leveraged |
| Template rules | **Not sent** | Per-form business rules not included |

---

## Target: What the LLM Should Receive

### 8 data layers, ordered by impact

---

### 1. Target Form Page Images (HIGH IMPACT)

**What:** Rendered PNG of each page of the target PDF at 150 DPI.

**Why:** The model can visually see which labels belong to which fields,
how fields are grouped into sections, and what the form layout looks
like. This is the single biggest accuracy improvement — a vision model
with the actual form image can resolve ambiguities that text alone cannot.

**How it changes the message:**

```
messages = [
    { role: "system", content: instructions },
    { role: "user", content: [
        { type: "image_url", image_url: { url: "data:image/png;base64,<page1>" }},
        { type: "image_url", image_url: { url: "data:image/png;base64,<page2>" }},
        { type: "text", text: "Fields: [...], Data: [...]" },
    ]},
]
```

**Cost consideration:** Each 150 DPI page image costs roughly 1,000-2,000
tokens. A 5-page form adds ~10,000 tokens (~$0.0015 on gpt-5-mini).
Acceptable for the accuracy gain.

**Data available from:** Page previews are already rendered by the system
(see `getPagePreviewUrl` in the frontend, `IngestConfig.default_dpi = 150`
in config).

---

### 2. Source Document Images (HIGH IMPACT)

**What:** Images of user-uploaded source documents — driver's licenses,
certificates, passport photos, scanned forms.

**Why:** The TextExtractionService does basic key:value parsing, but for
scanned images and photos it relies on OCR which can miss or garble
fields. Sending the original image lets the vision model read the
source directly.

**When to send:**
- Always for IMAGE sources (photos, scans)
- For PDF sources, send if the PDF is scanned (image-based) rather than
  digital-native
- Skip for CSV and plain TEXT sources (text is sufficient)

**Data available from:** Source documents are stored in Supabase storage.
The `DataSource` model has `file_path` pointing to the stored file.

---

### 3. Enriched Field Metadata (HIGH IMPACT)

**What:** Send more than just `label` for each field.

Current field data:
```json
{ "field_id": "field_3", "label": "氏名", "type": "text",
  "x": 150.0, "y": 200.0, "width": 300.0, "height": 25.0, "page": 1 }
```

Target field data:
```json
{
  "field_id": "field_3",
  "label": "氏名",
  "acroform_name": "applicant_full_name",
  "type": "text",
  "page": 1,
  "section": "Personal Information",
  "nearby_labels": ["フリガナ", "生年月日", "性別"],
  "position_description": "Top-left area of page 1"
}
```

**New fields to add:**

| Field | Source | Why |
|-------|--------|-----|
| `acroform_name` | AcroForm field dictionary | Often contains English hints even for JP forms |
| `section` | Extracted from page structure | Groups related fields (e.g., "Address Section") |
| `nearby_labels` | Spatial analysis of PDF text | Shows which other labels are close by |
| `position_description` | Derived from bbox | Human-readable position instead of raw coordinates |

**Note:** Drop raw `x, y, width, height` from the prompt — they waste
tokens and confuse the model. Replace with `position_description`.

---

### 4. Page Structure and Section Headers (MEDIUM IMPACT)

**What:** Extract section headers, horizontal rules, and grouping
information from the PDF and send as structured context.

**Example:**
```
Page 1 Structure:
  Section "申請者情報" (Applicant Information):
    Fields: 氏名, フリガナ, 生年月日, 性別
  Section "連絡先" (Contact):
    Fields: 住所, 電話番号, メールアドレス

Page 2 Structure:
  Section "勤務先情報" (Employer Information):
    Fields: 会社名, 部署, 役職
```

**Why:** Tells the model that 氏名 and 住所 are in different sections,
preventing cross-contamination. Currently the model sees all fields
as one flat list with no grouping.

**How to extract:** Use PDF text extraction with spatial analysis —
identify large/bold text as section headers, use vertical gaps and
horizontal lines as section boundaries.

---

### 5. Multilingual Instructions and Few-Shot Examples (MEDIUM IMPACT)

**What:** Replace the current generic English system prompt with
language-aware instructions including concrete examples.

**Add to system prompt:**

```
## Language Handling
- Field labels and data may be in Japanese, English, or mixed.
- Match semantically across languages.
- Japanese names are family-name first (姓 → 名).

## Common Field Mappings (examples)
- 氏名 / Full Name
- 姓 / Family Name / Last Name
- 名 / Given Name / First Name
- 住所 / Address
- 電話番号 / Phone Number
- 生年月日 / Date of Birth
- メールアドレス / Email

## Example Match
Source data: "Name: 田中太郎, Address: 東京都新宿区..."
Form fields: [氏名, 住所, 電話番号]
→ 氏名 = "田中太郎" (confidence: 0.95)
→ 住所 = "東京都新宿区..." (confidence: 0.95)
→ 電話番号 = unfilled (no phone data in source)
```

---

### 6. User Profile Data (MEDIUM IMPACT)

**What:** Pre-saved personal information that applies across all forms
for a given user — name, address, date of birth, phone number, etc.

**Why:** Many forms ask for the same applicant info. If the user has
already entered their name and address once, the system should reuse
it without requiring them to upload a source document every time.

**How to include in prompt:**

```
## User Profile (pre-registered information)
- Full Name: 田中太郎
- Date of Birth: 1990-01-15
- Address: 東京都新宿区西新宿1-1-1
- Phone: 03-1234-5678
- Email: tanaka@example.com

Use this data for matching when no other source provides the value.
Profile data has confidence 0.95 (user-verified).
```

**Prerequisite:** Requires a user profile storage feature (not yet built).
This is a follow-up feature, not an immediate change.

---

### 7. Template-Specific Rules (MEDIUM IMPACT)

**What:** Per-form rules that tell the LLM how specific fields should
be filled for this particular form template.

**Example:**

```
## Template Rules for Form "確定申告書B"
- Field "提出日" should be today's date in 令和 format (e.g., 令和7年2月5日)
- Field "整理番号" should be left unfilled (assigned by tax office)
- Field "住所" should use the registered address, not current address
- Fields "収入金額" are numeric, use no commas, yen amounts without ¥
```

**Why:** Business forms have conventions that a generic LLM won't know.
Template rules encode domain knowledge that dramatically improves
accuracy for specific forms.

**Prerequisite:** Requires a template rule editor UI and storage.
Rules can be created manually per template or learned from user
corrections over time.

---

### 8. Extracted Source Text with Structure (LOW-MEDIUM IMPACT)

**What:** Improve how extracted text from sources is formatted before
sending to the LLM.

**Current format (flat):**
```
### Driver's License (pdf)
Extracted fields:
  - Name: 田中太郎
  - Address: 東京都新宿区...
  - DOB: H2.1.15
```

**Target format (structured with metadata):**
```
### Source: Driver's License (pdf)
Document type: Japanese driver's license
Extraction confidence: 0.85
Data:
  Personal:
    - Full Name (氏名): 田中太郎
    - Date of Birth (生年月日): H2.1.15 (→ 1990-01-15)
  Address:
    - Address (住所): 東京都新宿区西新宿1-1-1
  License:
    - License Number: 012345678901
    - Expiry: 2027-05-20
```

**Improvements:**
- Identify the source document type (license, passport, etc.)
- Group extracted data by category
- Normalize dates and formats alongside raw values
- Include extraction confidence per field

---

## Summary: Data Layers to Send

```
┌─────────────────────────────────────────────────────┐
│                    LLM INPUT                        │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ 1. Target form page images (PNG, 150 DPI)    │   │
│  │    → model can SEE the form layout           │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │ 2. Source document images (scans, photos)    │   │
│  │    → model reads sources directly            │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │ 3. Enriched field metadata                   │   │
│  │    label + acroform_name + section +          │   │
│  │    nearby_labels + position_description       │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │ 4. Page structure / section headers          │   │
│  │    → grouped field context                   │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │ 5. Multilingual instructions + examples      │   │
│  │    → JP/EN field mapping, name ordering      │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │ 6. User profile data (if available)          │   │
│  │    → pre-registered personal info            │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │ 7. Template rules (if available)             │   │
│  │    → per-form business rules                 │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │ 8. Structured source extractions             │   │
│  │    → categorized, normalized, with confidence │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ──────────────────────────────────────────────────  │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ TWO-PASS ESCALATION                          │   │
│  │ Pass 1: gpt-5-mini  (all fields)             │   │
│  │ Pass 2: gpt-4o      (low-confidence only)    │   │
│  │ Threshold: configurable, default 0.8         │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Implementation Order

| Phase | Layers | Prerequisites |
|-------|--------|---------------|
| Phase 1 | 1 (form images) + 3 (enriched metadata) + 5 (multilingual prompts) | None — can do now |
| Phase 2 | 4 (page structure) + 8 (structured extractions) | PDF structure analysis |
| Phase 3 | 2 (source images) + two-pass escalation | Multimodal API call for sources |
| Phase 4 | 6 (user profile) + 7 (template rules) | New features: profile storage, rule editor |

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `AUTOFILL_IMAGE_DPI` | `150` | DPI for rendering form page images |
| `AUTOFILL_SEND_FORM_IMAGES` | `True` | Include target form page images |
| `AUTOFILL_SEND_SOURCE_IMAGES` | `True` | Include source document images |
| `AUTOFILL_MAX_PAGES_AS_IMAGES` | `10` | Max pages to render as images (cost control) |
| `ESCALATION_CONFIDENCE_THRESHOLD` | `0.8` | Below this, escalate to stronger model |
| `ESCALATION_MODEL` | `"gpt-4o"` | Model for the second pass |
| `MIN_FILL_CONFIDENCE` | `0.5` | Below this, don't fill the field |
