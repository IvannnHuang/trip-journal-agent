# U1 Foundation — Code Generation Plan

**Unit**: U1 Foundation (monolith package `trip_journal/`, see `inception/application-design/unit-of-work.md`)
**Stories**: US-17 (place lookup), US-18 (model and Ollama address on the Settings page), US-19 (keep working when Ollama is down / model missing / fails mid-job), US-20 (clear result when the agent cannot finish: tool errors, step limit) — foundation parts only; trip import, journal and Q&A screens belong to U2/U3. (Labels corrected during Part 2 to match `stories.md`.)
**Inputs**: `construction/u1-foundation/functional-design/*`, `nfr-requirements/*`, `nfr-design/*`, `inception/application-design/{unit-of-work,component-methods}.md`.
**Status**: Part 1 approved by the owner ("批准，含下载"). Part 2 (generation) done; all 29 steps ticked. Build and Test not started.

## Deviations from the generic rule-file layout (for approval)

| # | Item | Plan | Reason |
|---|---|---|---|
| D-1 | Code layout | Single package `trip_journal/` + `tests/` at the workspace root, not `src/{unit}/` | Matches `unit-of-work.md` (one deployable monolith, units are folders inside it) |
| D-2 | `.gitignore` | Add `.hypothesis/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.coverage`, `htmlcov/` | NP-8 requires `.hypothesis/` ignored; the others are tool caches |
| D-3 | `htmx.min.js` | Vendored file in `trip_journal/pages/static/`; one download (htmx 2.0.4 from unpkg, ~50 KB) **only with owner permission**; never loaded from a CDN at runtime | Tech-stack decision: no CDN; downloading a file needs explicit permission |
| D-4 | Version pins | `pyproject.toml` lower bounds = versions uv resolves today; exact versions only in `uv.lock` | Verify, not recall (tech-stack-decisions.md) |
| D-5 | `data/` path clash | `.gitignore` line `data/` also matches `trip_journal/data/`. Change it to `/data/` (root only) so the package folder is tracked | Found with `git check-ignore`; without this the data layer would never be committed |
| D-6 | Extra small modules | `api/deps.py` (AppState, `get_state`, `JobView` registry) and `pages/render.py` (Jinja setup, `render_page` / `render_fragment`) | Keeps route files thin; units U2/U3 register their job views here |
| D-7 | Extra partial | `_partials/status_panel.html` (model status panel, also returned for `HX-Request` on `/api/settings/model-status`) | One template for page and htmx refresh |
| D-8 | `/` route | `/` redirects (307) to `/settings` | U1 has no trip list yet; U2 replaces it |
| D-9 | Base URL path | Only an empty path, `/` or `/v1` is accepted; other paths are rejected, not rewritten | Safer than silently dropping a user path (SE-3) |
| D-10 | Test helpers in app code | `JobRunner.wait(job_id)`; `SettingsRepository.set_many`; `TripRepository.counts`; `PlaceLookup.lookup(..., stop_id=)`; `find_by_coordinates` rounds in Python | Needed by tests and by U2/U3 callers; no behaviour change for users |
| D-11 | Bug found by PBT | `split_terms` treats NUL (U+0000) as whitespace | P-Q1/P-Q2 found SQLite errors / match-all on NUL in a query |

## Steps

### A. Project setup
- [x] 1. `pyproject.toml` (project `trip-journal-agent`, Python `>=3.12`, deps: fastapi, uvicorn, pydantic, jinja2, openai, httpx, python-multipart; dev group: pytest, pytest-cov, pytest-asyncio, hypothesis, ruff, mypy); ruff + mypy + pytest + coverage config; `uv sync`; fill lower bounds from `uv.lock` (D-4)
- [x] 2. `.gitignore` updates (D-2, D-5)
- [x] 3. Package skeleton: `trip_journal/__init__.py` and sub-package `__init__.py` files

### B. Core: config, logs, errors
- [x] 4. `trip_journal/config.py` — LC-1 constants (timeouts, limits, defaults, env names, `NOT_IN_RECORDS`, User-Agent)
- [x] 5. `trip_journal/logs.py` — NP-7: `setup_logging()`, `current_job_id` ContextVar + Filter, `kv()`, `TRIP_JOURNAL_LOG_LEVEL` fallback with `log.level_invalid`
- [x] 6. `trip_journal/services/errors.py` — exception classes, `UserFacingError`, ER-1 fixed wording, ER-3 suffix, `to_user_facing()`, `status_message()`

