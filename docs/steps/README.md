# Steps (MVP v1)

- Step 00: Bootstrap
- Step 01: PDF Generate (manual placement)
- Step 02: JSON-driven TemplateSchema
- Step 03: Adjust UI
- Step 04: Analyze (LLM -> DraftTemplate)
- Step 05: Persistence (Supabase DB + storage)

## Working rule
- Each step = one branch: `step/NN-slug`
- Before pushing: run `make check`
- Merge to `main` before starting the next step (cut new step branch from `main`)
