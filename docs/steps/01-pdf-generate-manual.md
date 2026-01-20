# Step 01: PDF Generate (Manual placement, single known PDF)

## Goal
Prove the PDF generation pipeline works end-to-end:
input JSON -> overlay text drawing -> merged output PDF.

This step intentionally uses manual / fixed coordinates and does not depend on template schema or UI editing.

## Scope
- Implement backend endpoint: `POST /generate`
  - Accepts minimal payload with a few fields (e.g., `name`, `address`)
  - Uses a fixed, known template PDF stored locally in the API container (or fetched via URL env var)
  - Generates overlay PDF with text drawn at hard-coded coordinates
  - Merges overlay onto template and returns PDF bytes
- Package Japanese font into the Docker image (IPAexGothic or similar).
- Add minimal unit/integration tests to validate:
  - Endpoint returns PDF content-type
  - Output PDF is non-empty and parseable (basic check)
- Add a local template PDF under `apps/api/assets/templates/` (one of the NTA PDFs is acceptable, but do not commit sensitive docs).

## Out of Scope
- Any LLM analysis
- Any dynamic schema driving
- Any coordinate editing UI
- Any database or storage persistence
- Any signed URL workflow

## Files/Dirs to touch
- `apps/api/app/main.py` (or equivalent FastAPI entry)
- `apps/api/app/routes/generate.py`
- `apps/api/app/services/pdf_generate_manual.py`
- `apps/api/assets/fonts/*`
- `apps/api/assets/templates/*` (a single template)
- `apps/api/tests/*`
- `apps/api/Dockerfile`

## Implementation Notes
- Use `reportlab` to create overlay PDF (same page size as template).
- Use `pypdf` to merge overlay onto the template page.
- Coordinate system MUST be defined and documented in code:
  - Use PDF points
  - Origin = bottom-left
- Use a known font to avoid tofu for Japanese.

## Done Criteria (Acceptance)
- `POST /generate` returns a valid PDF for a sample request.
- Output includes drawn text at expected approximate location (manual visual check once).
- `make test-api` passes.
- Docker build succeeds and the container runs locally.

## Commands
- `make test-api`
- Local run: `cd apps/api && source .venv/bin/activate && uvicorn app.main:app --reload`
- Test request (example):
  - `curl -X POST http://localhost:8000/generate -H "Content-Type: application/json" -d '{"name":"山田太郎","address":"東京都..." }' --output out.pdf`
