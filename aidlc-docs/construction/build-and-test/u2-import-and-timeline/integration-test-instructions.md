# Integration Test Instructions (U2 Import and Timeline)

**Purpose**: check the U2 pages end to end in a real browser (Claude desktop browser pane, Chromium) against a running app with a file database. U2 makes no model calls.

## Setup
1. Start the app (see `build-instructions.md`) on port 8741 with a fresh `$env:TEMP\bt-u2.db`.
2. Open `http://127.0.0.1:8741/`.
3. Files were put into the file input with a `DataTransfer` script, because the browser pane cannot open a file picker. Import was then clicked normally. The 14-day reference trip and the 19.71 MB file were posted to `/api/trips` with `curl`.

## Scenarios and results
| # | Scenario | Expected | Result |
|---|---|---|---|
| S1 | `/` with no trips | 307 to `/trips`, "No trips yet", import panel | **PASS** |
| S2 | Import an invalid file (unknown key, missing lat / lon) | 422; issue list swapped into the import panel | **PASS after F-1 fix** (first run failed: panel did not change, console "Response Status Error Code 422"). Re-run: "3 issues found", `trip.extra: unknown field 'extra'`, `stops[0].lat` / `stops[0].lon: required field is missing`; a second bad file on the swapped-in panel also swaps |
| S3 | Import `sample_data/minimal_trip.json` | success, redirect to the trip overview | **PASS**: lands on `/trips/1`, "A day in Lisbon", 4 stops · 8 notes · 10 photos |
| S4 | Import the same `trip_id` again | 409 message with a "Delete the existing trip" link | **PASS after F-1 fix** (first run failed like S2). Re-run, right after a 422 swap: "A trip with the id 'bt-f1' is already imported…" and the link to `/trips/1/delete` |
| S5 | Day page of the sample | timeline, local times, +1 day marks, unnamed stop shows coordinates, photo groups | **PASS** (matches the golden values in `test_views.py`) |
| S6 | `]` / `[` keys on the 14-day reference trip | next / previous day | **PASS**: Day 1 → 2 → 3 → 2 |
| S7 | Delete the 19.71 MB trip from its confirmation page | redirect, "✔ Trip deleted.", trip gone, active trip unchanged | **PASS** |
| S8 | `TRIP_JOURNAL_PORT` (CI-1) | serves on the chosen port | **PASS** (8741) |

Result: **8 of 8 pass** (S2 and S4 re-run 2026-11-27 with fresh `$env:TEMPt-u2b.db` after the F-1 fix).

## Not verified
- The "Importing…" indicator: imports finish in under 3 s, too fast to see. The `hx-indicator` wiring is in the template.
- Delete while a job runs (409 `job_running`): U2 has no page that starts a job; API tests cover it with a monkeypatched `JobRunner.running`.
- Browsers other than Chromium.
