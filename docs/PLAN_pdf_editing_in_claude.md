# Plan: PDF Editing Features Inside Claude

## Goal
Enable users to visually edit PDF forms **without leaving Claude**. Leverage existing EditableDocumentPreview, InlineEditor, and FillService components through MCP integration.

---

## Current State Analysis

### Existing Backend Components
| Component | Location | Purpose |
|-----------|----------|---------|
| `MCPStorage` | `app/mcp/storage.py` | Redis-based form/document storage |
| `render_preview` | `app/mcp/tools/render_preview.py` | Generate PNG images of PDF pages with field highlights |
| `get_fields` | `app/mcp/tools/get_fields.py` | List all fields with values and status |
| `update_field` | `app/mcp/tools/update_field.py` | Update individual field values |
| `export_pdf` | `app/mcp/tools/export_pdf.py` | Generate filled PDF with AcroForm or overlay |

### Existing Frontend Components (NOT usable directly in Claude)
| Component | Location | Purpose |
|-----------|----------|---------|
| `EditableDocumentPreview` | `components/preview/EditableDocumentPreview.tsx` | Full PDF viewer with zoom, pan, field highlights |
| `InlineEditor` | `components/editor/InlineEditor.tsx` | Popover for editing field values |
| `FieldHighlight` | `components/preview/FieldHighlight.tsx` | Visual field overlays |

### MCP Tools Implemented (Vision-First Architecture)
| Tool | Status | Purpose |
|------|--------|---------|
| `register_form` | Done | Register form from Claude's visual analysis |
| `add_fields` | Done | Add more fields to existing form (chunked) |
| `update_fields` | Done | Set multiple field values |
| `get_form_summary` | Done | Text-based form status |
| `list_forms` | Done | List registered forms |
| `export_pdf` | Done | Generate filled PDF |
| `render_preview` | Done | Generate PNG preview with highlights |
| `get_fields` | Done | Detailed field list |

---

## The Challenge