### C. Data layer
- [x] 7. `trip_journal/data/schema.sql` — U1 section: trips, stops, notes, photos, `notes_fts` (trigram) + triggers, settings, place_cache, indexes
- [x] 8. `trip_journal/data/db.py` — `connect(path)` (foreign_keys ON, row_factory), `init_schema()`
- [x] 9. `trip_journal/data/repositories.py` — Trip (`known_citation_ids`), Stop (`list_by_day`, `get`, `find_by_coordinates`), Note (`by_stop`, `search` SN-1..SN-6), Photo (`find_between`), Settings, PlaceCache repositories; small `insert_*` helpers used by tests (U2 import will reuse them)

### D. Domain
- [x] 10. `trip_journal/domain/grounding.py` — GR-1..GR-7: `split_sentences`, `extract_citations`, `check_text`, `find_unsupported_sentences`, `Citation`, `SentenceCheck`

### E. Agent
- [x] 11. `trip_journal/agent/llm.py` — `ToolCall`, `LLMReply`, `LLMClient` Protocol, `OllamaClient` (AsyncOpenAI, `max_retries=0`, timeout 120), `FakeLLMClient` (script, `calls`, optional delay)
- [x] 12. `trip_journal/agent/tools.py` — arg models (`extra="forbid"`), views, TR-1 `wrap_tool_result` / `unwrap_tool_result`, five tools, `ToolContext`, `ToolRegistry`, `default_registry()` (TA-1..TA-10)
- [x] 13. `trip_journal/agent/loop.py` — `AgentLoop` AL-1..AL-11, NP-1 per-call timeout, `<think>` stripping, `not_run` on step 8, callback isolation, `ToolCallRecord`, `AgentResult`
- [x] 14. `trip_journal/agent/prompts/__init__.py` + `_shared_tool_data.md` — `PromptLibrary(directory)`, `get`, `version`

### F. Places
- [x] 15. `trip_journal/places/lookup.py` — `cache_key()` (PL-1), `RateLimiter` (NP-4, injectable clock/sleep), `PlaceLookup` PL-2..PL-9 (no network in tests: httpx `MockTransport`)

### G. Services
- [x] 16. `trip_journal/services/settings.py` — SE-1..SE-7: `Settings`, `SettingsUpdate`, validators (`validate_model`, `normalize_base_url`, `parse_bool`), `SettingsService.get/update/model_status` (NP-3 probe)
- [x] 17. `trip_journal/services/jobs.py` — JB-1..JB-8: `JobRunner`, `JobRef`, `JobStatus`, `JobProgress`, ring of 20 finished jobs, NP-1 job timeout, logs `job.*` with job_id context

### H. Web
- [x] 18. `trip_journal/main.py` — `create_app()` (dependency wiring, startup schema init), `run()` binding 127.0.0.1, uvicorn `log_config=None`
- [x] 19. `trip_journal/api/settings.py`, `trip_journal/api/jobs.py` — JSON routes (422 / 404 / HX-Request fragment)
- [x] 20. `trip_journal/pages/settings.py` + templates (`base.html`, `settings.html`, `_partials/{model_banner,job_progress,trace,error,citations}.html`) + `static/{htmx.min.js,app.css}` (D-3), `data-testid` on interactive elements

### I. Tests (no network, no Ollama)
- [x] 21. `tests/conftest.py` (Hypothesis profiles `default`/`ci`, tmp DB fixture, app client fixture) + `tests/strategies.py` (shared domain generators)
- [x] 22. Unit tests: `tests/unit/` (config, logs, errors, db/repositories, search, grounding examples, settings, places, jobs)
- [x] 23. Agent tests: `tests/agent/` (loop with FakeLLMClient, tools, prompts)
- [x] 24. API/page tests: `tests/api/` (FastAPI TestClient; settings JSON + form, model-status JSON + fragment, jobs 404, fragment rendering)
- [x] 25. Property tests: `tests/property/` (see PBT mapping below)
- [x] 26. Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy trip_journal`, `uv run pytest --cov`, then `HYPOTHESIS_PROFILE=ci` run with a fixed seed; fix until green; record real results

### J. Docs and records
- [x] 27. Code summaries in `aidlc-docs/construction/u1-foundation/code/` (`code-summary.md`: files, public API, test results, deviations)
- [x] 28. `PROMPT_LOG.md` entry `## 13`; `[PROMPT #13]` ADDED / CHANGED tags in code
- [x] 29. Update `aidlc-state.md` (Code Generation for U1 done; Build and Test not started), append audit.md, show the standard completion message

