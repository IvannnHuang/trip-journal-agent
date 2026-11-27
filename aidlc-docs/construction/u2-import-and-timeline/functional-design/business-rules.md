# U2 Import and Timeline - Business Rules

**Stage**: Functional Design (U2), answers all A (2026-11-27)
**Q-refs** point to the questions in `aidlc-docs/construction/plans/u2-import-and-timeline-functional-design-plan.md`.

---

## 1. Import validation (C17, C03)

### 1.1 File-level rules (location `"file"`; the first failing rule stops the import)
| Id | Rule | Message |
|---|---|---|
| IM-1 | 1 byte to 20 MB (20 × 1024 × 1024 bytes) | "The file is empty." / "The file is larger than 20 MB." |
| IM-2 | UTF-8, a leading BOM is removed | "The file is not UTF-8 text. Only the JSON trip format is supported." |
| IM-3 | First non-space character `<` → XML/GPX (FR-1.2). The file name and content type are never used (Q10) | "This looks like an XML/GPX file. Only the JSON trip format is supported." |
| IM-4 | Valid JSON; top level is one object | "The file is not valid JSON (line L, column C)." / "The file must contain one JSON object." |

### 1.2 Record rules (all reported together, Q9)
| Id | Rule | Q-ref |
|---|---|---|
| IM-5 | Unknown field anywhere → issue at its path, message `unknown field 'x'` (US-01 Scenario 3) | FR-1.3 |
| IM-6 | Required field missing → `required field is missing`; wrong JSON type → `must be a string` / `must be a number` / `must be an integer` / `must be a list` / `must be an object`; no string-to-number coercion | Q5 |
| IM-7 | `*_utc` times: ISO-8601 with `Z` or `+00:00` only; no zone → `must be a UTC time ending in Z`; another offset → `must be in UTC (Z or +00:00), the local offset goes in utc_offset_minutes` | Q1 |
| IM-8 | `utc_offset_minutes` in -720..+840 and a multiple of 15 → else `must be between -720 and 840 and a multiple of 15` | Q2 |
| IM-9 | Text limits: `trip_id` and record ids 1-100, no leading/trailing spaces; `title` 1-200; stop `name` 1-200 when not blank (blank = missing); note `text` 1-10,000; `file_name` 1-255; `home_timezone` 1-64; `route_summary` ≤ 5,000; lengths after trim; text stored exactly as written | Q3, Q4, Q5 |
| IM-10 | `lat` -90..90, `lon` -180..180, finite; photo `lat`/`lon` both or neither | |
| IM-11 | `stops` has at least 1 item; `notes` present (may be empty); `photos` optional | Q6 |
| IM-12 | Ids unique within each type; a duplicate is reported at the second one: `stops[7].id: duplicate id 's3' (first at stops[2])` | Q4 |
| IM-13 | `notes[i].stop_id` must be a `stops[].id`: `notes[3].stop_id: no stop with id 's9'`; `stops[i].end_utc >= start_utc`: `stops[4].end_utc: end_utc (...) is before start_utc (...)` (US-01 Scenario 2) | |
| IM-13a | Not checked (allowed): a note's time outside its stop (Q7); overlapping stops (Q8); several trips' days overlapping | Q7, Q8 |

### 1.3 Reporting
- IM-14: issues ordered by their position in the file; at most 50, then `and N more issues`; **nothing is stored** when any issue exists (one transaction, US-01 Scenarios 2-4).
- Cross-record checks skip records that already failed the schema, so one bad field does not cause a chain of follow-up issues.
- Locations use the file's own keys and 0-based list indexes (`stops[4].end_utc`), the same form as the US-01 example.

### 1.4 Duplicates and storing
- IM-15: only a fully valid file is checked for a duplicate (Q11). `trip.trip_id` already stored → 409 `trip_exists`, message "A trip with the id 'X' is already imported. Delete it first, then import again." A unique-constraint error from a parallel import gives the same 409.
- IM-16: trip, stops, notes and photos are written in one transaction; any failure rolls back all of it. The import never executes file content (no `eval`, `exec`, `pickle`; US-01 rule).
- IM-17: times stored as UTC text `YYYY-MM-DDTHH:MM:SSZ` (U1 format); fractional seconds are cut (FA-2). Coordinates stored as given (WGS-84 decimal degrees, FR-1.4).