Claude can display:
- Text (Markdown formatted)
- Images (PNG/JPEG via base64 or URL)
- Links (but user doesn't want navigation)

Claude **cannot** display:
- Interactive web components (React)
- Clickable field overlays
- Real-time editing UI

---

## Strategy: Image-Based Visual Editing

Since Claude can display images, we use `render_preview` to show the PDF with visual indicators, then update via conversation.

### Visual Editing Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                     CLAUDE INTERFACE                          │
│                                                               │
│  User: [attaches PDF]                                         │
│                                                               │
│  Claude: Here's your form with detected fields:              │
│                                                               │
│  ┌──────────────────────────────┐                            │
│  │ [Rendered PDF Image]          │  ← render_preview          │
│  │ ┌────────────────────────┐   │    with field highlights   │
│  │ │ 1. Name    [_______]   │   │                            │
│  │ │ 2. SSN     [_______]   │   │                            │
│  │ │ 3. Address [_______]   │   │                            │
│  │ └────────────────────────┘   │                            │
│  └──────────────────────────────┘                            │
│                                                               │
│  Field 1 (Name) is highlighted in yellow.                    │
│  What value should I fill for "Name"?                        │
│                                                               │
│  User: John Smith                                             │
│                                                               │
│  Claude: [Updates field, shows new preview with              │
│           Field 1 now green (filled)]                         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Enhanced render_preview Tool (Completed)

The `render_preview` tool already exists. Enhancements needed:

```python
render_preview(
    form_id: str,
    page: int = 1,
    zoom: float = 1.0,
    highlight_fields: list[str] = [],  # Field IDs to highlight
    highlight_style: str = "yellow",   # yellow, green (filled), red (error)
    show_values: bool = True,          # Overlay filled values on image
)
```

**Current Status**: Basic implementation exists, needs value overlay and color coding.

### Phase 2: Visual Field Selection

Allow Claude to highlight specific fields and walk user through them:

```python
# New tool or enhancement
highlight_field(
    form_id: str,
    field_id: str,
    style: str = "active",  # active (yellow), filled (green), empty (gray)
) -> ImageContent  # Returns image with that field highlighted
```

**Workflow**:
1. Claude calls `render_preview` with all fields gray
2. Claude calls `highlight_field(field_id="name")` → shows image with "Name" field in yellow
3. User provides value
4. Claude calls `update_fields` then `render_preview` showing "Name" in green

### Phase 3: Smart Field Navigation

Claude guides user through fields intelligently:

```python
# Enhancement to get_form_summary
get_next_unfilled_field(
    form_id: str,
    skip_optional: bool = False,
) -> {
    field: FieldInfo,
    preview_image: ImageContent,  # Page with this field highlighted
    context: str,  # "This is the SSN field on page 1, top right"
}
```

### Phase 4: Inline Value Preview

Show filled values on the rendered image:

```
┌──────────────────────────────────┐
│ Name:     [John Smith_______]    │  ← Value shown in field
│ SSN:      [___-__-____]          │  ← Empty field outline
│ Address:  [___________________]  │
└──────────────────────────────────┘
```

Implementation in `_render_page()`:
```python
# After rendering page, overlay text values
for field_info in fields.values():
    if value := field_info.get("value"):
        bbox = field_info.get("bbox")
        # Draw value text at bbox position
        page.insert_text(
            (bbox[0] + 2, bbox[1] + 12),
            str(value)[:30],  # Truncate long values
            fontsize=10,
            color=(0, 0, 0.8),  # Blue for filled values
        )
```

---

## MCP Tool Enhancements

### 1. Enhanced render_preview

```python
Tool(
    name="render_preview",
    description="Render PDF page as image with field highlights and filled values",
    inputSchema={
        "properties": {
            "form_id": {"type": "string"},
            "page": {"type": "integer", "default": 1},
            "zoom": {"type": "number", "default": 1.5},  # Larger for readability
            "highlight_mode": {
                "type": "string",
                "enum": ["all", "empty", "filled", "single"],
                "default": "all"
            },
            "highlight_field_id": {
                "type": "string",
                "description": "Field to highlight (when mode is 'single')"
            },
            "show_values": {
                "type": "boolean",
                "default": True,
                "description": "Overlay filled values on the image"
            },
        }
    }
)
```

### 2. New visual_edit_field Tool

Combines field info + preview in one call:

```python
Tool(
    name="visual_edit_field",
    description="Get a visual preview focused on a specific field for editing",
    inputSchema={
        "properties": {
            "form_id": {"type": "string"},
            "field_id": {"type": "string"},
        }
    }
) -> {
    "field_info": {
        "id": "...",
        "name": "taxpayer_name",
        "label": "Name (as shown on tax return)",
        "type": "text",
        "current_value": "John Smith" | null,
        "required": true,
        "options": [...] | null,  # For dropdowns
    },
    "preview_image": ImageContent,  # Page with this field highlighted
    "instructions": "Enter the taxpayer's full legal name"
}
```

### 3. New get_form_visual_summary Tool

Returns both text summary AND a preview image:

```python
Tool(
    name="get_form_visual_summary",
    inputSchema={
        "properties": {
            "form_id": {"type": "string"},
            "page": {"type": "integer", "default": 1},
        }
    }
) -> [
    TextContent("Form W-9: 5/8 fields filled"),
    ImageContent(preview_with_color_coded_fields),
]
```

---

## Color Coding System

| Status | Color | Meaning |
|--------|-------|---------|
| Empty + Required | Red outline | Must fill |
| Empty + Optional | Gray outline | Can skip |
| Currently Editing | Yellow fill | Focus here |
| Filled | Green outline | Completed |
| Error/Invalid | Red fill | Needs correction |

---

## Example Conversation Flow

```markdown
User: [attaches W-9.pdf] Help me fill this out

Claude: I've analyzed your W-9 form. Here's an overview:

[IMAGE: Full form with all fields outlined - 8 empty fields in red/gray]

I found 8 fields to fill:
1. Name * (required)
2. Business name
3. Tax classification *
4. Exemptions
5. Address *
6. City, State, ZIP *
7. SSN or EIN *
8. Signature & Date

Let's start with the required fields. Here's the first one:

[IMAGE: Page 1 with "Name" field highlighted in yellow]

**Field: Name**
Enter your full legal name as shown on your income tax return.

What name should I fill in?

---

User: Sarah Johnson

Claude: Got it! I've filled in "Sarah Johnson".

[IMAGE: Page 1 with "Name" field now green, showing "Sarah Johnson"]

Next field:

[IMAGE: Same page with "Business name" field highlighted in yellow]

**Field: Business name (optional)**
If you have a different business name, enter it here.
Skip if same as your personal name.

---

User: SJ Design Studio

Claude: Added "SJ Design Studio".

[IMAGE: Shows both fields green with values visible]

Progress: 2/8 fields filled

[Continues through all fields...]

---

Claude: All required fields are complete! Here's your filled form:

[IMAGE: Full form with all fields green, values visible]

Ready to generate your PDF. Please either:
1. Share a link to the original blank W-9
2. Re-attach the PDF file

User: [re-attaches W-9.pdf]

Claude: Generating your filled W-9...

Done! [Download W-9_Sarah_Johnson_filled.pdf]
```

---

## Implementation Priority

### Must Have (Phase 1)
- [x] Basic render_preview tool
- [ ] Value overlay on rendered images
- [ ] Color-coded field status (empty/filled/active)

### Should Have (Phase 2)
- [ ] visual_edit_field tool for focused editing
- [ ] get_form_visual_summary for overview + image
- [ ] Zoom to specific field region

### Nice to Have (Phase 3)
- [ ] Multi-page navigation with thumbnails
- [ ] Field validation indicators
- [ ] Signature field handling

---

## Technical Notes

### Image Size Optimization

For Claude to display images well:
- Resolution: 1.5x-2x zoom (918x1188 for letter-size at 1.5x)
- Format: PNG for quality, JPEG for smaller size
- Max size: ~500KB per image (fits in context easily)

```python
# In _render_page
zoom = 1.5  # 150% scale for readability
matrix = fitz.Matrix(zoom, zoom)
pixmap = page.get_pixmap(matrix=matrix, alpha=False)

# Compress if needed
if len(png_bytes) > 500_000:
    # Convert to JPEG with quality reduction
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(png_bytes))
    output = io.BytesIO()
    img.save(output, 'JPEG', quality=85)
    return output.getvalue()
```

### Field Position Accuracy

Claude's visual analysis may not have exact coordinates. When overlaying values:

```python
# If we have bbox from AcroForm
if field.get("bbox"):
    x, y = bbox[0], bbox[3] - 12  # Bottom-left, adjusted up

# If we only have Claude's estimated position
elif position := field.get("position"):
    y_pct = position.get("y_percent", 50)
    x_pct = position.get("x_percent", 10)
    x = page_width * (x_pct / 100)
    y = page_height * (y_pct / 100)
```

---

## Alternative: Embedded Editor Link

If the user eventually wants more interactivity:

```python
# MCP returns a link to the web editor
open_visual_editor(
    form_id: str,
    return_to_claude: bool = True,  # Show "Back to Claude" button
) -> {
    "editor_url": "https://daru-pdf.io/edit/{form_id}?session={session_id}",
    "message": "Click to open visual editor (changes sync back to Claude)"
}
```

But this violates the "stay in Claude" requirement, so it's a fallback only.

---

## Files to Modify

1. `apps/api/app/mcp/tools/render_preview.py`
   - Add value overlay
   - Add color coding
   - Add field highlight modes

2. `apps/api/app/mcp/server.py`
   - Add `visual_edit_field` tool
   - Add `get_form_visual_summary` tool
   - Update tool descriptions

3. (Optional) New file: `apps/api/app/mcp/tools/visual_editing.py`
   - Combined visual editing helpers

---

## Success Criteria

1. User can see rendered PDF preview in Claude with field highlights
2. User can see which fields are filled (green) vs empty (red/gray)
3. User can see filled values overlaid on the preview image
4. User can navigate through fields with visual guidance
5. User never needs to leave Claude for the editing workflow
