# Step 00: Bootstrap (Repo baseline, schemas, tooling)

## Goal
Establish a stable monorepo baseline so subsequent steps can be implemented with minimal ambiguity and consistent tooling.

## Scope
- Create monorepo structure:
  - `apps/web` (React TSX via Vite)
  - `apps/api` (Python FastAPI)
  - `packages/schema` (shared schema artifacts)
  - `infra/gcp` (placeholder only; infra implementation later)
  - `docs/steps` (this directory)
- Add root `Makefile` with targets: `setup`, `lint`, `type`, `test`, `check`
- Add minimal project configs:
  - API: `pyproject.toml` (ruff, mypy, pytest), `requirements.txt`
  - Web: `package.json` scripts for `lint`, `typecheck`, `test`, `format` (can be placeholders initially)
- Add shared schema scaffolding (no business schema yet):
  - `packages/schema/README.md`
  - `packages/schema/src/index.ts` exporting types (empty stubs ok)
- Ensure `make check` runs end-to-end without failing due to missing files (skips allowed, but no hard crash).

## Out of Scope
- Any PDF processing logic
- Any LLM integration
- Any database / storage integration
- Any deployment infrastructure beyond placeholders

## Files/Dirs to touch
- `Makefile`
- `apps/api/*`
- `apps/web/*`
- `packages/schema/*`
- `docs/steps/*`

## Design Notes / Decisions
- Monorepo is the single source of truth for layout and dependency boundaries.
- Backend = Python (FastAPI). Frontend = React TSX (Vite).
- All future services will consume a shared `TemplateSchema` in `packages/schema` (defined in Step 02).

## Done Criteria (Acceptance)
- Repo directories exist as specified.
- `make setup` completes (or is no-op-safe).
- `make check` completes without non-zero exit (can log “skipping” for missing tooling).
- Web app can run locally with `npm run dev` or `pnpm dev` (even if it renders a placeholder page).
- API can run locally with `uvicorn` (placeholder route is fine).

## Commands
- `make setup`
- `make check`
- API local: `cd apps/api && source .venv/bin/activate && uvicorn app.main:app --reload`
- Web local: `cd apps/web && pnpm dev` (or `npm run dev`)
