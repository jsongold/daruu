# Plan: Claude-Native File Handling (No Navigation)

## Goal
Users stay in Claude throughout the entire form-filling workflow. No redirects to external pages.

## Core Insight
Claude is multimodal - it can **read PDFs directly** from attachments. We don't need to send the file through MCP. Claude extracts the data, MCP receives only metadata.

---

## Strategy: Claude Reads, MCP Acts

```
┌─────────────────────────────────────────────────────────────┐
│                        CLAUDE                                │
│  ┌─────────┐    ┌──────────────┐    ┌─────────────────┐    │
│  │  User   │───▶│ Claude reads │───▶│ Extracts fields │    │
│  │attaches │    │  PDF directly│    │ names, types,   │    │
│  │  PDF    │    │  (multimodal)│    │ positions       │    │
│  └─────────┘    └──────────────┘    └────────┬────────┘    │
│                                               │              │
│                                               ▼              │
│                                    ┌─────────────────┐      │
│                                    │ Calls MCP tool  │      │
│                                    │ with METADATA   │      │
│                                    │ only (small)    │      │
│                                    └────────┬────────┘      │
└─────────────────────────────────────────────┼───────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      MCP SERVER                              │
│  ┌─────────────────┐    ┌─────────────────────────────┐    │
│  │ register_form   │    │ Store field definitions     │    │
│  │ (metadata only) │───▶│ No actual PDF needed yet   │    │
│  └─────────────────┘    └─────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Workflow Phases

### Phase 1: Form Analysis (No file transfer needed)
```
User: [attaches tax_form.pdf] "Help me fill this form"

Claude: *reads PDF visually*
Claude: "I can see this is a W-9 form with these fields:
        - Name (text, line 1)
        - Business name (text, line 2)
        - Tax classification (checkbox, line 3)
        - Address (text, line 4)
        ..."

Claude: calls register_form({
  form_type: "W-9",
  fields: [
    {name: "name", type: "text", page: 1, position: "line 1"},
    {name: "business_name", type: "text", page: 1, position: "line 2"},
    ...
  ]
})

MCP: Returns form_id
```

### Phase 2: Data Collection (Conversation in Claude)
```
Claude: "I'll help you fill this W-9. What's your full legal name?"
User: "John Smith"

Claude: "And your business name if different?"
User: "Smith Consulting LLC"

Claude: calls update_fields(form_id, {
  name: "John Smith",
  business_name: "Smith Consulting LLC"
})
```

### Phase 3: Review (Text-based, no preview image)
```
Claude: "Here's what I have so far:
        ✓ Name: John Smith
        ✓ Business name: Smith Consulting LLC
        ○ Tax classification: Not set
        ○ Address: Not set

        What's your tax classification?"
```

### Phase 4: Export (Only time file is needed)

**Option A: Cloud URL**
```
Claude: "Your form is ready! To generate the filled PDF,
        please share a link to your original form
        (Google Drive, Dropbox, etc.)"

User: "https://drive.google.com/file/d/xxx"

Claude: calls export_pdf(form_id, source_url: "https://...")
MCP: Fetches file, fills it, returns download link
```

**Option B: Claude Desktop filesystem**
```
Claude: calls export_pdf(form_id, local_path: "/Users/john/tax_form.pdf")
MCP: (via filesystem MCP) reads local file, fills, saves
```

**Option C: Re-attachment**
```
Claude: "Please attach the original PDF again so I can
        generate your filled form."

User: [re-attaches PDF]

Claude: *reads PDF as base64, but ONLY for export*
Claude: calls export_pdf(form_id, file_data: "base64...")
```

---

## MCP Tool Redesign

### Current Tools (file-heavy) → New Tools (metadata-first)

| Old | New | Data Size |
|-----|-----|-----------|
| `upload_form(file_data)` | `register_form(fields, metadata)` | ~1KB vs ~1MB |
| `render_preview(form_id)` | `get_form_summary(form_id)` | Text only |
| `export_pdf(form_id)` | `export_pdf(form_id, source_url)` | URL reference |

### New Tool Definitions

```python
# 1. Register form from Claude's analysis
register_form(
    form_type: str,           # "W-9", "1040", etc.
    fields: list[Field],      # Field definitions
    page_count: int,
    metadata: dict            # Any extra info
) -> form_id

# 2. Update field values
update_fields(
    form_id: str,
    values: dict[str, any]    # field_name -> value
) -> success

# 3. Get current state (text-based)
get_form_summary(
    form_id: str
) -> {filled: [...], empty: [...], warnings: [...]}

