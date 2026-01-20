# Step 03: Adjust UI (PDF viewer + drag to edit placement)

## Goal
Provide a browser-based editor where a user can visually adjust placements (x/y/max_width) for each field on top of the PDF.

This establishes the “semi-automatic” workflow even before LLM analysis exists.

## Scope
- Web app UI:
  - Upload/select a template PDF (local URL or fetched)
  - Display PDF page using `pdf.js`
  - Overlay interactive objects using `react-konva`:
    - placement boxes (bbox)
    - anchor markers are optional in v1
  - Allow user to:
    - select a field from a list
    - drag the field bbox to adjust x/y
    - resize width to adjust max_width (minimum required)
    - edit font policy (max/min) in a side panel (optional)
  - Export edited `schema_json` (download JSON) and/or send to backend
- Minimal backend support:
  - Optional endpoint: `POST /templates/preview` or reuse `/generate` to preview output quickly

## Out of Scope
- LLM analysis
- DB persistence (Step 05)
- Organization/Auth (v2)
- Multi-user collaboration

## Files/Dirs to touch
- `apps/web/src/pages/editor.tsx` (or route)
- `apps/web/src/components/PdfViewer.tsx`
- `apps/web/src/components/PlacementLayer.tsx`
- `apps/web/src/lib/schema.ts` (zod validation)
- `apps/web/src/api/client.ts`
- (optional) `apps/api/app/routes/preview.py`

## Implementation Notes
- pdf.js coordinate system differs from PDF points; MUST implement consistent mapping:
  - PDF points <-> viewport pixels conversion
  - include page rotation handling if present (basic: assume 0 rotation for v1)
- Keep schema in React state as the single source.
- Provide “snap to” or arrow-key nudge (optional).

## Done Criteria (Acceptance)
- User can load a PDF and see a page rendered.
- User can move at least 1 field bbox and export updated schema_json.
- Updated schema_json works with `/generate` to produce a PDF reflecting the change.
- `make check-web` passes.

## Commands
- `make check-web`
- Run web: `cd apps/web && pnpm dev` (or `npm run dev`)
