# Step 02: TemplateSchema (JSON-driven placement + auto-fit text)

## Goal
Replace hard-coded coordinates with a JSON-driven schema so the generation engine is template-driven and reusable.

## Scope
- Define shared schema artifacts in `packages/schema`:
  - DraftTemplate and FinalTemplate (v1 only needs FinalTemplate minimum)
  - Field definition: id/label/type/required/validation
  - Placement definition: page_index/x/y/max_width/align/font_policy
- Implement backend to accept either:
  - `template_id` (optional; persistence later), OR
  - direct `schema_json` inline in request payload
- Update `/generate` to:
  - iterate over `fields[]` and draw each corresponding value
  - apply auto-fit text:
    - if text width > max_width: reduce font size down to min
    - if still too long: ellipsize
- Add schema validation on API input (Pydantic + JSON Schema check or pydantic models).

## Out of Scope
- LLM analysis
- UI coordinate editor (Step 03)
- DB persistence (Step 05)
- Anchor-based relative placement (optional later)

## Files/Dirs to touch
- `packages/schema/*` (JSON Schema + TS types)
- `apps/api/app/models/template_schema.py`
- `apps/api/app/services/pdf_engine.py`
- `apps/api/app/routes/generate.py`
- `apps/api/tests/*`

## Design Notes
- Single source of truth: `schema_json`.
- Coordinate system: PDF points, origin bottom-left, page_index 0-based.
- Field `key` in schema must match input payload keys.

## Done Criteria (Acceptance)
- `/generate` can render at least 5 fields driven by schema_json.
- Auto-fit reduces font size for long strings and ellipsizes at min font size.
- Invalid schema_json is rejected with a clear error.
- `make check-api` passes.

## Commands
- `make check-api`
