# Build Instructions (U2 Import and Timeline)

**Stage**: Build and Test, unit U2. Measured 2026-11-27 on the team's Windows laptop (uv 0.13.10, Python 3.13.14). U1's `../build-instructions.md` still applies; this file lists only what U2 changes.

## What changed since U1
- **No new dependency** (U2-NFR). `uv sync --frozen`: "Checked 44 packages".
- **Port override (CI-1)**: `TRIP_JOURNAL_PORT` sets the port, so the U1 port workaround is no longer needed.
- **`/` redirects to `/trips`** (D-2).
- **Generated test data**: `scripts/make_reference_trip.py` (seed 5940) writes `sample_data/generated/reference_trip.json` (0.83 MB) and `large_trip.json` (19.71 MB). The folder is git-ignored; the slow perf test creates the files when they are missing.

## Build steps
```powershell
Set-Location D:\documents\web\classes\INFO5940\trip-journal-agent
uv sync --frozen
uv run ruff check trip_journal tests scripts/make_reference_trip.py
uv run ruff format --check trip_journal tests scripts/make_reference_trip.py
uv run mypy --strict trip_journal tests scripts/make_reference_trip.py
```
Measured: ruff "All checks passed!", 78 files already formatted, mypy "no issues found in 77 source files".

## Run the app
```powershell
$env:TRIP_JOURNAL_PORT = "8741"; $env:TRIP_JOURNAL_DB = "$env:TEMP\bt-u2.db"; uv run trip-journal
```
Measured: log `Uvicorn running on http://127.0.0.1:8741`; `GET /` returns 307 to `/trips`.

## Known warning
`ruff check .` on the whole repo still fails on `scripts/model_spike.py` (4 × E501, U1 spike script, out of scope).
