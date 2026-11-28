# U4 Daily Journal - Code Summary

**Stage**: Code Generation (Part 2 done 2026-11-28, awaiting owner approval). Build and Test not started.
**Plan**: `aidlc-docs/construction/plans/u4-daily-journal-code-generation-plan.md` (22/22 steps ticked)
**Who**: Claude wrote the prompts (step 7, D-14) and reviewed and fixed both batches; Codex exec implemented C1 (backend, worktree `codex/u4-backend`) and C2 (frontend, worktree `codex/u4-frontend`). Both were applied to main's working tree as uncommitted patches after owner OK.
**Tag**: new and changed files carry `ADDED [PROMPT #36]` / `CHANGED [PROMPT #36]`.

## Application code (`trip_journal/`)
| Area | Files | Role |
|---|---|---|
| `data/` | `journals.py` (new); `schema.sql`, `repositories.py` (changed) | tables `journals`, `journal_paragraphs`; `JournalRepository` (`get`, `exists`, `save_generated` in one `BEGIN IMMEDIATE`, `save_user_edit`); `Repositories.journals` |
| `domain/` | `journal_merge.py` (new); `views.py`, `grounding.py` (changed) | slots, owners, `merge_journal`, `mark_user_edit`; `SentenceView`, `ParagraphView`, `JournalView`, `CitationTarget`, `NothingToRegenerate`; `DayView.journal_exists`; citation ids capped at 18 digits |
| `agent/` | `journal.py`, `prompts/journal*.md` (6 new); `loop.py`, `prompts/organizer.md` (changed) | chunk plan, step-0 pre-fetch, per-chunk `AgentLoop`, summary call, strict heading parse; `AgentLoop` `reasoning_effort` / `request_timeout_s`; `ToolCallRecord.group`; organizer tip and rating rules |
| `services/` | `journal.py` (new); `errors.py`, `trips.py` (changed) | `JournalService` start / get / edit / citation; new errors `ParagraphTooLongError`, `NoRecordsError`, not-found messages; day badge |
| `api/` | `journal.py` (new); `deps.py` (changed) | JSON + htmx endpoints; `AppState.journal`; `JobView.fresh_context` |
| `pages/` | `journal.py`, `static/journal.js` (new); `render.py`, `settings.py`, `static/app.css` (changed) | page and fragment routes; draft swap, keepalive save, focus moves, panel Escape; `local_time` filter; job fragment merges a fresh read for finished journal jobs |
| templates | `journal/{page,result,status}.html`, `_partials/{citation_panel,journal_body,journal_count,journal_editor,journal_paragraph,journal_trace}.html` (new); `_partials/{day_stops,error,job_progress,note_item,stop_item}.html`, `days/day.html` (changed) | journal page, editor, citation panel, trace; day-page Journal link + badge; CI2 focus hook |
| root | `main.py`, `config.py` (changed) | `JournalService` wiring, `JobView("journal/result.html", fresh_context=...)`, routers; journal constants (300 s per call, cap 1800 s, chunk 6 stops / 4,000 chars, max paragraph 5,000) |

### Endpoints
| Method and path | Result |
|---|---|
| `GET /api/trips/{id}/days/{day}/journal` | `JournalView`; 404 |
| `POST /api/trips/{id}/days/{day}/journal` body `{"tone"}` | 202 job; 200 `nothing_to_regenerate`; 404; 422 `no_records` / bad tone; 429 busy; 503 model |
| `PUT /api/trips/{id}/days/{day}/journal/paragraphs/{slot}` body `{"text"}` | 200 paragraph + `unsupported_count`; 404; 422 (> 5,000 chars) |
| Pages: `GET /trips/{id}/days/{day}/journal`, `/journal/fragment`, `/journal/paragraphs/{slot}/edit`, `/journal/paragraphs/{slot}`, `GET /trips/{id}/citations/{kind}/{cid}` | htmx fragments; 422 bad kind |

