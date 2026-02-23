# Python Refactor Clean

Safely identify and remove dead Python code with test verification:

1. Run cleanup tooling (prefer Poetry):
   - `poetry run ruff check . --fix`
   - `poetry run black .`
   - `poetry run vulture apps/api/app apps/api/tests` (dead-code candidates)

2. Generate a short report (in-chat) grouped by:
   - SAFE: unused imports, obviously unused local helpers
   - CAUTION: routers/entrypoints, DI, dynamic imports
   - DANGER: config/bootstrapping, anything reflection-based

3. Propose SAFE deletions/edits only.

4. Before each deletion batch:
   - Run `poetry run pytest`
   - Apply the batch
   - Re-run `poetry run pytest`
   - Roll back if tests fail

Never delete Python code without running tests first.
