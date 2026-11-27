# Build Instructions (U3 Note Organizer)

**Stage**: Build and Test, unit U3. Measured 2026-11-27 on the team's Windows laptop (uv 0.13.10, Python 3.13.14, Ollama 0.40.18 with `qwen3:8b`). U1's `../build-instructions.md` and U2's `../u2-import-and-timeline/build-instructions.md` still apply; this file lists only what U3 changes.

## What changed since U2
- **No new dependency** (U3-NFR, Q11 A). `uv sync --frozen` unchanged.
- **New table** `note_suggestions`, created by the app's schema setup on start; no migration step for a fresh database.
- **Organizer call** sends `response_format` `json_schema` and `reasoning_effort="none"` to Ollama `/v1`; the organizer per-call limit is 240 s.

## Build steps
```powershell
Set-Location D:\documents\web\classes\INFO5940\trip-journal-agent
uv sync --frozen
uv run ruff check trip_journal tests
uv run ruff format --check trip_journal tests
uv run mypy --strict trip_journal tests
```
Measured: ruff "All checks passed!", 96 files already formatted, mypy "no issues found in 94 source files".

## Run the app (Ollama must be running with `qwen3:8b` pulled)
```powershell
$env:TRIP_JOURNAL_PORT = "8742"; $env:TRIP_JOURNAL_DB = "$env:TEMP\bt-u3.db"; uv run trip-journal
```
Measured: serves on `http://127.0.0.1:8742`; `GET /trips` returns 200.

## Known warning
`scripts/model_spike.py` still fails ruff E501 (U1 spike script, out of scope).
