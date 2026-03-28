# Autobook

![Coverage](coverage.svg)

Autobook is an AI-assisted accounting prototype that converts raw transaction text into double-entry journal recommendations, routes uncertain cases into a clarification queue, and surfaces ledger-driven statement views.

## Frontend Docs

Frontend-specific references:

- `FRONTEND_ARCHITECTURE.md`
- `FRONTEND_DEPLOYMENT.md`
- `FRONTEND_REALTIME_UPDATES.md`

## Local Testing

Run the Python test suite with coverage:

```powershell
cd autobook
$env:PYTHONPATH='src'
python -m poetry run pytest
```

Generate the profiling reports required for A5:

```powershell
cd autobook
$env:PYTHONPATH='src'
python -m poetry run python scripts/profile_a5_backend.py
```

Coverage reports are generated in:

- `coverage.xml`
- `htmlcov/`

Profiling reports are generated in:

- `a5_artifacts/profiling/`

## CI Coverage

The GitHub workflow in `.github/workflows/coverage.yml` runs the Python tests with `pytest-cov`, publishes a coverage summary for pull requests, and updates the repository coverage badge on pushes to `main`.
