# U2 Import and Timeline - Domain Entities

**Stage**: Functional Design (U2), answers in `aidlc-docs/construction/plans/u2-import-and-timeline-functional-design-plan.md` (all A, 2026-11-27)
**Stories**: US-01, US-02, US-03, US-04
**Storage**: U2 adds **no tables and no columns**. It writes the U1 tables `trips`, `stops`, `notes`, `photos` (U1 `domain-entities.md` 1.2) and the settings key `active_trip_id`.

---

## 1. Import models (C17, `domain/import_schema.py`)

Every model uses `extra="forbid"` (unknown field → issue), strict JSON types (no `"5"` → `5`; an integer is accepted where a number is expected) and `allow_inf_nan=False`. The file is validated from its JSON text (`model_validate_json`), so time strings are parsed as ISO-8601.

### 1.1 `TripMeta` (`trip`)
| Field | Type | Required | Rule (Q-ref) |
|---|---|---|---|
| `trip_id` | string | yes | 1-100 chars after trim, no leading/trailing spaces (Q4, Q5); becomes `trips.source_id` |
| `title` | string | yes | 1-200 chars after trim (Q5) |
| `home_timezone` | string | no | 1-64 chars, free text, never used in any calculation (Q3) |

### 1.2 `StopIn` (`stops[]`)
| Field | Type | Required | Rule |
|---|---|---|---|
| `id` | string | yes | 1-100 chars, no leading/trailing spaces, unique among stops (Q4) |
| `name` | string \| null | no | 1-200 chars after trim; `""` or only spaces counts as missing (Q5) |
| `start_utc`, `end_utc` | UTC time | yes | ISO-8601 with `Z` or `+00:00`; no zone or any other offset is refused (Q1); `end_utc >= start_utc` |
| `utc_offset_minutes` | integer | yes | -720..+840 and a multiple of 15 (Q2); one offset for the whole stop |
| `lat` | number | yes | -90..90 |
| `lon` | number | yes | -180..180 |

### 1.3 `NoteIn` (`notes[]`)
| Field | Type | Required | Rule |
|---|---|---|---|
| `id` | string | yes | as `StopIn.id`, unique among notes |
| `text` | string | yes | 1-10,000 chars after trim; stored exactly as written (Q5, FR-3.4) |
| `time_utc` | UTC time | yes | as stop times (Q1) |
| `utc_offset_minutes` | integer | yes | as stops (Q2) |
| `stop_id` | string \| null | no | must equal a `stops[].id` in the same file; its time is not compared with the stop's window (Q7) |

### 1.4 `PhotoIn` (`photos[]`, the list may be missing)
| Field | Type | Required | Rule |
|---|---|---|---|
| `id` | string | yes | as `StopIn.id`, unique among photos |
| `time_utc`, `utc_offset_minutes` | | yes | as notes |
| `lat`, `lon` | number \| null | no | both present or both missing; ranges as stops |
| `file_name` | string \| null | no | 1-255 chars when present; metadata only |

No `stop_id` on photos: placement is computed at view time (Q13, business-logic-model 3.3).

### 1.5 `TripFile` (top level)
| Field | Type | Required | Rule |
|---|---|---|---|
| `trip` | `TripMeta` | yes | |
| `stops` | list of `StopIn` | yes | at least 1 (Q6) |
| `notes` | list of `NoteIn` | yes | may be empty (Q6) |
| `photos` | list of `PhotoIn` | no | default empty |
| `route_summary` | string \| null | no | up to 5,000 chars (Q5) |

Overlapping stops are allowed (Q8).

### 1.6 `ImportIssue`
| Field | Type | Example |
|---|---|---|
| `location` | string | `"stops[4].end_utc"`, `"notes[2].stop_id"`, `"trip"`, `"file"` |
| `message` | string | `"end_utc (2026-05-02T09:00:00Z) is before start_utc (2026-05-02T10:00:00Z)"` |

`ImportValidationError(issues: list[ImportIssue], more: int)`: at most 50 issues, `more` = how many were left out (Q9).

---

## 2. View models (C03, C04)