# 4. Export with source file
export_pdf(
    form_id: str,
    source_url: str | None,   # Cloud link
    source_path: str | None,  # Local path (Desktop)
    source_data: str | None   # Base64 (last resort)
) -> download_url
```

---

## Field Definition Schema

What Claude extracts from reading the PDF:

```json
{
  "fields": [
    {
      "name": "taxpayer_name",
      "label": "Name (as shown on your income tax return)",
      "type": "text",
      "page": 1,
      "position": {
        "description": "Line 1, full width",
        "y_percent": 15
      },
      "required": true,
      "validation": "non-empty string"
    },
    {
      "name": "tax_classification",
      "label": "Federal tax classification",
      "type": "checkbox_group",
      "page": 1,
      "options": [
        "Individual/sole proprietor",
        "C Corporation",
        "S Corporation",
        "Partnership",
        "Trust/estate",
        "LLC"
      ]
    }
  ]
}
```

---

## Handling Different Claude Environments

| Environment | File Access Method | Export Strategy |
|-------------|-------------------|-----------------|
| Claude.ai (web) | User re-attaches | Base64 at export only |
| Claude Desktop | Filesystem MCP | Local file path |
| Claude API | User provides URL | Cloud URL |

---

## Benefits

1. **No context overflow** - Only small metadata passes through MCP
2. **No navigation** - User never leaves Claude
3. **Fast interaction** - No file upload waits during conversation
4. **Works everywhere** - Adapts to Claude environment

## Trade-offs

1. **Relies on Claude's PDF reading** - May miss some fields
2. **No visual preview** - Text-based status only (or image generation)
3. **Export requires file** - One of the three methods needed

---

---

## Alternative Strategy: Compress File Data

If we must send file data through MCP, minimize token usage:

### Compression Techniques

#### 1. **Extract Only Form Structure (Best)**
Instead of sending entire PDF, extract just coordinates:

```python
# From a 500KB PDF → 2KB JSON
{
  "pages": 1,
  "fields": [
    {"name": "Name", "rect": [50, 100, 300, 120], "type": "text"},
    {"name": "SSN", "rect": [400, 100, 550, 120], "type": "text"},
  ]
}
```

#### 2. **Downscale Images Aggressively**
For visual preview, reduce resolution drastically:

```python
# Original: 612x792 @ 150dpi = ~500KB
# Compressed: 150x200 @ 72dpi = ~5KB

from PIL import Image
img = Image.open(pdf_page_image)
img = img.resize((150, 200), Image.LANCZOS)
img = img.convert('L')  # Grayscale
img.save(output, 'JPEG', quality=30)
```

#### 3. **Send Thumbnail + Coordinates**
```
┌──────────────┐
│ 📄 tiny      │  +  field_rects: [...]
│   thumbnail  │
│   (5KB)      │
└──────────────┘
```

#### 4. **Binary-to-Token Efficient Encoding**
Base64 is 33% overhead. Alternatives:

| Encoding | Overhead | Tokens/KB |
|----------|----------|-----------|
| Base64 | +33% | ~1,400 |
| Base85 | +25% | ~1,200 |
| zlib + Base64 | -50% then +33% | ~700 |
| Field-only JSON | -99% | ~20 |

```python
import zlib
import base64

# Compress then encode
compressed = zlib.compress(pdf_bytes, level=9)
encoded = base64.b85encode(compressed).decode()
# Typical 500KB PDF → 150KB → 190KB encoded
```

#### 5. **Send Hash + Server Cache**
First time: Send compressed file, server caches with hash
Subsequent: Send only hash reference

```python
# First call
register_form(file_hash="abc123", file_data="compressed...")

# Later calls
get_fields(file_hash="abc123")  # Server uses cached file
```

#### 6. **Progressive Loading**
Send in stages:
1. First call: Page 1 only (thumbnail)
2. Claude confirms form type
3. Second call: Full field extraction
4. No more file data needed

### Token Budget Estimation

| Content | Tokens |
|---------|--------|
| Simple form (1 page, 10 fields) | ~200 |
| Complex form (5 pages, 50 fields) | ~1,000 |
| Full PDF base64 (500KB) | ~700,000 ❌ |
| Compressed PDF (50KB) | ~70,000 ⚠️ |
| Field metadata only | ~500 ✅ |

### Recommended Hybrid Approach

```
Phase 1: Claude reads PDF visually
         → No data through MCP

Phase 2: Register form with metadata only
         → ~500 tokens

Phase 3: Fill fields conversationally
         → ~200 tokens per update

Phase 4: Export with compressed file OR URL
         → 50KB compressed OR 0 bytes (URL)
```

---

## Implementation Priority

1. [ ] **Phase 1**: `register_form` + `update_fields` + `get_form_summary`
2. [ ] **Phase 2**: `export_pdf` with URL support
3. [ ] **Phase 3**: Claude Desktop filesystem integration
4. [ ] **Phase 4**: Visual preview generation (optional)

---

## Example Conversation

```
User: [attaches W-9.pdf]
User: I need to fill out this W-9 for my freelance work

Claude: I can see this is an IRS Form W-9 (Request for Taxpayer
        Identification Number and Certification). Let me help you
        fill it out.

        I've identified these fields:
        • Name (required)
        • Business name (optional)
        • Tax classification
        • Exemptions
        • Address
        • City, State, ZIP
        • SSN or EIN
        • Signature & Date

        Let's start - what's your full legal name as it appears
        on your tax return?

User: Sarah Johnson

Claude: Got it. Do you have a business name that's different
        from your personal name?

User: Yes, it's "SJ Design Studio"

Claude: What's your federal tax classification?
        □ Individual/sole proprietor
        □ C Corporation
        □ S Corporation
        □ Partnership
        □ LLC (specify classification)

User: Individual/sole proprietor

Claude: [continues collecting info...]

Claude: Great! Here's your completed W-9:

        ✓ Name: Sarah Johnson
        ✓ Business name: SJ Design Studio
        ✓ Classification: Individual/sole proprietor
        ✓ Address: 123 Main St, Austin, TX 78701
        ✓ SSN: ***-**-1234

        Ready to generate your filled PDF. Please share a
        Google Drive or Dropbox link to your blank W-9,
        or re-attach it here.

User: [re-attaches W-9.pdf]

Claude: *calls export_pdf*

        Done! Here's your filled W-9:
        📄 [Download W-9_Sarah_Johnson_filled.pdf]
```