---

## 2. Day derivation (C18)
| Id | Rule |
|---|---|
| DD-1 | A stop's day = local date of `start_utc + utc_offset_minutes` (FR-2.1). Its end time never moves it |
| DD-2 | Each record uses its own offset; `home_timezone` is never used (Q3) |
| DD-3 | A note with `stop_id` has its stop's day; a note without one has the local date of its own time (Q12) |
| DD-4 | Order within a day: stops by (`start_utc`, `end_utc`, `source_id`); notes and photos by (`time_utc`, `source_id`). Import inserts stops in this order |
| DD-5 | Trip days = sorted set of stop days, days of unlinked notes, days of photos in no stop. No empty days. `day_number` = index + 1 (Q15) |
| DD-6 | A photo is in a stop when `start_utc <= time_utc <= end_utc`; with several candidates, the latest start (ties: latest `source_id`); otherwise "Other photos" on its own local date (Q13). Computed at view time |
| DD-7 | `ends_next_day` = local date of `end_utc + offset` is later than the stop's day; shown as `+1 day` (or `+N days`) (Q16) |

---

## 3. Timeline display (C04, C01)
| Id | Rule |
|---|---|
| TL-1 | Unknown `trip_id` → 404 `trip_not_found` ("This trip does not exist. It may have been deleted.") on pages and API |
| TL-2 | A well-formed date that is not a trip day → 404 `day_not_found` ("This trip has no records on that date."). A malformed date → 404 on pages, 422 in the API (Q18) |
| TL-3 | Times shown as local `HH:MM`. The offset label (`UTC+01:00`, `UTC-05:00`, `UTC+05:45`) is shown next to times only when the day's stops do not all share one offset (Q16) |
| TL-4 | A stop without a name: "Unnamed place" plus coordinates to 4 decimals. The page never calls PlaceLookup or the model (Q17) |
| TL-5 | Photos are metadata only: count per stop, plus a list of local time, coordinates (or "no location") and file name. No images or thumbnails (US-04 rule, FR-2.3) |
| TL-6 | "Notes not linked to a stop" and "Other photos" appear after the stops, only when not empty (Q13, Q14) |
| TL-7 | Previous / next day links follow DD-5; the missing direction is shown disabled (`aria-disabled`, not a link) on the first / last day (US-04 Scenario 4) |
| TL-8 | Raw note text is shown escaped (Jinja autoescape); it is never rendered as HTML |

---

## 4. Active trip (C04)
| Id | Rule |
|---|---|
| AT-1 | A successful import makes the new trip active (Q19) |
| AT-2 | Opening a trip overview or one of its days, or "Make active" in the trip list, makes that trip active |
| AT-3 | The base layout shows the active trip's title or "No trip selected" on every page (US-02 rule) |
| AT-4 | If the stored active trip no longer exists (deleted), the most recently imported remaining trip becomes active; with none, there is no active trip and `/trips` shows the import form |
| AT-5 | Every trip-scoped read takes one trip id; no query joins two trips (US-02 Scenario 2) |

---

## 5. Delete (C04)
| Id | Rule |
|---|---|
| DL-1 | Pages: delete needs the confirmation page; a `GET` never deletes (Q20) |
| DL-2 | The confirmation names the trip, the counts of stops, notes and photos, and says that journals and note decisions are deleted too (US-03 Scenario 2) |
| DL-3 | API `DELETE /api/trips/{id}` deletes at once and returns 204; unknown id → 404 |
| DL-4 | Delete removes every row of the trip by cascade (incl. FTS rows and U3/U4 tables); `settings` and `place_cache` stay (U1 rule 1.3) |

---

## 6. Testable Properties (PBT-01; PBT-02 and PBT-03 are blocking in U2's Definition of Done)

Generators (`tests/strategies.py`, extended): a valid `TripFile` strategy with 1-10 stops, 0-15 notes, 0-15 photos; times between 2000-01-01 and 2099-12-31 UTC, whole seconds; offsets from multiples of 15 in -720..840; stop durations 0-36 h (so some cross midnight); notes optionally linked to generated stop ids; unique ids per type; text from a printable Unicode alphabet incl. non-Latin letters.

