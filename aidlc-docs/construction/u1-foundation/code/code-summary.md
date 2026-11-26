# U1 Foundation - Code Summary

**Stage**: Code Generation (Part 2 done 2026-11-26). Build and Test not started.
**Plan**: `aidlc-docs/construction/plans/u1-foundation-code-generation-plan.md` (29/29 steps ticked)
**Tag**: every new file carries `ADDED [PROMPT #13]`; the one bug fix carries `CHANGED [PROMPT #13]`.

## Application code (`trip_journal/`)
| Package | Files | Role |
|---|---|---|
| root | `config.py`, `logs.py`, `main.py` | constants and limits; key=value logs with `job_id`, no note/journal/prompt text; FastAPI app factory, binds 127.0.0.1 |
| `data/` | `db.py`, `repositories.py` | SQLite schema + FTS5; repositories for trips, stops, notes, photos, places, settings; `split_terms` |
| `domain/` | `grounding.py` | sentence split, citation parse, unsupported-sentence check |
| `agent/` | `llm.py`, `loop.py`, `tools.py`, `prompts/` | OpenAI-compatible Ollama client (120 s per call, max_retries=0); tool loop with step limit and trace; 5 read-only tools with `<tool_result>` envelope; shared prompt text + versioning |
| `places/` | `lookup.py` | Nominatim lookup, 1 req/s lock, 5 s timeout, 4-decimal cache key |
| `services/` | `errors.py`, `jobs.py`, `settings.py` | error kinds; background job runner (5 min limit, keeps last finished jobs); settings with localhost-only base URL |
| `api/` | `deps.py`, `jobs.py`, `settings.py` | JSON + htmx fragment endpoints for jobs, settings, model status |
| `pages/` | `render.py`, `settings.py`, `templates/`, `static/` | Settings page, banners (Ollama down, model missing), partials; vendored htmx 2.0.4 |

## Tests (`tests/`)
- `unit/` (8 files), `agent/` (3), `api/` (3), `property/` (6), plus `conftest.py`, `strategies.py`.
- No network, no Ollama: `httpx.MockTransport`, fake LLM client, in-memory SQLite.
- PBT: round trips P-G3, P-S4, P-T1, P-K1; invariants P-G1/2/4/5/6/8, P-K2/3, P-T2..T4, P-Q1/Q2; idempotence P-G7, P-S3; stateful P-J1 (JobMachine).

## Results (2026-11-26, Windows laptop, Python 3.13.14)
| Check | Result |
|---|---|
| `uv run pytest --cov=trip_journal` | 154 passed, 1 warning, 55.8 s; coverage 95% (lowest: `pages/render.py` 65%, `agent/llm.py` 75%) |
| `HYPOTHESIS_PROFILE=ci pytest tests/property --hypothesis-seed=12345` | 22 passed, 235.9 s |
| `ruff check` / `ruff format --check` on `trip_journal tests` | clean |
| `mypy --strict` on `trip_journal tests` | clean (54 files) |

## Deviations (see plan D-1..D-11)
- D-6..D-10: small helper modules and test hooks (`deps.py`, `render.py`, `status_panel` partial, `/` redirect, base URL path rule, `JobRunner.wait` etc.).
- D-11: PBT found that a NUL character in a search query broke SQLite (FTS "unterminated string", LIKE matching every note). `split_terms` now treats NUL as whitespace; regression test `test_nul_character_is_whitespace`.

## Notes and known gaps
- openai 3.60 annotates its errors with `httpx2.Response`; one test passes an `httpx.Response` (works at runtime, `type: ignore[arg-type]` with a comment).
- `scripts/model_spike.py` (earlier spike, out of scope) has 4 ruff E501 errors, so `ruff check .` on the whole repo fails; `trip_journal` and `tests` are clean.
- Not verified: real Ollama run, real Nominatim call, the page in a real browser, and Ollama stopping after a cancelled request (`ollama ps`). These belong to Build and Test.
