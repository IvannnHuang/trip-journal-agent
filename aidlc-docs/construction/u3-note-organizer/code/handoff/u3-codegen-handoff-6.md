# U3 code generation hand-off 6 (plan steps 14-15 done, 2026-11-27)

- 完成：步骤 14（`pages/notes.py`，在 `main.py` 的 `notes_api` 之后注册）和 15（模板和 CSS），已勾选，未提交。
- 检查：pytest 338 passed / 3 deselected（+3 smoke）；ruff check、format --check、mypy --strict 全部通过。未做浏览器检查。
- 下一步：步骤 16-18。

## New decisions
- D-34: Extra partials: `_partials/day_stops.html` (the review region), `organizer_job.html` (the job area), `accept_all.html` (also sent OOB), and `photo_line.html` (CI-1).
- D-35: A plain-form organize answers 303 to `<day or trip>?job=<id>`, or `?nothing=1` when nothing is left to send. A plain accept-all answers 303 to `?accepted=n`. `render_day` (pages/days.py) and `render_overview` (pages/trips.py) are shared by the GET pages and the error re-renders.
- D-36: error replies swap via `hx-on::before-swap`: `#day-stops` (409, 422), organizer sections (404/409/429/503). 409 from review is retargeted to `#day-stops`; 422 from an edit is retargeted to `#note-{id}` (HX-Retarget + HX-Reswap outerHTML).
- D-37: plain GET edit / plain 422 = full day page with the form open; GET edit on a non-pending row = 409.
- D-29 / D-5 applied: no retry link (Organize button stays); busy = 429.
- Audit: the entry carries the real clock time 15:11:27Z (earlier than the brief's 15:25:00Z).

## Routes (pages/notes.py)
| Route | htmx | plain |
|---|---|---|
| POST `/trips/{id}/days/{day}/organize` | 200 `organizer_job.html`; errors keep their status (404, 409, 429, 503) | 303 `?job=` / `?nothing=1`; error = full page with that status |
| POST `/trips/{id}/organize` | same | 303 to `/trips/{id}?…` |
| POST `/trips/{id}/days/{day}/accept-all` | 200 `#day-stops` + OOB accept-all + status "N suggestions accepted" | 303 `?accepted=n` |
| POST `/suggestions/{sid}/accept\|reject\|undo` | 200 `#day-stops` + OOB; 409 retargeted | 303 to the day; 409 = day page |
| GET `/suggestions/{sid}/edit` | 200 note row with the form | 200 day page with the form |
| POST `/suggestions/{sid}/edit` | 200 `#day-stops`; 422 note row with errors | 303; 422 day page |
| GET `/suggestions/{sid}/row` | 200 note row (Cancel) | 303 to the day |
| unknown sid/trip/day | 404 error.html | 404 page |

## Templates, ids, testids
- `days/day.html` = bar + `day_stops.html`; photos via `photo_line.html`.
- Bar: `#organizer-bar`, button `organizer-day` "Organize notes for this day", form `#accept-all-form` / button `organizer-accept-all` "Accept all for this day (N)" (disabled at 0), `#organizer-status` role=status, `#organizer-job`.
- Job area: `organizer-error`, `organizer-nothing`. Summary `organizer/summary.html`: `organizer-summary`, `organizer-summary-heading` ("Organized N notes" / "… over D days"), `organizer-summary-day-{day}`, `organizer-not-organized-{day}`, `organizer-dropped-{day}`, `organizer-batches-failed`, `organizer-remaining` (S.2), `organizer-show-results`.
- `#day-stops` (`day-stops-region`) holds `day-stops` (ol) and `day-other-notes`.
- `note_item.html`: `#note-{id}`; `note-{id}-organized`, `-category`, `-edited`, `-rejected`; box `suggestion-{sid}` "Suggestion – not saved". Buttons `suggestion-{sid}-accept|edit|reject|undo` have the aria-labels "Accept / Edit / Reject suggestion for note at HH:MM" and "Undo decision for note at HH:MM".
- `suggestion_edit.html`: form `edit-{sid}` (aria-label "Edit suggestion for note at HH:MM"); fields `edit-{sid}-category|stop|dish|rating|tip`; errors `edit-{sid}-{field}-error` plus aria-invalid / aria-describedby; `edit-{sid}-save` "Save and accept"; `edit-{sid}-cancel` (Esc clicks it).
- Overview: `overview-organizer`, button `organizer-trip` "Organize the whole trip", `#organizer-job`, `overview-day-{day}-review` "N to review". List: CI-2 "1 day" / "n days".

## Tests and fixtures
- New `tests/api/test_organizer_pages.py` (3 smoke tests). Fixture `pages`; it reuses helpers from `tests/api/test_notes_api.py` (`make_client`, `reply`, `import_trip`, `wait_job`, `DAY`, `NOTE_LABELS`).
- No U2 test changed.
