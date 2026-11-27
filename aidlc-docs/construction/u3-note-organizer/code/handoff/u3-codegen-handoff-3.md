# U3 Code Generation Part 2 (a): hand-off 3 (2026-11-27)

**Status:** steps 7-9 done and ticked. Steps 10-13 are NOT started. This session hit context compaction and stopped at a clean step, as the brief says.
**Checks:** pytest 300 passed, 3 deselected (baseline 276, +24 new). ruff check, ruff format --check and mypy --strict on trip_journal + tests are all clean.
**Not done:** no commit. code-summary.md and PROMPT_LOG were not written (brief). Steps 16 and 17 are not ticked.

## Files
- NEW `trip_journal/domain/organizer.py`: models, field rules, `check_edit`, `cut_note_text`, `plan_batches`, view helpers. Tag `ADDED [PROMPT #25]`.
- NEW `trip_journal/agent/prompts/organizer.md`: system prompt. It has no tag comment, because the file is model-facing text and a tag would go into the prompt and change `PromptLibrary.version()`.
- NEW `trip_journal/agent/organizer.py`:
  - `make_labels`, `escape_note`, `build_user_message`, `build_messages`, `failed_batch`, `parse_reply`;
  - `NoteOrganizer(llm, prompts, call_timeout_s=240).organize_batch(batch) -> OrganizerBatchResult`;
  - `RESPONSE_FORMAT` is a json_schema built from `OrganizerReply`.
- CHANGED `agent/prompts/__init__.py`: `PromptLibrary.get(name, tone=None, shared=True)` (D-15).
- ADDED `data/repositories.py`: `NoteRepository.get(trip_id, note_id) -> NoteRow | None` (D-18).
- NEW `tests/unit/test_organizer_parse.py`: 24 tests. It covers the field rules, `check_edit`, `cut_note_text`, `plan_batches` (hypothesis), the user-message layout and escaping, the system prompt without the shared text, `parse_reply` (OR-V1..V5 drop reasons, failed outcomes, never raises (hypothesis)) and `organize_batch` (one call; schema, effort and timeout are recorded; `model_error`; `call_timeout`; cancel propagates).
- Test files still open:
  - `test_organizer_batches.py`, `test_organizer_prompt.py` and `test_organizer_call.py`: their content is mostly in `test_organizer_parse.py`. Split the file or keep it, and note which in code-summary.
  - `test_suggestions_repo.py`
  - `test_organizer_service.py`
  - `tests/api/test_notes_api.py`
- No strategies were added to `tests/strategies.py` yet (step 16). The tests use local helpers `stop()`, `note()`, `item()`, `reply()`.

## New decisions
- **D-21:** `domain.organizer.check_edit(raw, stop_ids) -> (SuggestionEdit | None, dict[field, message])` returns its issues and does not raise. The service raises `SuggestionEditError(fields)`, so the domain does not import services. Messages:
  - "unknown field"
  - "category is required"
  - "category 'x' not allowed"
  - "rating must be a whole number"
  - "rating N outside 1-5"
  - "dish longer than 80 characters"
  - "tip longer than 200 characters"
  - "stop is not one of this day's stops"
- **D-22 (planned, not done):** `api/trips.py error_response(exc)` should add `body["fields"] = exc.fields` for `SuggestionEditError`.
- **D-23:** `OrganizeStart` stays in `services/organizer.py` (D-17), even though plan step 7 lists it in the domain.