### 6.1 Round trip (PBT-02)
- P-I1: for every valid `TripFile` t, `parse_trip_file(t.model_dump_json(exclude_none=...).encode())` equals t.
- P-I2: import then read back (repositories) gives the same trips, stops, notes and photos (ids, times, offsets, text exact), advisory.

### 6.2 Validation invariants (PBT-03)
- P-I3: adding an unknown key to any object of a valid file gives an issue whose location ends with that key.
- P-I4: setting any stop's `end_utc` before its `start_utc` gives an issue at `stops[i].end_utc`, and nothing is stored.
- P-I5: any issue list has at most 50 items, and `len(issues) + more` equals the total found.

### 6.3 Day derivation invariants (PBT-03)
- P-D1: `group_stops_by_day` is a partition: every stop is in exactly one group.
- P-D2: every stop's group key equals `local_date(start_utc, offset)`; the end time never changes it (stop past midnight).
- P-D3: each group is sorted by (`start_utc`, `end_utc`, `source_id`).
- P-D4: `local_date(t + 24 h, o)` is the day after `local_date(t, o)`; for a fixed t, a larger offset never gives an earlier date (monotonic in offset).
- P-D5: the day index is sorted and unique; for every day d except the last, `prev(next(d)) == d`.
- P-D6: every note with a `stop_id` is on its stop's day.
- P-D7: every photo is in at most one stop, and that stop's window contains the photo time; a photo in no window is on its own local date's "Other photos".
- P-D8: the sum of per-day counts equals the trip's totals of stops, notes and photos.

### 6.4 No PBT property identified
Page rendering, the active-trip setting and delete are tested with examples (API/page tests for 201, 409, 422, 404, 204 and the confirmation flow).

---

## 7. Design check (A8)

### 7.1 Stories
| Story / scenario | Covered by |
|---|---|
| US-01 S1 valid file: stored, in list, days with counts | IM-15/16, AT-1, business-logic 1 and 3.1, frontend 2.1-2.2 |
| US-01 S2 end before start, names field and record | IM-13, IM-14 |
| US-01 S3 unknown field | IM-5 |
| US-01 S4 > 20 MB, GPX, non-JSON | IM-1..IM-4 |
| US-01 rules: UTC + offset, WGS-84, no eval, documented schema | IM-7, IM-16, IM-17, `docs/import-format.md` (frontend 4) |
| US-02 S1/S2 switch trips, chat stays in the active trip | AT-1..AT-5 (S2 re-tested in U5) |
| US-03 S1 re-import refused, tells to delete first | IM-15 |
| US-03 S2/S3 confirmation, cancel | DL-1, DL-2 |
| US-03 S4 re-import after delete | business-logic 5 step 4 |
| US-04 S1 normal day | DD-4, TL-3, TL-5 |
| US-04 S2 stop past midnight | DD-1, DD-3, DD-7, sample `s4` |
| US-04 S3 time-zone change | DD-2, P-D2 |
| US-04 S4 prev/next, disabled at ends | TL-7 |
| US-04 rules: photos as metadata, keyboard | TL-5, frontend 3 |

### 7.2 Unit Definition of Done (`unit-of-work.md` U2)
Import validation example tests and round-trip PBT (6.1); day-derivation invariants (6.3); API tests for 422, 409, 404 (frontend 2.6); ruff, mypy and coverage ≥ 80% are checked at Code Generation.

### 7.3 Interface changes
Listed in `domain-entities.md` section 4 (IC-1..IC-7).

---

## 8. Open assumptions for review
| Id | Assumption |
|---|---|
| FA-1 | Strict JSON types: `"38.7"` for `lat` is refused (an integer `38` is accepted). Chosen so a malformed export is caught, not silently converted |
| FA-2 | Fractional seconds in times are accepted and cut to whole seconds on store, to match U1's stored UTC text format |
| FA-3 | Duplicate keys inside one JSON object: the parser keeps the last one (Pydantic JSON behavior, to be confirmed in Code Generation); not reported as an issue |
| FA-4 | Day headings use English weekday and month names ("Day 1 - Sat 2 May 2026"); the UI language follows the project's existing English UI |
