# Integration Test Instructions (U1 Foundation)

**Purpose**: check that U1's parts work together against the real local model server (Ollama 0.40.18, `qwen3:8b`), not mocks. Measured 2026-11-26 on the team laptop (GTX 1650 Ti 4 GB, 15.7 GiB RAM).

U1 has no question or journal page and no cancel endpoint (those come in U2 to U4). So the agent path was driven by a scratch harness that wires the same classes the app uses. The harness is **not** in the repo.

## Setup
1. Start Ollama and pull the model: `ollama pull qwen3:8b`.
2. Start the app (port 8000 was busy on the laptop, so port 8740 was used; see `build-instructions.md`):
```powershell
Set-Location D:\documents\web\classes\INFO5940\trip-journal-agent
$env:TRIP_JOURNAL_DB = "$env:TEMP\bt.db"; uv run python -c "import uvicorn; from trip_journal.logs import setup_logging; from trip_journal.main import create_app; setup_logging(); uvicorn.run(create_app(), host='127.0.0.1', port=8740, log_config=None)"
```
3. Browse to `http://127.0.0.1:8740/` (redirects to `/settings`).

## Scenarios and results

### S1. Settings page ↔ Ollama status probe (PASS)
- **Steps**: open `/settings` with Ollama running and `qwen3:8b` installed.
- **Expected**: model name, base URL, place-lookup checkbox, Save button, and a Model status panel with "Check again".
- **Measured**: all shown; the log line is `status.check reachable=True installed=True model=qwen3:8b`.

### S2. Model not installed (PASS, UX nit)
- **Steps**: save model `qwen3:14b` (not pulled).
- **Measured**: "✔ Settings saved.", then the top banner "The model qwen3:14b is not installed in Ollama. Run ollama pull qwen3:14b, then try again.", an inline warning, and status "✖ No".
- **Nit**: the same message shows three times (banner, inline, status panel).

### S3. Ollama not running (PASS, simulated)
- **Steps**: save base URL `http://localhost:11999/v1` (nothing listens there). Ollama itself was **not** stopped, because the owner had not approved it.
- **Measured**: banner "The local model is not available. Ollama is not running at http://localhost:11999/v1. Start Ollama (open the Ollama app or run ollama serve), then try again."; reachable "✖ No".

### S4. Non-local base URL rejected (PASS)
- **Steps**: `PUT /api/settings` with `http://example.com:11434/v1`.
- **Measured**: HTTP 422 `invalid_settings` with "Use a local address such as http://localhost:11434/v1."
- Settings were then restored to `qwen3:8b` / `http://localhost:11434/v1`.

### S5. JobRunner → AgentLoop → OllamaClient → tools → grounding (PASS, slow)
- **Harness**: it seeds an in-memory DB with the trip "Japan test trip": stops Fushimi Inari, Nishiki Market (2026-06-02) and Osaka Castle, and notes 1 to 3. It asks "What did I eat in Kyoto on 2026-06-02, and where?" through `JobRunner` with the default 300 s limit, then runs `check_text` on the answer.
- **Measured**: done in **241.2 s**, in 3 steps (107.4 s including the model load, then 69.3 s and 64.5 s).
  - Tool calls: `list_day_stops(2026-06-02)`, then `get_stop_notes(1)`, then `get_stop_notes(2)`.
  - The answer is correct: grilled octopus skewer and matcha soft serve at Nishiki Market, with the citation `[note:2]`.
  - **Grounding**: sentence 1 has no citation, so it is flagged unsupported; sentence 2 is supported. The check works. The model does not cite every sentence, which matters for the U3/U4 prompts.
- **First attempt failed** after 20.5 s with `model_error`:
  - Ollama returned HTTP 500 because its runner (`llama-server.exe`) crashed with exit 0xc0000409, "CUDA error: shared object initialization failed". Only 1.3 GiB of system RAM was free at the time.
  - The app mapped the error correctly and did not retry (`max_retries=0`).
  - A rerun with 4.5 GiB free succeeded. This is an environment limit, not an app bug.

### S6. Cancel / timeout stops generation in Ollama (PASS, both paths; NFR Design check)
| Path | How | Job result | Ollama side |
|---|---|---|---|
| Task cancel | `task.cancel()` 20 s into a model call | `job_timeout` at 20.7 s | log: `500 \| 20.29s POST /v1/chat/completions`, `srv stop: cancel task`, `slot release ... n_tokens = 780`, `all slots are idle` |
| Job deadline | `JobRunner(timeout_s=20)` | `job_timeout` at 20.0 s | log: `500 \| 19.67s`, `srv stop: cancel task`, `all slots are idle` |

- **Load before the cancel**: GPU at 33% and runner CPU time growing by about 2.9 s every 3 s.
- **Load 3 s after the cancel**: GPU at 0% and CPU growth of about 0.02 to 0.05 s every 3 s (idle).
- `ollama ps` still lists `qwen3:8b` (6.0 GB, 61%/39% CPU/GPU) until its keep-alive runs out. The model stays loaded but stops generating, which is expected.
- **Note**: a manual cancel is reported with the code `job_timeout`, by design in `JobRunner._run`. A separate `job_cancelled` code could be added when U2 adds the cancel button.

## Not verified in this stage
- Stopping Ollama for real (S3 used a wrong port instead).
- Clicking the "Check again" button, and the place-lookup toggle.
- A real Nominatim call (it is off by default; it is covered by mocked unit tests for the 5 s timeout, 1 request per second and the cache).
- A question asked through the UI (U1 has no such page or endpoint).

## Cleanup
Stop the app with Ctrl+C. Delete the scratch DB. Ollama and its installed models were left unchanged.