| Model | Fields | Used by |
|---|---|---|
| `DaySummary` | `local_date: LocalDate`, `day_number: int` (1-based), `stop_count`, `note_count`, `photo_count` | trip overview, import result |
| `TripSummary` | `trip_id: int`, `source_id`, `title`, `imported_at`, `first_date`, `last_date`, `days: list[DaySummary]`, `is_active: bool` | trip list, `POST /api/trips` (201) |
| `PhotoMeta` | `photo_id`, `local_time` (`HH:MM`), `lat`, `lon`, `file_name` | inside stops and "Other photos" |
| `NoteItem` | `note_id`, `local_time` (`HH:MM`, plus `+1 day` flag), `text` | inside stops and "Notes not linked to a stop" |
| `StopTimelineItem` | `stop_id`, `name` (or `None`), `lat`, `lon`, `start_local`, `end_local` (`HH:MM`), `ends_next_day: bool` (end on a later local date than start), `offset_label` (`"UTC+01:00"`), `notes: list[NoteItem]`, `photos: list[PhotoMeta]`, `photo_count`, `organized: None` (slot U3 fills) | day timeline |
| `DayView` | `trip_id`, `trip_title`, `local_date`, `day_number`, `day_count`, `heading` (`"Day 1 - Sat 2 May 2026"`), `show_offsets: bool` (stops do not all share one offset, Q16), `stops: list[StopTimelineItem]`, `unlinked_notes: list[NoteItem]`, `other_photos: list[PhotoMeta]`, `prev_date: LocalDate \| None`, `next_date: LocalDate \| None` | day timeline |
| `DeletePreview` | `trip_id`, `title`, `stop_count`, `note_count`, `photo_count` | delete confirmation page |

---

## 3. Mapping import records to U1 tables

| Import | Table and column | Derived by U2 |
|---|---|---|
| `trip.trip_id`, `title`, `home_timezone`, `route_summary` | `trips.source_id`, `title`, `home_timezone`, `route_summary` | `imported_at` = now (UTC) |
| `StopIn` | `stops` (`source_id` = `id`) | `local_date` = C18 `local_date(start_utc, offset)` |
| `NoteIn` | `notes` (`stop_id` = row id of the referenced stop) | `local_date` = the stop's `local_date` when `stop_id` is set, else C18 of the note's own time (Q12) |
| `PhotoIn` | `photos` | `local_time` = naive local ISO of its own time and offset |

- Times are stored in U1's canonical UTC text `YYYY-MM-DDTHH:MM:SSZ`; fractional seconds are cut to whole seconds (monotonic, so `end >= start` still holds). See assumption FA-2.
- Stops are inserted in day order (`start_utc`, `end_utc`, `source_id`), so U1's `ORDER BY start_utc, id` gives the same order as rule DD-4.

---

## 4. Interface changes compared with `component-methods.md` and U1 code

| # | Change | Why |
|---|---|---|
| IC-1 | `NoteRepository.add` gets an optional `local_date` argument (today it always derives from the note's own time) | Q12: a note follows its stop's day |
| IC-2 | Repository `add` methods each call `commit()`; U2 needs one transaction for the whole import. Add a `commit: bool = True` flag (or `add_many` methods) and let ImportService commit once / roll back | C03 "store everything in one transaction" |
| IC-3 | `StopRepository.add` and `NoteRepository.add` must use C18 `local_date` (one function, not a copy) | single source for day derivation (PBT-03 tests one function) |
| IC-4 | `TripSummary` gains `imported_at`, `first_date`, `last_date`, `is_active`; `DaySummary` gains `day_number` | trip list and headings |
| IC-5 | New errors in `services/errors.py`: `ImportValidationError(issues, more)` (422, code `import_invalid`), `TripAlreadyExistsError(source_id)` (409, code `trip_exists`); `NotFoundError` gets codes `trip_not_found` and `day_not_found` | `component-methods.md` errors table |
| IC-6 | `group_stops_by_day` keeps its signature; a new pure function `build_day_index(stops, unlinked_notes, photos) -> list[LocalDate]` computes the day list (Q15) and `assign_photos(stops, photos)` places photos (Q13) | Q13, Q15 |
| IC-7 | `TripService.get_delete_preview(trip_id) -> DeletePreview` added | Q20 confirmation page |
