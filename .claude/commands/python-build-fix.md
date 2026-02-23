# Python Build and Fix

Incrementally fix Python runtime, lint, and test failures:

1. Install or refresh dependencies: `poetry install` (or `pip install -r requirements.txt` for quick checks).

2. Run the relevant checks in this order:
   - `poetry run pytest` (or the targeted test module)
   - `poetry run mypy --strict`
   - `poetry run black --check .`
   - `poetry run ruff check .`
   - Optional: `python -m compileall apps/api/app`

3. Parse the combined output:
   - Group messages by file and then by severity (error > warning).
   - Track test failures separately from lint/type errors.

4. For each issue:
   - Capture 5 lines of context (before/after) for clarity.
   - Explain why it happens (type mismatch, missing import, assertion failure, etc.).
   - Propose the smallest fix that keeps existing behavior.
   - Apply the fix, rerun only the command that originally failed, and ensure it now passes.
   - Repeat until the same issue disappears or you decide a larger change is needed.

5. Stop if:
   - A fix introduces new FAIL/ERROR output that prevents progress.
   - The same error persists after three thoughtful attempts.
   - The user explicitly asks to pause.

6. Summarize the work:
   - Tests/lints that are now green.
   - Remaining blockers, including why they were left unresolved.
   - New errors introduced (if any).

Prioritize correctness over speed; keep builds reproducible by relying on the lockfile and documented scripts.
