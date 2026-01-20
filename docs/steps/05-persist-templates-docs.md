# Step 05: Persistence (Supabase DB + template/doc lifecycle)

## Goal
Persist templates and generated documents so users can reuse templates and download prior outputs.
No auth/org yet in v1 (anonymous or simple session identifier).

## Scope
- Supabase Postgres schema (migrations):
  - `templates`:
    - id, name, status(draft/final), schema_json, pdf_fingerprint, pdf_path, version
  - `template_revisions`:
    - template_id, from_version, to_version, before_schema_json, after_schema_json, updated_by (nullable)
  - `documents`:
    - id, template_id, input_values_json (optional), output_pdf_path, created_at
- Backend endpoints:
  - `POST /templates` (create draft)
  - `POST /templates/{id}/finalize` (save final + revision)
  - `GET /templates/{id}` (fetch schema)
  - `POST /documents` (generate + persist record)
  - `GET /documents/{id}` (fetch metadata + download URL)
- File storage:
  - Store template PDFs and generated PDFs in GCS (preferred) or Supabase Storage (acceptable)
  - Use signed URLs for download
- v1 identity:
  - If no auth, use a simple `client_id` stored in localStorage to scope access (optional).
  - Alternatively, keep all templates public in v1 (not recommended for NTA docs if sensitive).

## Out of Scope
- Supabase Auth / Organizations / RBAC (v2)
- Learning logs (v3)
- Multi-tenant strict isolation in v1 (keep minimal)

## Files/Dirs to touch
- `apps/api/app/db/*` (supabase client)
- `apps/api/app/routes/templates.py`
- `apps/api/app/routes/documents.py`
- `apps/api/app/services/storage.py` (GCS signed URLs)
- `apps/api/migrations/*` (or `supabase/migrations/*`)
- `apps/web` changes to load/save templates (optional)

## Done Criteria (Acceptance)
- A DraftTemplate from `/analyze` can be saved as `templates(draft)`.
- Adjusted schema can be finalized and stored with revision history.
- `/documents` generates PDF and stores metadata + file path.
- Download uses signed URL.
- `make check-api` passes.

## Commands
- `make check-api`
