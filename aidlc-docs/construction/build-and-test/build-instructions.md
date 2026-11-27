# Build Instructions (U1 Foundation)

**Stage**: Build and Test, unit U1 Foundation. Measured on 2026-11-26 on the team's Windows laptop.

## Prerequisites
- **Build tool**: uv 0.13.10 (the project uses `pyproject.toml` + `uv.lock`; build backend hatchling).
- **Python**: `requires-python >= 3.12`; measured with Python 3.13.14.
- **Runtime dependencies** (lower bounds in `pyproject.toml`, exact versions in `uv.lock`): fastapi 0.165.0, uvicorn 0.54.0, httpx 0.29.0, openai 3.60.0, pydantic 2.14.4, jinja2 3.1.6, python-multipart.
- **Dev dependencies**: pytest 9.2.0, pytest-asyncio 1.5.0, pytest-cov 7.1.0, hypothesis 6.170.17, mypy 2.4.1, ruff 0.17.6.
- **Model server**: Ollama (measured 0.40.18) with `qwen3:8b` pulled (`ollama pull qwen3:8b`, 5.2 GB). Only needed to run the app, not for the tests.
- **Environment variables** (all optional):

| Variable | Default | Purpose |
|---|---|---|
| `TRIP_JOURNAL_MODEL` | `qwen3:8b` | model name (a saved setting wins over it) |
| `TRIP_JOURNAL_OLLAMA_BASE_URL` | `http://localhost:11434/v1` | must be http on localhost, 127.0.0.1 or [::1] |
| `TRIP_JOURNAL_PLACE_LOOKUP` | off | Nominatim place lookup |
| `TRIP_JOURNAL_LOG_LEVEL` | `INFO` | log level |
| `TRIP_JOURNAL_DB` | `data/trip_journal.db` | SQLite file |
| `HYPOTHESIS_PROFILE` | `default` (100 examples) | `ci` = 500 examples, for the pre-merge run |

- **System**: Windows 11 / macOS / Linux. Measured laptop: Windows 11 Home, NVIDIA GeForce GTX 1650 Ti (4 GB VRAM), so `qwen3:8b` runs partly on the CPU.

## Build Steps

### 1. Install dependencies
```powershell
Set-Location D:\documents\web\classes\INFO5940\trip-journal-agent
uv sync --frozen
```
Measured: "Checked 44 packages", 0.1 s (already installed). A first install downloads the packages from PyPI.

### 2. Configure the environment
Nothing is required. Start Ollama (the Ollama app, or `ollama serve`) before using the app.

### 3. Build / static checks
Python needs no compile step. The "build" gate is lint + types:
```powershell
uv run ruff check trip_journal tests
uv run ruff format --check trip_journal tests
uv run mypy --strict trip_journal tests
```

### 4. Run the app
```powershell
uv run trip-journal
```
Serves on `http://127.0.0.1:8000` (localhost only) and opens nothing by itself; browse to `/` (redirects to `/settings`).

**Port 8000 conflict (found in this stage):** `HOST` and `PORT` are fixed in `trip_journal/config.py`. On the measured laptop port 8000 was already held by Docker Desktop / WSL (`wslrelay`, `com.docker.backend`), so `uv run trip-journal` failed with `[WinError 10048]` (exit code 3). Workaround used for Build and Test (same wiring as `run()`):
```powershell
uv run python -c "import uvicorn; from trip_journal.logs import setup_logging; from trip_journal.main import create_app; setup_logging(); uvicorn.run(create_app(), host='127.0.0.1', port=8740, log_config=None)"
```
Follow-up for U2 or later: allow a port override (for example `TRIP_JOURNAL_PORT`).

### 5. Verify build success
- **Expected**: ruff and mypy print no errors; the app log shows `Uvicorn running on http://127.0.0.1:<port>` and a `status.check reachable=True installed=True model=qwen3:8b` line on the first page load.
- **Artifacts**: none (no wheel is built for U1). The SQLite file is created at `TRIP_JOURNAL_DB` on first start.
- **Known warning**: `ruff check .` on the whole repo fails on `scripts/model_spike.py` (4 × E501, an earlier spike script outside `trip_journal/` and `tests/`).

## Troubleshooting

### `uv sync --frozen` fails
- **Cause**: `uv.lock` out of date with `pyproject.toml`, or no network for a first install.
- **Solution**: run `uv lock` (needs the team's OK, it changes versions), then `uv sync`.

### App does not start: `[WinError 10048]`
- **Cause**: port 8000 (or the chosen port) is in use.
- **Solution**: find the owner with `Get-NetTCPConnection -LocalPort 8000 -State Listen`; stop it or use the port workaround above.

### Settings page says "Ollama is not running"
- **Cause**: Ollama is stopped, or the base URL points at the wrong port.
- **Solution**: start Ollama; check the base URL on the Settings page; press "Check again".

### Settings page says "The model ... is not installed"
- **Solution**: `ollama pull <model>`, or change the model name on the Settings page.
