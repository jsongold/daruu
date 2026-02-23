# Python Test Coverage

Analyze Python test coverage and generate missing tests:

1. Run tests with coverage (Poetry-first):
   - `poetry run pytest --cov=apps/api/app --cov-report=term-missing --cov-report=html`

2. Identify modules below target coverage (aim for 80%+ meaningful coverage).

3. For each under-covered module:
   - Enumerate untested branches and error paths
   - Add unit tests for pure helpers
   - Add integration tests for FastAPI routes/services
   - Prefer behavior-level assertions over implementation details

4. Verify new tests pass and re-run coverage.

5. Show before/after coverage summary.
