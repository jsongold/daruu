# Plan: Single-Page Web Interface

## Goal
Create a single-page PDF form filling interface without chat/agent complexity.

## Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Logo                    Single Page Editor              [Export PDF]    │
├────────────────┬───────────────────────────────────┬────────────────────┤
│                │                                   │                    │
│   LEFT PANE    │         CENTER PANE               │    RIGHT PANE      │
│   (250px)      │         (flexible)                │    (280px)         │
│                │                                   │                    │
│  Field List    │    Document Preview               │   Activity Log     │
│  - All fields  │    - PDF viewer                   │   - Upload events  │
│  - Status      │    - Zoom/pan                     │   - Edit history   │
│  - READ-ONLY   │    - Field highlights             │   - Export events  │
│  - Click to    │    - INLINE EDITING here          │                    │
│    highlight   │                                   │                    │
│                │                                   │                    │
│                │                                   │                    │
│                │                                   │                    │
├────────────────┴───────────────────────────────────┴────────────────────┤
│                        BOTTOM: Documents Section                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ [+ Upload]  [Doc1.pdf ✓] [Doc2.pdf] [Doc3.pdf]    [Clear All]       ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

## Existing Components to Reuse

| Section | Component | Location |
|---------|-----------|----------|
| Center | `EditableDocumentPreview` | `components/preview/EditableDocumentPreview.tsx` |
| Center | `FieldHighlight` | `components/preview/FieldHighlight.tsx` |
| Center | `InlineEditor` | `components/editor/InlineEditor.tsx` |
| Left | `FieldInfoPanel` | `components/editor/FieldInfoPanel.tsx` |
| Right | `ActivityTimeline` | `components/activity/ActivityTimeline.tsx` |
| Bottom | `DocumentUploader` | `components/documents/DocumentUploader.tsx` |
| UI | `Button`, `Card`, `Badge` | `components/ui/*` |

## New Components Needed

1. **`SinglePage.tsx`** - Main single-page layout container
2. **`DocumentBar.tsx`** - Bottom bar with upload + document list combined
3. **`FieldListReadOnly.tsx`** - Read-only field list (click to highlight in preview)

## Data Flow

```
┌─────────────────┐
│  SimplePage     │  (Main state holder)
│  - documents[]  │
│  - activeDocId  │
│  - fields[]     │
│  - activities[] │
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼
FieldList  Preview   Activity   Upload
(left)     (center)   (right)   (bottom)
```

## State Management

```typescript
interface SimplePageState {
  // Documents
  documents: Document[];
  activeDocumentId: string | null;

  // Fields for active document
  fields: FieldData[];
  selectedFieldId: string | null;

  // Preview
  currentPage: number;
  zoom: number;
  pageUrls: string[];

  // Activity log
  activities: Activity[];

  // UI state
  isLoading: boolean;
  isExporting: boolean;
  error: string | null;
}
```

## API Endpoints Used

| Action | Endpoint | Client |
|--------|----------|--------|
| Upload document | `POST /documents/upload` | `client.ts` |
| Get page preview | `GET /documents/{id}/pages/{page}/preview` | `client.ts` |
| Get fields | `GET /documents/{id}/fields` | `editClient.ts` |
| Update field | `PATCH /documents/{id}/fields/{fieldId}` | `editClient.ts` |
| Export PDF | `POST /documents/{id}/export` | `client.ts` |

## Implementation Steps

### Step 1: Create SimplePage Layout (30 min)
- Create `SimplePage.tsx` with CSS Grid layout
- 4 sections: left, center, right, bottom
- Responsive breakpoints for smaller screens

### Step 2: Integrate Document Upload (20 min)
- Use existing `DocumentUploader`
- Handle upload success → add to documents list
- Auto-select uploaded document

### Step 3: Integrate Document Preview (30 min)
- Use existing `EditableDocumentPreview`
- Connect to page preview API
- Handle field click → select field

### Step 4: Integrate Field List (20 min)
- Use existing `FieldInfoPanel` or create simplified version
- Show all fields with status (filled/empty)
- Click to select and scroll to field

### Step 5: Integrate Activity Log (15 min)
- Use existing `ActivityTimeline` or create simplified version
- Log: uploads, field edits, exports

### Step 6: Add Document List (20 min)
- Simple list/grid of uploaded documents
- Click to switch active document
- Delete option

### Step 7: Add Export Functionality (15 min)
- Export button in header/footer
- Download filled PDF

## File Structure

```
apps/web/src/
├── pages/
│   └── SinglePage.tsx           # NEW - Main single-page interface
├── components/
│   └── single/                   # NEW folder
│       ├── DocumentBar.tsx       # NEW - Upload + document list bar
│       ├── FieldListReadOnly.tsx # NEW - Read-only field list
│       └── ActivityLog.tsx       # NEW - Activity log panel
```

## Routing

Add new route in `App.tsx`:
```typescript
<Route path="/single" element={<SinglePage />} />
```

Or replace the default route if this becomes the main interface.

## Styling

- Use existing Tailwind classes
- CSS Grid for main layout
- Consistent with existing UI components

## Success Criteria

1. Single page - no navigation required
2. Upload PDF → see preview immediately
3. Click field in preview → edit inline
4. See all fields in left panel
5. Activity log shows actions
6. Export filled PDF works
