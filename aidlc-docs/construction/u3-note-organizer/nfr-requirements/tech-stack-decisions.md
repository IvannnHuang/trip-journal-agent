# U3 Note Organizer - Tech Stack Decisions

**Stage**: Construction - NFR Requirements (plan step 6)
**Source**: U1 and U2 `tech-stack-decisions.md`, `pyproject.toml`, `trip_journal/agent/llm.py`, plan answers Q1, Q2, Q3, Q10, Q11 (all A, owner, 2026-11-27T13:46:37Z), probe in the plan
**Scope**: U3 adds **no new runtime or dev dependency**. This file records the model-call choices and what U3 reuses.

---

## 1. Model call

| Decision | Value | Evidence / reason |
|---|---|---|
| Model | `qwen3:8b` (U1 default) | U1 NFR Q1 A |
| Endpoint | Ollama OpenAI-compatible `/v1` through the `openai` SDK (`OllamaClient`, U1) | U1 |
| Output format | `response_format` `json_schema`, schema from the `OrganizerReply` Pydantic model; no `json_object` fallback | Q1 A; probe: honoured by Ollama 0.40.18 with thinking on and off |
| Thinking | Off for the organizer only: `reasoning_effort="none"`. Agent loop unchanged (thinking on) | Q2 A; probe: 116 s vs ≥ 342 s per 10-note batch |
| Switches rejected | `/no_think` in the prompt (did not stop thinking with `json_schema`, 505 s); `extra_body={"think": false}` (timed out twice at 400 s, presumed ignored on `/v1`) | probe runs 3, 5 |
| Per-call limit | 240 s (organizer); 120 s stays for the agent loop | Q3 A |
| Context | No `num_ctx` sent; Ollama default (4096 on the probe laptop); batches capped at 10 notes and 6,000 characters of note text | Q5 A |
| Retries | None (`max_retries=0`, AL-8) | U1 |

Rejected: `json_object` only (Q1 C, weaker shape guarantee with no gain); a fallback call (Q1 B, a retry against AL-8); thinking on (Q2 B, every batch over the limit on this laptop); a thinking setting (Q2 D, more UI for no current need); smaller batches at 120 s (Q3 B, changes Functional Design and doubles calls).

## 2. Runtime (reused)

| Area | Choice | U3 use |
|---|---|---|
| Language | Python 3.12+ | all code |
| Web | FastAPI, uvicorn, Jinja2, htmx 2.0.4 | organize buttons, review fragments, overview counts |
| Validation | Pydantic v2 (`extra="forbid"` for edits; reply items checked by OR-V rules) | `OrganizerReply`, edit model |
| Database | `sqlite3` direct in the event loop, one `BEGIN IMMEDIATE` transaction per batch save and per review action | `note_suggestions` table |
| Jobs | U1 `JobRunner`, one `organize` job | |
| Not added | `jsonschema`, `instructor` or any structured-output library (Q11 A) | |

## 3. Testing (reused)

| Decision | Value |
|---|---|
| Runner | pytest, pytest-cov (≥ 80% on U3 modules), FastAPI `TestClient` |
| PBT framework | Hypothesis (PBT-09, U1) |
| Profiles | `default` 100, `ci` 500, `print_blob=True`, `deadline=None`, seed in the pre-merge run; no new profile |
| Stateful test | `RuleBasedStateMachine` with `stateful_step_count=30` (P-O4) |
| Strategies | shared `tests/strategies.py`: reply items, mutations, status mixes, action sequences |
| Fake model | `FakeLLMClient` (U1), extended to record `reasoning_effort` and `response_format` |
| Lint / types | ruff, mypy strict |

## 4. Dependency versions

No change. `pyproject.toml` keeps lower bounds; `uv.lock` stays the source of exact versions. `reasoning_effort` is an argument of `chat.completions.create` in the locked `openai` SDK; the probe passed it through the project's `.venv` without error (run 6).

## 5. Logging

U1 setup (`logging`, console, key=value, `TRIP_JOURNAL_LOG_LEVEL`). U3 adds the batch, run and review-action lines in `nfr-requirements.md` §6.