## Test list

| Area | File | Checks (main) |
|---|---|---|
| Logs | `tests/unit/test_logs.py` | format with `job_id=-`, ContextVar inside a job, invalid level → INFO + warning, `kv` quoting; **marker note text never in any log line** (caplog) |
| Errors | `tests/unit/test_errors.py` | ER-1 exact wording per code, ER-3 suffix, HTTP codes, `status_message` |
| DB | `tests/unit/test_repositories.py` | schema creates, FK cascade, FTS triggers on insert/update/delete, `known_citation_ids`, `find_by_coordinates`, `find_between` inclusive |
| Search | `tests/unit/test_search.py` | FTS path (bm25), LIKE path for short terms, `%`/`_`/`\` escaping, quotes in query, limit |
| Grounding | `tests/unit/test_grounding.py` | headings checked, Chinese punctuation, citation after punctuation, unknown ids, `NOT_IN_RECORDS` exemption on/off |
| Settings | `tests/unit/test_settings.py` | resolution order, invalid level skipped + warning, URL rules, atomic `update`, status probe via httpx MockTransport (installed / missing / `:latest` / unreachable / 2 s timeout) |
| Places | `tests/unit/test_places.py` | import name no network, lookup off, cache hit, miss → request + cache, failure not cached, `display_name` fallback, rate limiter spacing with fake clock |
| Jobs | `tests/unit/test_jobs.py` | start/busy 429, progress steps, success/failure/timeout states, ring of 20, unknown id 404, job_id in logs |
| Loop | `tests/agent/test_loop.py` | final answer, tool round-trip, unknown tool, invalid args, step limit + `not_run`, missing call id, `<think>` strip, model timeout / error, callback exceptions ignored |
| Tools | `tests/agent/test_tools.py` | each tool happy path, foreign stop_id, record cap 50, note truncation, error envelope, TR-1 format |
| Prompts | `tests/agent/test_prompts.py` | `get`, missing prompt, `version` changes when a file changes |
| API | `tests/api/test_settings_api.py`, `test_jobs_api.py`, `test_pages.py` | 200/422/404, HX-Request fragment, settings page renders banner + form with `data-testid`, trace partial empty text |

## PBT mapping (blocking rules PBT-02 / 03 / 07 / 08 / 09)

| Rule | What it requires | Covered by (business-rules.md §10) | Test file |
|---|---|---|---|
| PBT-02 Round-trip | encode → decode returns the input | P-G3 (split then join keeps text), P-S4 (save → get settings), P-T1 (wrap → unwrap tool result, incl. `<` and non-ASCII), P-K1 (cache key → float → key stable) | `test_grounding_props.py`, `test_settings_props.py`, `test_tool_result_props.py`, `test_cache_key_props.py` |
| PBT-03 Invariants | properties that hold for all inputs | P-G1/G2/G4/G5/G6/G8 (citation extraction oracle, supported ⇔ rule, metamorphic: adding a known citation never makes a sentence unsupported), P-G7 + P-S3 idempotence, P-K2/K3 (key format, −0 normalised), P-T2..T4 (cap 50, truncation length, error envelope), P-Q1/Q2 (search never raises on any text, results ⊆ trip notes) | same files + `test_search_props.py` |
| PBT-07 Shared generators | domain strategies in one place | `tests/strategies.py`: trips/stops/notes, citation-bearing text, model names, base URLs, coordinates, tool payloads | used by all property files |
| PBT-08 Shrinking + reproducibility | failures shrink, seed printed | `print_blob=True`, `deadline=None`, profiles `default` (100) / `ci` (500), `--hypothesis-seed` in the run command; no `assume`-heavy filters | `tests/conftest.py` |
| PBT-09 Framework | Hypothesis as dev dependency | `hypothesis` in the uv dev group, locked in `uv.lock` | `pyproject.toml` |
| (advisory) | stateful | P-J1 JobRunner state machine (`RuleBasedStateMachine`): at most one running, ≤ 20 finished, ids unique | `test_jobs_stateful.py` |

## Success criteria
1. ruff + mypy clean; all tests pass under `default` and `ci` profiles.
2. Coverage of `trip_journal/domain` and `trip_journal/agent/tools.py` ≥ 80% (target whole package ≥ 80%).
3. No test opens a network socket or needs Ollama.
4. Every plan step ticked; summaries and records written; Build and Test not started.
