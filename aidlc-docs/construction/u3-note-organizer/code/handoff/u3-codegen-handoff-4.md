# U3 code generation hand-off 4 (steps 10-11)

Summary: steps 10 and 11 done and ticked in the plan. All four checks pass:
pytest 331 passed (baseline 300, +31), ruff check clean, ruff format clean, mypy --strict clean.
Nothing committed. Not written: code-summary.md, PROMPT_LOG. Audit entry 2026-11-27T14:43:43Z.

## Files
- NEW `trip_journal/services/organizer.py` (ADDED [PROMPT #25])
- NEW `tests/unit/test_organizer_service.py` (21 tests, T-O1..T-O10 and more)
- NEW `tests/unit/test_suggestions_repo.py` (9 tests)
- CHANGED `trip_journal/domain/views.py`, `trip_journal/services/trips.py` (CHANGED [PROMPT #25])
- CHANGED `tests/unit/test_trips_service.py`: summary dict gains `pending_suggestions: 0`;
  new test `test_note_follows_effective_stop_and_pending_count` (D-10, IC-2, IC-3).

## New decisions
- D-24: `start()` order is 404 check -> busy check (`jobs.running`) -> pick notes -> nothing to send
  returns `OrganizeStart(job=None, 0, 0)` -> model probe (`llm.status()`, 503 if not ok) -> job.
  So "nothing to send" never gives 503, and busy never probes the model.
- D-25: a DB error while saving a batch fails the job; only that batch's transaction is rolled back,
  earlier batches stay saved.
- D-26: added `get_view(sid)` and `list_for_day(trip_id, day)` for the step 13 GET route.
- D-27: a pending (or rejected) row does not move the note; only accepted / edited rows use
  `effective_stop_id` (OR-S2). Effective stop None -> "Other notes" when `note.local_date == day`.
- D-28: `TripService._load` reads suggestions once per trip read (`list_for_trip`), N-6 budget.

## Facts for steps 12-13
Constructor:
```
OrganizerService(repos: Repositories, jobs: JobRunner, settings: SettingsService,
                 trips: TripService, llm_factory: Callable[[Settings], LLMClient],
                 prompts: PromptLibrary, call_timeout_s: float = ORGANIZER_CALL_TIMEOUT_S)
```
Methods:
- `async start(trip_id, day: str | None = None) -> OrganizeStart`
- `accept(sid) / reject(sid) / undo(sid) -> SuggestionView`
- `edit_and_accept(sid, raw: Mapping[str, Any]) -> SuggestionView` (runs `check_edit` itself)
- `accept_all(trip_id, day) -> int`
- `get_view(sid) -> SuggestionView`, `list_for_day(trip_id, day) -> list[SuggestionView]`
- `JOB_KIND = "organize"`; job result model is `OrganizerRunSummary` (domain/organizer.py).

`OrganizeStart(BaseModel)`: `job: JobRef | None`, `notes_to_send: int`, `batches: int`.
Lives in `services/organizer.py` (D-17/D-23).

Errors raised:
| case | error | http | code |
|---|---|---|---|
| unknown trip / day | NotFoundError | 404 | trip_not_found / day_not_found |
| unknown suggestion | NotFoundError | 404 | suggestion_not_found |
| a job is running | ModelBusyError | 429 | model_busy (plan step 13 text says 409; check against U1 convention) |
| model not ready | ModelUnavailableError(status) | 503 | |
| action not allowed from status | SuggestionStateError(status) | 409 | suggestion_state |
| invalid edit | SuggestionEditError(issues: dict[str, str]) | 422 | invalid_edit |
| job: timeout before any ok batch | JobTimeoutError(limit_s) | job failed | |
| job: every batch failed | ModelCallError("error") | job failed | model_error |

View fields (domain/views.py):
- `NoteItem` adds `organized: OrganizedFields | None`, `suggestion: SuggestionView | None`,
  `review_status: SuggestionStatus | None`, `suggestion_id: int | None` (all default None).
- `StopTimelineItem.organized` removed (D-9).
- `DaySummary.pending_suggestions: int = 0`.

Open for later: templates or API tests that read `stop.organized` will need updating (not read here).
