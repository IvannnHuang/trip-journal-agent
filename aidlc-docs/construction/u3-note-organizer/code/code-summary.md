# U3 Note Organizer - Code Summary

**Stage**: Code Generation (Part 2 done 2026-11-27, awaiting owner approval). Build and Test not started.
**Plan**: `aidlc-docs/construction/plans/u3-note-organizer-code-generation-plan.md` (22/22 steps ticked)
**Tag**: new and changed files carry `ADDED [PROMPT #25]` / `CHANGED [PROMPT #25]` (all U3 code steps were done under that prompt; PROMPT_LOG #26 onward log the later steps).

## Application code (`trip_journal/`)
| Area | Files | Role |
|---|---|---|
| `data/` | `suggestions.py` (new), `schema.sql`, `repositories.py` (changed) | table `note_suggestions` (one row per note: model values, edited values, status pending/accepted/edited/rejected); `SuggestionRepository`; `NoteRepository.get` |
| `domain/` | `organizer.py` (new), `views.py` (changed) | suggestion types, edit and reply validation, batching rules; `NoteItem.organized/.suggestion/.review_status`, `DaySummary.pending_suggestions` |
| `agent/` | `organizer.py`, `prompts/organizer.md` (new), `llm.py`, `prompts/__init__.py` (changed) | batch call with `json_schema` output and `reasoning_effort="none"`, strict parsing; per-call `timeout_s` |
| `services/` | `organizer.py` (new), `jobs.py`, `errors.py`, `trips.py` (changed) | start order 404 -> busy -> pick notes -> nothing to send -> model probe -> job; per-batch save; review actions; limit-aware job timeout; new errors; suggestion-aware day view |
| `api/` | `notes.py` (new), `deps.py` (changed) | JSON endpoints (below) |
| `pages/` | `notes.py` (new; the hand-offs also call it `pages/organizer.py`), `days.py`, `trips.py`, `render.py`, `static/app.css` (changed) | htmx review pages |
| templates | `_partials/{accept_all,day_stops,note_item,organizer_bar,organizer_job,photo_line,suggestion_edit}.html`, `organizer/` (new); `_partials/stop_item.html`, `days/day.html`, `trips/{list,overview}.html` (changed) | review rows, job area, summary |
| root | `main.py`, `config.py` (changed) | `llm_factory`, organizer constants, router wiring |

### Endpoints
| Method and path | Result |
|---|---|
| `POST /api/trips/{id}/organize` body `{"day": date or null}` | 202 job; 200 `job_id: null` when nothing to send; 503 model; 409; 404; 429 busy |
| `GET /api/trips/{id}/days/{date}/suggestions` | suggestion views |
| `POST /api/suggestions/{sid}/accept`, `/reject`, `/undo` | view; 409 `suggestion_state`; 404 |
| `PUT /api/suggestions/{sid}` | edit and accept; 422 `invalid_edit` with `fields` |
| `POST /api/trips/{id}/days/{date}/suggestions/accept-all` | `{"accepted": n}` |
| Pages: `POST /trips/{id}/days/{date}/organize`, `POST /trips/{id}/organize`, `POST /trips/{id}/days/{date}/accept-all`, `POST /suggestions/{sid}/accept` / `reject` / `undo`, `GET` and `POST /suggestions/{sid}/edit`, `GET /suggestions/{sid}/row` | htmx gets `#day-stops` or the row; plain POST gets 303 |

## Decisions (D-1..D-45, one line each)
| ID | Decision |
|---|---|
| D-1 | `create_app(llm_factory=...)`; factory called per organize run; tests pass a fake |
| D-2 | `LLMClient.chat` gains `reasoning_effort` and `timeout_s` (sent only when set) |
| D-3 | organizer per-call limit 240 s (SDK `timeout=` and `asyncio.timeout`), outcome `call_timeout` |
| D-4 | `JobRunner.start(..., timeout_s=None)`; timeout message names the limit used |
| D-5 | busy stays HTTP 429 (the FD's 409 was a text slip) |
| D-6 | new errors `suggestion_not_found`, `SuggestionStateError` 409, `SuggestionEditError` 422 |
| D-7 | one `note_item.html` partial renders every note |
| D-8 | `<section id="day-stops">` wraps timeline and "Other notes"; review actions return it |
| D-9 | `StopTimelineItem.organized` removed; data lives on `NoteItem` |
| D-10 | note shown under its effective stop; `notes.stop_id` never written |
| D-11 | job progress text per FD |
| D-12 | pages module is `pages/notes.py` in code (hand-offs also say `organizer.py`) |
| D-13 | inner deadline in the organizer job work; job limit `min(300 x batches, 1800)` |
| D-14 | `JobTimeoutError` message depends on the limit |
| D-15 | `PromptLibrary.get(..., shared=False)` for the organizer (no shared tool data) |
| D-16 | `SuggestionView` has `trip_id`, `local_date`; review actions return a view, pages re-render the day |
| D-17 | `OrganizeStart` lives in `services/organizer.py` (domain must not import `JobRef`) |
| D-18 | `NoteRepository.get(trip_id, note_id)` added |
| D-19 | duplicate check OR-V5 compares only with items kept for the same note |
| D-20 | `start` checks readiness with `llm.status()` of the factory client |
| D-21 | `check_edit` returns issues instead of raising; service raises `SuggestionEditError` |
| D-22 | API error body adds `fields` for `SuggestionEditError` |
| D-23 | `OrganizeStart` stays in services (see D-17) |
| D-24 | `start()` order: 404 -> busy -> pick notes -> nothing to send -> model probe |
| D-25 | a DB error fails the job; only that batch is rolled back |
| D-26 | repo gains `get_view` and `list_for_day` |
| D-27 | only accepted / edited rows move a note |
| D-28 | `TripService._load` reads suggestions once per trip read |
| D-29 | no retry link; the Organize button stays visible |
| D-30 | busy is 429 `model_busy` |
| D-31 | organize body optional; `day` validated like day routes |
| D-32 | 200 "nothing to send" body shape fixed |
| D-33 | 422 `invalid_edit` body = U1 error body + `fields` |
| D-34 | extra partials: `day_stops`, `organizer_job`, `accept_all` (also OOB), `photo_line` |
| D-35 | plain-form organize / accept-all answer 303 with `?job=`, `?nothing=1`, `?accepted=n`; shared `render_day` / `render_overview` |
| D-36 | error replies swap via `hx-on::before-swap`; 409 retargets `#day-stops`, 422 edit retargets `#note-{id}` |
| D-37 | plain GET edit / 422 shows the full day page with the form open; GET edit on a non-pending row = 409 |
| D-38 | shared test helpers in `tests/fixtures/organizer.py` |
| D-39 | `two_day_trip_bytes()` is the reference multi-day trip |
| D-40 | model labels follow time order (source n6 is label `n4`) |
| D-41 | placement checked by parsing the day page |
| D-42 | app-level properties build a fresh app per example with `review_client(llm)` |
| D-43 | no per-test `max_examples`; U1 profiles rule; P-O4 `stateful_step_count=30` |
| D-44 | re-runs change `LabellingLLM.category`, exercising "re-run replaces pending values" |
| D-45 | perf test copies the reference-trip loader; reply typed with a small `Protocol` |

## Tests (`tests/`)
- New: `unit/{test_organizer_parse,test_organizer_prompt,test_organizer_call,test_organizer_batches,test_organizer_service,test_suggestions_repo}.py`, `api/{test_notes_api,test_organizer_pages}.py`, `property/{test_organizer_props,test_suggestions_stateful}.py` (P-O1..P-O4), `perf/test_review_speed.py` (P.5, slow), `fixtures/organizer.py`.
- Changed: `conftest.py` (`fake_llm`, app client), `strategies.py`, `unit/{test_errors,test_jobs,test_trips_service}.py`, `api/test_trip_pages.py` (CI-1 / CI-2, D-9 / D-10).

## Results (2026-11-27, Windows laptop)
| Check | Result |
|---|---|
| `uv run pytest --cov` | 386 passed, 4 deselected (slow), 1 warning, 190 s; total coverage 97% (U2 was 275 passed, 97%) |
| `HYPOTHESIS_PROFILE=ci pytest tests/property` | 38 passed, 563 s (9 min 23 s; U2 alone was 348 s) |
| `pytest -m slow` | 4 passed, 7.3 s |
| `ruff check` / `ruff format --check trip_journal tests` | clean (96 files formatted) |
| `mypy --strict trip_journal tests` | clean (94 files) |

### U3 module coverage (target >= 80%)
| Module | Coverage | Missing |
|---|---|---|
| `data/suggestions.py` | 100% | - |
| `domain/organizer.py` | 100% | - |
| `agent/organizer.py` | 99% | branch 182->178 |
| `services/organizer.py` | 98% | 379, 404 |
| `api/notes.py` | 95% | 105-106, 115-116 |
| `pages/notes.py` | 94% | 51, 159, 168, 191, 207, 209-210, 261, 274 |

The two 100% modules are not listed in the report (`skip_covered`). No tests were added for coverage.

### Speed P.5 (review action <= 300 ms; busiest reference day 2026-06-13, 166 suggestions, 17 batches)
| Action | ms (step 20 run / step 21 `-m slow -s` run) | Target |
|---|---|---|
| Accept | 130 / 144 | 300 |
| Reject | 79 / 88 | 300 |
| Edit and accept | 84 / 89 | 300 |
| Undo | 79 / 86 | 300 |
| Accept all | 130 / 146 | 300 |

In-process `TestClient`, in-memory SQLite. The same slow run also passed U2 P.1-P.4 (busiest day page 0.119 s).

## Deviations and notes
- No app bugs were found in steps 21-22; app code is unchanged by them.
- `scripts/model_spike.py` still has ruff E501 errors; out of scope and not in the checked paths.
- Owner decisions kept: D-5 (busy is 429, not the FD's 409) and D-29 (no retry link).

## For Build and Test
- Check the day page in a real browser: Organize, progress, review rows, Accept / Reject / Undo, Edit form (422 retarget), Accept all, 409 swap.
- Manual accuracy smoke check with Ollama qwen3:8b using `reasoning_effort="none"`; batch target <= 120 s.
- Re-run P.5 against a file DB over HTTP.