## Decisions (D-1..D-16, one line each)
| ID | Decision |
|---|---|
| D-1 | busy stays HTTP 429 (FD "409" was a text slip) |
| D-2 | `AgentLoop` gains optional `reasoning_effort` and `request_timeout_s`; defaults keep U1/U3 callers unchanged |
| D-3 | `ToolCallRecord.group` (`prefetch`, `part n`, `summary`), default `None`; old trace JSON still validates |
| D-4 | prompt = `journal` + tone fragment (+ `journal_summary` for the summary call); `PromptLibrary.get(tone=)` not used |
| D-5 | `JournalRepository` in `data/journals.py`, exposed as `Repositories.journals` |
| D-6 | chunk plan computed before the job so the limit `min(300 × calls, 1800)` is known; test ties plan chars to step-0 results |
| D-7 | step-0 pre-fetch as a synthetic assistant `tool_calls` message plus tool results built by the registry |
| D-8 | per-run grounding: generated paragraphs checked against ids in the stored trace, user paragraphs against trip ids; on read only |
| D-9 | job kind `journal`; `JobView("journal/result.html")`; result carries `#journal-body` and "Draft ready" |
| D-10 | `DayView.journal_exists` via one `exists` query |
| D-11 | `pages/static/journal.js`, no build step; everything else is htmx |
| D-12 | notes without a stop are not pre-fetched (**open item**, see below) |
| D-13 | progress texts: BL-9 for one chunk, U4-NFR-U.1 texts for chunked runs |
| D-14 | organizer tip quoted from the note (original language allowed); rating example "9/10 becomes 5" |
| D-15 | days with > 50 stops: no pagination (**known limit**, see below) |
| D-16 | rows for stops no longer in the day are hidden on read, not deleted; citation ids ≤ 18 digits; `start_generation` re-checks BL-1 steps 1-4 after the model-status await |

## Review fixes by Claude
- C1: the three D-16 fixes (from a Codex read-only review of the save transaction: atomic, no await inside it, no XSS found).
- C2, R1: a finished journal job's poll fragment renders a fresh `get_journal` (`JobView.fresh_context`, `pages/journal.py` `finished`), so an edit saved after the job ends shows; test added by Codex.
- C2, R2: exactly one `|safe`, on `sentence.text_html` (already escaped by `sentence_html`); no `innerHTML`; `<script>` in notes and edits shows escaped in page, editor, panel and trace (tests).
- C2 fixes: draft swap no longer moves focus out of a kept editor; editor caret goes to the end; editor textarea full width; two tests added (running-journal first progress text, failed journal job keeps its trace and saves nothing).

## Open item and known limit
- **D-12 (open)**: notes not attached to a stop are not pre-fetched; the model sees them only if it calls `search_notes`. Owner kept this non-blocking; revisit if the smoke check shows missed notes.
- **D-15 (known limit)**: `list_day_stops` keeps the U1 50-record cap, so on a day with more than 50 stops, stop citations past the cap may show as unsupported in generated paragraphs. U4 envelope is ≤ 50 stops/day (reference trip ~21).

## Tests
| Check | Result (main working tree, 2026-11-28) |
|---|---|
| `pytest --cov=trip_journal` | 427 passed, 4 deselected; total coverage 98% (agent/journal.py 99%, services/journal.py 98%, api/journal.py 93%, data/journals.py and domain/journal_merge.py covered by unit and property tests) |
| `HYPOTHESIS_PROFILE=ci pytest tests/property` | 42 passed (P-1..P-8, PBT-02 round trip) |
| `ruff check`, `ruff format --check`, `mypy --strict trip_journal tests` | clean |
| Browser (FakeLLM demo data) | page, citation buttons, unsupported mark, citation panel + Escape focus return, editor autosave "Saved", Done focus return, trace groups incl. "prefetch (loaded by the app)", day badge "drafted": all pass |

New test files: `tests/unit/test_journal_{merge,parse,chunks,prompt,agent,repo,service,review_fixes}.py`, `tests/property/test_journal_props.py`, `tests/api/test_journal_{api,pages}.py`. Changed: `tests/agent/test_loop.py`, `tests/conftest.py`, `tests/strategies.py`, `tests/api/test_{organizer,trip}_pages.py`, `tests/unit/test_organizer_{parse,prompt}.py`.

## Carried to Build and Test
- Reloading the page while a journal job runs shows no progress and leaves Write enabled (outside the FD; decide fix or accept).
- `journal.js` behaviour has no automated test: browser checks from FD §5 (draft swap with a dirty editor, keepalive save, focus moves).
- Nit: "1 unsupported sentences" (matches the FD string "N unsupported sentences").
- From the plan: manual quality smoke check (U4-NFR-G.3), speed P.4 and P.7, U3 18-note smoke re-run (JR-CI1). Manual runs use `TRIP_JOURNAL_PORT` (8765 is in use by another local app on this laptop).
- Worktrees `../trip-journal-agent-wt/u4-backend` and `u4-frontend` kept until the owner OKs removing them.
- pytest in main reported 1 warning (not seen in the worktree run, not reproduced in tests/api, unit, agent); identify it during Build and Test.
