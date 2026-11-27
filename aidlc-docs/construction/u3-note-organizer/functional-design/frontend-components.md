# U3 Note Organizer - Frontend Components

**Stage**: Functional Design (U3). The owner answered A to all 21 questions on 2026-11-27.
**Stack**: the same as U2: FastAPI, Jinja2 server-rendered pages and htmx 2.0.4. Every action is a real `<form method="post">`, so it works without JavaScript; htmx only swaps regions.

---

## 1. Day page changes (`days/day.html`, `_partials/stop_item.html`)

| Part | Content |
|---|---|
| Organizer bar (top of the day) | A **Organize notes for this day** button, `POST /trips/{id}/days/{date}/organize`, and an **Accept all for this day (N)** button, `POST /trips/{id}/days/{date}/accept-all`, which is disabled when N = 0 (OR-AA2). There is also a status area with `role="status"` for "9 suggestions accepted" and "Nothing to organize". |
| Job progress | The U1 job-progress poller fragment replaces the organizer bar while the job runs. When the job is done, the `organize` job view (`AppState.job_views["organize"]`) shows the run summary (section 4) and a "Show results" link that reloads the day region. |
| Stop region | `<section id="day-stops">` wraps the stop list and the unlinked notes. Review actions return this whole region (FA-6). |
| Note row (`_partials/note_item.html`, new; it replaces the inline `<li>` in `stop_item.html`) | The time and the raw text (unchanged), then one of three blocks: **organized line** (OR-D1), **suggestion box** (OR-D2) or **rejected line** (OR-D3) |
| Photo line (CI-1) | `time · 38.7118, -9.1301 · IMG_0412.jpg`, or `time · no location · …` |

### 1.1 Suggestion box (pending)
- A dashed border and the label "Suggestion – not saved".
- The values: category tag, stop name (or "No stop"), and dish, rating as "n / 5" and tip when set.
- Buttons, in Tab order:
  - **Accept**: `POST /suggestions/{sid}/accept`;
  - **Edit**: `GET /suggestions/{sid}/edit` swaps the edit form into the box;
  - **Reject**: `POST /suggestions/{sid}/reject`.
- Each button has an `aria-label` that names the note, for example "Accept suggestion for note at 13:05".

### 1.2 Edit form (inline, `_partials/suggestion_edit.html`)

| Field | Control | Rule |
|---|---|---|
| Category | `<select>`, five options | OR-F4 |
| Stop | `<select>`: the day's stops in time order, with the name or "Unnamed place (lat, lon)", plus "No stop" | OR-S1 |
| Dish | `<input maxlength="80">` | OR-F2 |
| Rating | `<select>`: none, 1-5 | OR-F3 |
| Tip | `<textarea maxlength="200">` | OR-F2 |

- **Save and accept**: `POST /suggestions/{sid}/edit` stores the row with status `edited`.
- **Cancel**: `GET /suggestions/{sid}/row` brings back the suggestion box. Esc does the same (`hx-on:keydown`, OR-ST3).
- Invalid input returns 422 and the form again, with messages next to the fields (`aria-describedby`).

### 1.3 Decided rows
- **Organized line**: an **Undo** button, `POST /suggestions/{sid}/undo`.
- **Rejected line**: "Suggestion rejected" and **Undo**.

## 2. Trip overview changes (`trips/overview.html`)
- An **Organize the whole trip** button, `POST /trips/{id}/organize`. It shows the same job progress and summary as the day button, with the summary grouped by day (US-06 S2).
- In the day list, each day row shows "N to review" when `pending_suggestions > 0`. The row links to that day's page.

## 3. Trip list change (CI-2)
- The `trips/list.html` day count reads "1 day" for one day and "n days" otherwise.

## 4. Run summary fragment (`organizer/summary.html`)
- First a heading, "Organized N notes" (for a day) or "Organized N notes over D days" (for the trip).
- Then, per day:
  - how many notes got suggestions;
  - "K notes not organized", in a `<details>` list of the note's time, its first 60 characters and the reason;
  - dropped items, in a `<details>` list with each reason.
