# U4 Daily Journal - Tech Stack Decisions

**Stage**: Construction - NFR Requirements (plan step 6)
**Source**: U1 and U3 `tech-stack-decisions.md`, `pyproject.toml`, `trip_journal/agent/llm.py`, `trip_journal/agent/loop.py`, `trip_journal/config.py`, plan answers Q1-Q5, Q8, Q12, Q13 (all A, owner, 2026-11-28T00:08:56Z), probe in the plan
**Scope**: U4 adds **no new runtime or dev dependency** (Q13 A). This file records the model-call choices and what U4 reuses. Implementation notes N-1..N-9 are in `nfr-requirements.md` §9.

---

## 1. Model call

| Decision | Value | Evidence / reason |
|---|---|---|
| Model | `qwen3:8b` (U1 default) | U1 NFR Q1 A |
| Endpoint | Ollama `/v1` through the `openai` SDK (`OllamaClient`, U1) | U1 |
| Call style | `AgentLoop` with the five read-only tools, after an app-run step 0 that pre-fetches `list_day_stops` + `get_stop_notes` for every stop of the day | Q1 A; probe: the model skipped `get_stop_notes` in both pure agent runs |
| Thinking | Off for journal calls: `reasoning_effort="none"` through a new optional `AgentLoop` argument; other agent callers unchanged | Q2 A; probe: 99 s vs 359 s |
| Output format | Plain text with `## <slot>` headings (BL-3); no `response_format` | FD Q6 A |
| Per-call limit | 300 s (`JOURNAL_CALL_TIMEOUT_S`), passed both to `asyncio.timeout` and as per-request `timeout_s` (the SDK backstop is 120 s) | Q3 A, U3 N-2 |
| Job limit | `min(300 s × planned calls, 1800 s)` | Q3 A |
| Context | No `num_ctx` sent (Ollama default, 4,096 on this laptop); chunks of ≤ 6 stops or ≤ 4,000 note characters, summary call when chunked | Q5 A |
| Output length | No `max_tokens`; tone fragment sets length | Q8 A |
| Retries | None (`max_retries=0`, AL-8, JR-F4) | U1 |

Rejected: pure agent (Q1 B, ungrounded drafts); rejecting runs without `get_stop_notes` (Q1 D, most runs would fail); also pre-fetching `find_photos` (Q1 C, more context for little gain); thinking on (Q2 B, over the limit, fabricated real ids); a thinking setting (Q2 C); 240 s / 300 s or 120 s / 300 s limits (Q3 B, C); raising the Ollama context (Q5 C, unverified on `/v1`, slower, more VRAM); refusing big days (Q5 B); silent truncation (Q5 D); `max_tokens=2048` (Q8 B).

## 2. Runtime (reused)

| Area | Choice | U4 use |
|---|---|---|
| Language | Python 3.12+ | all code |
| Web | FastAPI, uvicorn, Jinja2, htmx 2.0.4 | journal page, editor autosave, citation panel, job fragment |
| Validation | Pydantic v2 (`extra="forbid"` for edits, tone enum) | edit body, `JournalDraft`, trace |
| Database | `sqlite3` direct in the event loop; one `BEGIN IMMEDIATE` save step per job; one transaction per edit | `journals`, `journal_paragraphs` |
| Jobs | U1 `JobRunner`, one `journal` job, job limit set per job | |
| Config | new constants in `config.py`: `JOURNAL_CALL_TIMEOUT_S`, `JOURNAL_JOB_TIMEOUT_PER_CALL_S`, `JOURNAL_JOB_TIMEOUT_CAP_S`, `JOURNAL_CHUNK_MAX_STOPS`, `JOURNAL_CHUNK_MAX_CHARS` | |
| Port | `TRIP_JOURNAL_PORT` for manual runs (8000 is taken on this laptop) | Build and Test |

## 3. Testing (reused)

| Decision | Value |
|---|---|
| Runner | pytest, pytest-cov (≥ 80% on U4 modules), FastAPI `TestClient` |
| PBT framework | Hypothesis (PBT-09, U1) |
| Profiles | `default` 100, `ci` 500, `print_blob=True`, `deadline=None`; no new profile |
| Strategies | shared `tests/strategies.py`: days and stops with note lengths, slot lists and owners, journal text with headings and citations, drafts |
| Properties | P-1..P-7 (business-rules) + P-8 chunk split |
| Fake model | `FakeLLMClient` (U1/U3), already records `reasoning_effort` and `timeout_s` |
| Lint / types | ruff, mypy strict |

## 4. Dependency versions

No change. `pyproject.toml` keeps lower bounds; `uv.lock` stays the source of exact versions. `reasoning_effort` and per-request `timeout` are already used by U3 through the locked `openai` SDK.

## 5. Logging

U1 setup (`logging`, console, key=value, `TRIP_JOURNAL_LOG_LEVEL`). U4 adds the job, chunk, edit and parse-drop lines in `nfr-requirements.md` §6; no note or journal text.
