# U2 Import and Timeline - Frontend Components

**Stage**: Functional Design (U2), answers all A (2026-11-27)
**Stack**: FastAPI + Jinja2 templates + htmx (U1 `base.html`). Pages are server-rendered and work without JavaScript; htmx only improves them.

---

## 1. Layout change (`templates/base.html`)
- Active-trip indicator in the header on every page: the active trip's title linking to `/trips/{id}`, or "No trip selected" linking to `/trips` (AT-3).
- The existing nav link `/trips` now resolves (carry-in CI-2).

## 2. Pages

### 2.1 Trip list and import (`GET /trips`, `trips/list.html`)
| Part | Content |
|---|---|
| Import form | `<form method="post" action="/trips/import" enctype="multipart/form-data">`, `<input type="file" name="file" accept=".json,application/json" required>` with a visible label, a "Import" submit button, and a one-line hint "JSON trip format, up to 20 MB" linking to `docs/import-format.md` |
| Issue list | Shown after a refused import: a heading "The file was not imported", the issue count, then a list `location: message` (up to 50, then "and N more issues"); `role="alert"` so screen readers announce it |
| 409 message | "A trip with the id 'X' is already imported. Delete it first, then import again." with a link to that trip's delete page |
| Trip table | One row per trip (TripRepository order: newest import first): title (link to overview), date range `first_date` - `last_date`, day count, imported at (local display), "Active" badge or a "Make active" button (`POST /trips/{id}/activate`), "Delete" link (`/trips/{id}/delete`) |
| Empty state | No trips: only the import form and "No trips yet. Import a trip file to start." |

### 2.2 Trip overview (`GET /trips/{id}`, `trips/overview.html`)
- Title, date range, route summary (escaped, when present).
- Day list: one row per `DaySummary`: "Day N - Sat 2 May 2026" linking to the day page, plus stop / note / photo counts.
- Opening the page sets the trip active (AT-2).
- Unknown trip → 404 page (TL-1).

### 2.3 Day timeline (`GET /trips/{id}/days/{YYYY-MM-DD}`, `trips/day.html`)
| Part | Content |
|---|---|
| Header | `DayView.heading`, trip title link, "Day N of M" |
| Day nav | "Previous day" / "Next day" links to `prev_date` / `next_date`; on the first / last day the missing one is a `<span aria-disabled="true">` styled as disabled (TL-7). Also a link back to the overview |
| Stop list | An ordered list; per stop: `start_local`-`end_local` (`+1 day` badge when `ends_next_day`), offset label only when `show_offsets` (TL-3), name or "Unnamed place (38.7118, -9.1301)" (TL-4), its notes (time + escaped text, TL-8), photo count and a `<details>` list of photo metadata (TL-5), and an empty slot `organized` for U3 (rendered as nothing in U2) |
| Unlinked notes | Section "Notes not linked to a stop", only when not empty (TL-6) |
| Other photos | Section "Other photos", only when not empty (TL-6) |
| Errors | Unknown trip / day or malformed date → 404 page with the message and a link to the overview or `/trips` (TL-1, TL-2) |

### 2.4 Delete confirmation (`GET /trips/{id}/delete`, `trips/delete.html`)
- Text: "Delete 'A day in Lisbon'? This removes 4 stops, 8 notes and 10 photos, plus any journals and note decisions for this trip. This cannot be undone." (DL-2)
- `<form method="post" action="/trips/{id}/delete">` with a "Delete trip" button, and a "Cancel" link back to the overview (US-03 S3). A `GET` never deletes (DL-1).
- After deleting: redirect `303` to `/trips` with the message "Trip deleted." The active trip falls back per AT-4.

### 2.5 404 page (`errors/404.html`)
Shared page: the error message from the code (`trip_not_found`, `day_not_found`) and links to `/trips`.

### 2.6 Route table
| Method and path | Success | Errors |
|---|---|---|
| `GET /trips` | 200 list page | - |
| `POST /trips/import` (multipart `file`) | 303 → `/trips/{id}` | 422 / 409: list page re-rendered with the issues, same HTTP status |
| `POST /trips/{id}/activate` | 303 → `/trips` | 404 |
| `GET /trips/{id}` | 200 overview | 404 `trip_not_found` |
| `GET /trips/{id}/days/{date}` | 200 day page | 404 `trip_not_found`, `day_not_found`, malformed date |
| `GET /trips/{id}/delete` | 200 confirmation | 404 |
| `POST /trips/{id}/delete` | 303 → `/trips` | 404 |
| `GET /api/trips` | 200 `list[TripSummary]` | - |
| `POST /api/trips` (multipart `file`) | 201 `TripSummary` | 422 `import_invalid` (`issues`, `more`), 409 `trip_exists` |
| `GET /api/trips/{id}` | 200 `TripSummary` | 404 `trip_not_found` |
| `GET /api/trips/{id}/days/{date}` | 200 `DayView` | 404 `trip_not_found` / `day_not_found`; 422 malformed date |
| `DELETE /api/trips/{id}` | 204 | 404 `trip_not_found` |

API errors use the U1 error body (`code`, `message`, plus `issues` and `more` for 422 import). Trip ids in paths are the integer row ids.

## 3. Keyboard and accessibility (US-04 rule)
- Every action is a link, button or form control in reading order; no click-only `div`s.
- Visible focus outline (U1 CSS); the file input has a `<label>`.
- Optional keys on the day page: `[` previous day, `]` next day (small inline script, ignored while typing in a field); the links work without it.
- Times carry `<time datetime="...">` with the UTC value.

## 4. Documentation produced in Code Generation
- `docs/import-format.md`: the C17 schema (domain-entities 1), rules IM-1..IM-13 with examples, and the minimal sample trip file `samples/minimal-lisbon-2026-05.json` (business-logic-model 6).