- When any batch failed: "Some notes could not be organized. Run the organizer again to retry them." (OR-RUN1 retries only those notes)
- When the job failed or timed out: the U1 user-facing error with its action (`model_error`, `job_timeout`, `job_cancelled`). Saved batches are still shown (OR-SAVE3).

## 5. Routes

### 5.1 Pages (`pages/organizer.py`)

| Method and path | Does | Returns | Errors |
|---|---|---|---|
| POST `/trips/{id}/days/{date}/organize` | `start(trip, day)` | the progress fragment, or a "Nothing to organize" status | 404, 409 `model_busy`, 503 |
| POST `/trips/{id}/organize` | `start(trip, None)` | the progress fragment | 404, 409, 503 |
| POST `/trips/{id}/days/{date}/accept-all` | `accept_all_pending` | the `#day-stops` region and status "N suggestions accepted" | 404 |
| POST `/suggestions/{sid}/accept` / `reject` / `undo` | the review action | the `#day-stops` region | 404, 409 `suggestion_state` |
| GET `/suggestions/{sid}/edit` | | the edit form fragment | 404, 409 (not pending) |
| POST `/suggestions/{sid}/edit` | `edit_and_accept` | the `#day-stops` region; on 422, the form with errors | 404, 409, 422 |
| GET `/suggestions/{sid}/row` | | the suggestion box (cancel) | 404 |

Without htmx (no `HX-Request` header), each POST redirects (303) back to the day page or the overview, following the U2 pattern.

### 5.2 JSON API (`api/notes.py`)

| Method and path | Body / result | Errors |
|---|---|---|
| POST `/api/trips/{id}/organize` | body `{"day": "YYYY-MM-DD" \| null}`; 202 `{"job_id", "notes_to_send", "batches"}`, or 200 `{"job_id": null, "notes_to_send": 0}` | 404, 409, 422 `invalid_date`, 503 |
| GET `/api/trips/{id}/days/{date}/suggestions` | `list[SuggestionView]` | 404, 422 |
| POST `/api/suggestions/{sid}/accept` / `reject` / `undo` | `SuggestionView` | 404, 409 |
| PUT `/api/suggestions/{sid}` | body `SuggestionEdit`; `SuggestionView` (status `edited`) | 404, 409, 422 `invalid_edit` |
| POST `/api/trips/{id}/days/{date}/suggestions/accept-all` | `{"accepted": n}` | 404, 422 |
| GET `/api/jobs/{job_id}` (U1) | the job status with `result` = `OrganizerRunSummary` | |

## 6. Interface changes against `component-methods.md` and the U1/U2 code

| Id | Change |
|---|---|
| IC-1 | `JobRunner.start(kind, work, timeout_s: float \| None = None)`, U1, Q7 A. `None` keeps 300 s. |
| IC-2 | `NoteItem` gains `organized`, `suggestion`, `review_status`. `StopTimelineItem.organized` is removed. `TripService.get_day` places notes by OR-S2 (U2). |
| IC-3 | `DaySummary.pending_suggestions` (U2). |
| IC-4 | `OrganizerBatchResult.dropped` becomes `list[DroppedItem]`, and the result gains `not_organized`. `organize_batch(batch: BatchInput)` takes rows and returns ids. Labels are internal. |
| IC-5 | `OrganizerService.start` returns `OrganizeStart` instead of `JobRef`, and a new `undo(sid)` is added. |
| IC-6 | `SuggestionRepository`: `save_batch(trip_id, note_ids, suggestions, prompt_version, model_name)` (OR-SAVE1; replaces `replace_pending`), `get`, `list_for_trip`, `list_for_day`, `set_status`, `undo`, `accept_all_pending(trip_id, note_ids) -> int`. |
| IC-7 | `Repositories` gains `suggestions`. `AppState` gains `organizer: OrganizerService`, and `job_views["organize"]` is registered. |
| IC-8 | `schema.sql` gets the U3 section with `note_suggestions`. |
| IC-9 | New errors: `NotFoundError(code="suggestion_not_found")` 404, `SuggestionStateError` 409 `suggestion_state`, `SuggestionEditError` 422 `invalid_edit`. |
| IC-10 | New prompt file `agent/prompts/organizer.md`. `PromptLibrary.get("organizer")` already works by name. |