## Facts for steps 10-13 and for part (b)
- **Domain names** (`trip_journal.domain.organizer`):
  - Types and constants: `Category`, `CATEGORIES`, `SuggestionStatus`, `BatchOutcome`, `DISH_MAX=80`, `TIP_MAX=200`, `PREVIEW_CHARS=60`, `NO_STOP_LABEL="No stop"`, `UNNAMED_STOP="Unnamed place"`, `EDIT_FIELDS`.
  - Models:
    - `NoteSuggestion(note_id, category, suggested_stop_id, dish, rating, tip)`
    - `DroppedItem(note_label, note_id, reason)`
    - `OrganizerBatchResult(suggestions, dropped, not_organized: list[int], outcome)`
    - `BatchInput(day, stops: tuple[StopRow,...], notes: tuple[NoteRow,...])`, a frozen dataclass
    - `NotOrganized(note_id, local_time, preview, reason)`
    - `DayRunResult(day, notes_sent, suggested, not_organized, dropped, failed_batches)`
    - `OrganizerRunSummary(trip_id, scope_day, days, total_suggested, total_not_organized, batches, batches_failed, skipped_decided, prompt_version, model_name, stopped=None, remaining_notes=0)`
    - `SuggestionValues`
    - `OrganizedFields(suggestion_id, category, stop_id, dish, rating, tip, edited)`
    - `SuggestionView(suggestion_id, trip_id, local_date, note_id, note_source_id, status, category, stop_id, stop_source_id, stop_label, dish, rating, tip, model_values)`
    - `SuggestionEdit` (extra="forbid")
  - Helpers: `model_values(row)`, `effective_values(row)` (f_* when edited), `organized_fields(row)` (None unless accepted or edited), `stop_label(stop)`, `suggestion_view(row, note, stops_by_id)`.
- **Batching:** `plan_batches(notes)` returns `list[list[NoteRow]]` in time order, closing a batch at 10 notes or at 6,000 characters of cut text. Each `BatchInput` carries all the day's stops.
- **Step 10 shape** (from the summary, not yet written):
  - `OrganizeStart(job: JobRef | None, notes_to_send, batches)`.
  - `OrganizerService(repos, jobs, settings, trips, llm_factory, prompts)` with:
    - `start(trip_id, day | None)`, which checks readiness with `llm.status()` on the factory-built client (D-20);
    - `accept`, `reject`, `edit_and_accept(sid, raw)`, `undo`: each returns a `SuggestionView`;
    - `accept_all(trip_id, day) -> int`.
  - Each batch is saved with `save_batch(..., commit=False)` inside `BEGIN IMMEDIATE`, committed per batch.
  - Inner deadline as D-13. `timeout_s = min(300 × batches, 1800)`.
  - Log lines go through `logs.kv` (`organizer.batch`, `organizer.run`, `organizer.review`).
- **Step 11:**
  - Remove `StopTimelineItem.organized` (D-9).
  - `NoteItem` gains `organized`, `suggestion`, `review_status` and `suggestion_id`.
  - A note's placement follows its effective stop (D-10).
  - `DaySummary` gains `pending_suggestions: int = 0`.
- **Step 12:** add `AppState.organizer` and `AppState.llm_factory`, set `job_views["organize"] = JobView("organizer/summary.html", retry_url)`, include the `api/notes` router, and give `create_app` an `llm_factory` keyword argument (D-1).
- **Step 13 routes:**

  | Method | Path | Result |
  |---|---|---|
  | POST | `/api/trips/{id}/organize` | 202 with job; 200 `job_id: null` + message; 503 / 409 / 404 / 429 |
  | GET | `/api/trips/{id}/days/{date}/suggestions` | |
  | POST | `/api/suggestions/{sid}/accept` | |
  | POST | `/api/suggestions/{sid}/reject` | |
  | POST | `/api/suggestions/{sid}/undo` | |
  | PUT | `/api/suggestions/{sid}` | 422 `invalid_edit` with `fields` |
  | POST | `/api/trips/{id}/days/{date}/suggestions/accept-all` | `{"accepted": n}` |

  An invalid date gives 422 `invalid_date`, via `is_valid_day`.
- **Test setup:** FakeLLMClient records `calls`, `tools_seen`, `response_formats`, `reasoning_efforts` and `timeouts`. `status_value` drives the 503 path.

## Next step
Start a fresh sub chat for steps 10-13, together with the step 16 strategies and the step 17 service / API tests. Its first step is to write `services/organizer.py` and `test_organizer_service.py`.
