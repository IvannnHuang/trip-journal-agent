# U3 code generation hand-off 5 (steps 12-13)

Summary: steps 12 and 13 done and ticked in the plan. pytest 335 passed, 3 deselected (+4);
ruff check, ruff format --check, mypy --strict clean. Nothing committed. Audit entry
2026-11-27T15:07:47Z. Not written: code-summary.md, PROMPT_LOG.

## Files
- CHANGED `trip_journal/api/deps.py`: `AppState.organizer: OrganizerService`,
  `AppState.llm_factory: Callable[[Settings], LLMClient]`.
- CHANGED `trip_journal/main.py`: `create_app(..., llm_factory=None)` (D-1; default builds
  `OllamaClient(settings.ollama_base_url, settings.model_name, http=<app client>)` per run),
  builds `OrganizerService(repos, runner, settings, trips, factory, PromptLibrary())`,
  registers `job_views["organize"]`, includes `notes_api.router`.
- NEW `trip_journal/api/notes.py` (router `router`, prefix `/api`, tag `notes`).
- NEW `tests/api/test_notes_api.py` (4 tests; local `make_client(http, llm)` helper builds the app
  with `llm_factory=lambda _s: llm`; step 16 may move it into `conftest.py` as `fake_llm`).

## New decisions
- D-29: `job_views["organize"] = JobView("organizer/summary.html", retry_url=None)`. `JobView`
  is static and the fragment route only knows the job, so no per-trip / per-day retry URL.
  A failed organize job shows the error without "Try again"; the Organize button in the
  organizer bar is the retry. Step 15 should keep that button visible next to the job box.
- D-30: busy (`ModelBusyError`) stays **429 `model_busy`** (U1 domain-entities), not the 409
  in plan step 13 / frontend-components. Settled by approved plan D-5 (main chat, 2026-11-27):
  keep 429; the 409 in step 13 is the review state-machine conflict (OR-ST), not busy.
- D-31: POST organize body is optional (`{}` or no body = whole trip); `day` is checked with
  `api.days.is_valid_day` -> 422 `invalid_date` (same body as the day API). The two day-scoped
  suggestion routes also give 422 `invalid_date` for a malformed date.
- D-32: 200 "nothing to send" body: `{"job_id": null, "kind": null, "notes_to_send": 0,
  "batches": 0, "message": "Nothing to organize: every note already has a decision."}`.
  202 body: `{"job_id", "kind": "organize", "notes_to_send", "batches"}`.
- D-33: 422 `invalid_edit` body = U1 error body + `"fields": {name: message}` (unknown keys
  are reported as fields too, from `check_edit`).

## Facts for steps 14-15
- Pages router: plan step 14 says `pages/notes.py`, handoff-1 says `pages/organizer.py`.
  Pick one and add `app.include_router(<module>.router)` in `main.py` after `notes_api`.
- Service calls (all on `state.organizer`): `await start(trip_id, day|None) -> OrganizeStart`
  (`job: JobRef|None`, `notes_to_send`, `batches`), `accept/reject/undo(sid)`,
  `edit_and_accept(sid, raw_mapping)`, `accept_all(trip_id, day) -> int`, `get_view(sid)`,
  `list_for_day(trip_id, day)`. Re-render a row via `state.trips.get_day(trip_id, day)` (NoteItem
  fields `organized`, `suggestion`, `review_status`, `suggestion_id`).
- Error -> status: NotFoundError 404 (`trip_not_found`, `day_not_found`,
  `suggestion_not_found`); ModelBusyError 429 `model_busy`; ModelUnavailableError 503
  (`ollama_unreachable` / `model_missing` via `to_user_facing`); SuggestionStateError 409
  `suggestion_state`; SuggestionEditError 422 `invalid_edit` with `exc.fields`. Every error
  has `http_status`; `to_user_facing(exc)` gives `code/message/action`.
- Job box: start the existing `_partials/job_progress.html` polling on
  `/jobs/{job_id}/fragment`; when done it includes `view.result_template` with `job`
  (`job.result` is an `OrganizerRunSummary` dict: `trip_id`, `scope_day`, `days[]`
  {`day`, `notes_sent`, `suggested`, `not_organized[]`, `dropped[]`, `failed_batches`},
  `total_suggested`, `total_not_organized`, `batches`, `batches_failed`, `skipped_decided`,
  `stopped`, `remaining_notes`).
- `organizer/summary.html` does **not exist yet**: step 15 must create it, or a finished
  organize job fragment will raise TemplateNotFound. Job state on success is `"done"`.
- Sample trip day `2026-05-02` has 8 notes (one batch, labels n1..n8 by time) and 4 stops.
