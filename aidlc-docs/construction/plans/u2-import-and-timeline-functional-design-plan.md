# U2 Import and Timeline - Functional Design Plan

**Unit**: U2 Import and Timeline (owner Ivan Huang, reviewer Edwin Chen)
**Stories**: US-01 Import a trip from a JSON file, US-02 Choose the active trip, US-03 Delete a trip and import a corrected file, US-04 Browse a day's timeline
**Components**: C03 ImportService, C04 TripService, C17 Import Schema and Validation, C18 Day Derivation, C25 (minimal sample trip only), C01/C02 for trips and days
**Inputs**: `unit-of-work.md` (U2), `stories.md` (US-01..US-04), `component-methods.md` (C03, C04, C17, C18, errors), `components.md`, U1 `domain-entities.md` (tables `trips`, `stops`, `notes`, `photos`, `settings`), U1 `code-summary.md`, U1 `build-and-test-summary.md` (findings)
**Extensions**: Security and Resiliency disabled. Property-Based Testing enabled in Partial mode (PBT-02, 03, 07, 08, 09 blocking). U2's Definition of Done needs a round-trip property for import (PBT-02) and invariants for day derivation (PBT-03), so testable properties are identified here (PBT-01, advisory).

**Fixed by U1 (not reopened here)**: the table columns for trips, stops, notes and photos, including the derived `local_date` (stops, notes) and `local_time` (photos) that U2's import must write; the U1 section of `schema.sql` is not edited; `settings` gets the key `active_trip_id`; error types `ImportValidationError` (422), `TripAlreadyExistsError` (409), `NotFoundError` (404).

---

## Part A - Functional design steps

- [x] A1. Domain entities: import models (`TripMeta`, `StopIn`, `NoteIn`, `PhotoIn`, `TripFile`, `ImportIssue`) with every field's type and limit; view models (`TripSummary`, `DaySummary`, `DayView`, `StopTimelineItem`, photo metadata view); how import records map to the U1 tables
- [x] A2. Business logic model: the import pipeline step by step (size, type, decode, JSON, schema, cross-record checks, duplicate check, day derivation, one transaction); day derivation (C18) incl. stop past midnight and different UTC offsets; building the day view (notes and photos placed on stops, prev/next day); active trip resolution; delete flow
- [x] A3. Business rules: validation rules with exact issue locations and messages; duplicate import → 409; missing trip or day → 404; ordering and tie-breaks; active-trip rules; delete rules
- [x] A4. Frontend components: trip list and import form, trip overview with days and counts, day timeline page, delete confirmation, active-trip indicator in the base layout; routes (pages and `/api/...`) with their errors
- [x] A5. Minimal sample trip (C25, plan Q5 C): the exact records, which edge cases each one covers, and the fixture loader for tests
- [x] A6. Testable properties (PBT-01, feeding PBT-02 and PBT-03): import round trip; day-derivation invariants; generators needed
- [x] A7. Carry-ins for Code Generation (from U1 Build and Test, recorded, not designed away): port override, `/trips` nav link 404, manual cancel reported as `job_timeout` instead of `job_cancelled`
- [x] A8. Check the design against US-01..US-04 acceptance criteria and the U2 Definition of Done; list every interface change against `component-methods.md`

---

## Questions

Please answer every question by writing the letter after `[Answer]:`. (Answers recorded on 2026-11-27: the owner Ivan Huang chose A for all 22 questions.) Option A is the recommended choice in each question. If no option fits, choose the last option (Other) and describe your choice after the tag.

### Import file format (C17)

## Question 1
How are times written in the import file? (`component-methods.md` uses `start_utc` plus `utc_offset_minutes`.)

A) Keep the designed form: `*_utc` fields must be UTC (ending in `Z` or `+00:00`); a time without a zone or with any other offset is refused; the local time comes only from `utc_offset_minutes`. One source of truth, no mismatch possible.

B) Accept any zone-aware time in `*_utc` and convert it to UTC; `utc_offset_minutes` still decides the local time (a file can then say `+02:00` in the time and `60` in the offset, which is confusing)

C) Replace the pair with one local time plus offset per record (for example `start_local: "2026-05-03T23:10:00+01:00"`) and derive UTC and the offset from it

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
Which UTC offsets are valid?

A) From -720 to +840 minutes (UTC-12:00 to UTC+14:00, the real-world range) and a multiple of 15 (covers +05:45 Nepal, +12:45 Chatham)

B) From -720 to +840 minutes, any integer

C) Any integer from -1439 to +1439 (what Python's `timezone` allows)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
How is `trip.home_timezone` checked? It is informational only (U1 table rule). Note: on Windows, Python's `zoneinfo` has no time-zone database unless the `tzdata` package is added.

A) Free text, optional, 1 to 64 characters, not checked against the time-zone database, never used for any calculation

B) Must be a valid IANA name (for example `Europe/Lisbon`), checked with `zoneinfo`; add the `tzdata` dependency

C) Remove the field from the schema

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
Record ids in the file (`stops[].id`, `notes[].id`, `photos[].id`): what must be unique?

A) Unique within each record type (a stop and a note may both be `"1"`); each id is a string of 1 to 100 characters with no leading or trailing spaces. This matches the U1 tables (UNIQUE (`trip_id`, `source_id`) per table).

B) Unique across all record types in the file

C) Option A, plus a restricted character set (letters, digits, `-`, `_`, `.`, `:`)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
Text limits (after trimming spaces):

A) `trip.title` 1 to 200 characters; `trip.trip_id` 1 to 100; stop `name` 1 to 200 when present (an empty string counts as missing); note `text` 1 to 10,000; `file_name` 1 to 255 when present; `route_summary` up to 5,000. Text is stored as written (trimming is used only for the checks; raw note text is never changed, FR-3.4).

B) Only "not empty" checks, no maximum lengths (the 20 MB file limit is the only cap)

C) Option A, but text is stored trimmed

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6
Minimum content of a trip file:

A) At least one stop; `notes` must be present but may be an empty list; `photos` may be missing or empty (as designed)

B) At least one stop and at least one note

C) An empty trip (no stops) is allowed

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7
A note with a `stop_id` whose time is outside that stop's start and end (for example written on the train afterwards):

A) Allowed, no check. People often write notes later; the note stays on the stop it names.

B) Refused with an issue naming the note

C) Allowed, but the import result lists a warning

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8
Stops that overlap in time (one starts before the previous one ends):

A) Allowed, no check (GPS exports often overlap a little; order is by start time)

B) Refused with an issue naming both stops

C) Allowed with a warning in the import result

D) Other (please describe after [Answer]: tag below)

[Answer]: A

### Import errors and file checks (C03, C17)

## Question 9
How many validation issues does a refused import report?

A) All issues found, up to 50 (then "and N more"), ordered by their place in the file. Schema issues and cross-record issues are both reported in one pass when the file parses; cross-record checks are skipped only for records that already failed the schema.

B) Only the first issue

C) All issues with no cap

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10
How is a "wrong type" file (GPX, CSV, image) detected (US-01 Scenario 4)?

A) By content: the bytes must decode as UTF-8 (a BOM is allowed and removed) and parse as a JSON object. The file name is not checked. If the content starts with `<` (XML, such as GPX), the message says "This looks like an XML/GPX file. Only the JSON trip format is supported."

B) By file name: the name must end in `.json`, then option A's content checks

C) By the upload's content type header, then option A's content checks

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11
In what order are a duplicate and an invalid file reported, if a file has both problems?

A) Validate the whole file first (422 with issues); only a valid file is checked for a duplicate `trip.trip_id` (409 "A trip with this id is already imported. Delete it first, then import again."). A unique-constraint error from a parallel import is also reported as 409.

B) Check the duplicate first (read just `trip.trip_id`), then validate

C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Day derivation and timeline (C18, C04)

## Question 12
Which day does a note belong to? (This matters for a stop past midnight: a note at 00:40 on a stop that started at 23:10.)

A) A note with a `stop_id` takes the `local_date` of its stop, so it is shown with the stop on the day the stop started; a note without a `stop_id` uses the local date of its own time and offset

B) Every note uses the local date of its own time and offset, even if its stop is on the day before

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 13
Photos have no `stop_id` in the schema. How are they shown on the timeline (photo count per stop, US-04)?

A) At view time, a photo belongs to the stop whose UTC start-to-end window contains the photo time; if several stops contain it, the one with the latest start. Photos in no stop are listed in an "Other photos" group on the day of their own local date. No schema change and no U1 table change.

B) Add an optional `stop_id` to `PhotoIn` and a `stop_id` column to `photos` (changes U1's schema section); photos without it go to "Other photos"

C) Option B, with option A's time window as the fallback when `stop_id` is missing

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 14
Notes without a `stop_id`, on the timeline:

A) Shown in a "Notes not linked to a stop" group at the end of the day, in time order. U2 never links them itself; U3's organizer can suggest a stop.

B) Linked automatically to the stop whose time window contains the note time, at import

C) Shown inline in the timeline at their time position between stops

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 15
Which local dates count as trip days (for the day list and previous/next)?

A) Every local date that has a stop, plus every date that has only unlinked notes or photos not in any stop, so nothing in the file is hidden. Days are sorted by date; "Day 1" is the earliest date. Gaps between dates are skipped (no empty days).

B) Only dates that have at least one stop (FR-2.1 strictly); records on other dates are not shown on any day

C) Every calendar date from the first to the last record, including empty days

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 16
How are times shown on the timeline?

A) Local `HH:MM` start and end, with "+1 day" after an end time on a later local date (for example "23:10 - 01:30 +1 day"). The UTC offset ("UTC+01:00") is shown next to each time only when the day's stops do not all share one offset.

B) Local times plus the UTC offset always shown

C) Local times only, no offset and no "+1 day" marker

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 17
A stop without an imported `name`, on the timeline page:

A) Shown as "Unnamed place" with its coordinates (4 decimals). The page never calls PlaceLookup, so it opens instantly and never waits on Nominatim; the agent's `lookup_place` tool stays the only caller (U1 rule).

B) Call PlaceLookup when the page opens (if place lookup is on; cached after the first call)

C) Option A plus a "Look up name" button per stop

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 18
Day URL and its errors:

A) Pages: `/trips/{trip_id}/days/{YYYY-MM-DD}`, heading "Day 2 - Sun 3 May 2026". API: `GET /api/trips/{trip_id}/days/{date}`. An unknown trip, or a well-formed date that is not a trip day, gives 404 (`trip_not_found` / `day_not_found`); a malformed date gives 404 on pages and 422 in the API.

B) Day number in the URL (`/trips/{trip_id}/days/2`)

C) Option A, but a malformed date gives 404 in the API too

D) Other (please describe after [Answer]: tag below)

[Answer]: A

### Trips, active trip and delete (C04)

## Question 19
Active trip rules (US-02):

A) A newly imported trip becomes the active trip. Opening any page of a trip (its overview or a day) also makes it active. If the active trip is deleted, the most recently imported remaining trip becomes active; with no trips left, there is no active trip and the trip list shows the import form. The base layout shows the active trip's title on every page, or "No trip selected".

B) The active trip changes only when the user picks it in the trip list (import and page visits do not change it)

C) Option A, but deleting the active trip leaves no active trip until the user picks one

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 20
How does the delete confirmation work (US-03), keeping the page usable by keyboard and without custom JavaScript?

A) "Delete trip" links to a confirmation page `GET /trips/{id}/delete` that names the trip and lists what will be deleted (counts of stops, notes and photos, plus "all journals and note decisions for this trip"); "Delete" submits `POST /trips/{id}/delete`, "Cancel" returns to the trip. The API `DELETE /api/trips/{id}` deletes at once (the API caller is the confirmation) and returns 204; unknown id → 404.

B) An HTML `<dialog>` on the same page opened with a small script

C) The browser's `confirm()` box via htmx `hx-confirm`

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 21
Where does a successful import from the page go, and how does the API take the file?

A) Page: `POST /trips/import` (multipart form, field `file`) redirects to the new trip's overview `/trips/{id}` with the day list and per-day counts of stops, notes and photos (US-01 Scenario 1). A refused import re-renders the trip list with the issues. API: `POST /api/trips` takes the same multipart field and returns `TripSummary` (201), 422 or 409.

B) Page redirects straight to Day 1 of the new trip

C) API takes the raw JSON as the request body (`application/json`) instead of multipart

D) Other (please describe after [Answer]: tag below)

[Answer]: A

### Minimal sample trip (C25)

## Question 22
What is the minimal sample trip about (`sample_data/minimal_trip.json`, plan Q5 C: one day, about 4 stops, 8 notes, 10 photos, one stop past midnight, one mixed-language note)? All data is synthetic; coordinates are public places.

A) One evening-and-day in Lisbon (UTC+01:00 in summer): 4 stops (a cafe, a viewpoint, a museum, a late dinner from 23:10 to 01:30), 8 notes incl. one mixed English/Portuguese note, one note at 00:50 on the dinner stop and one note without a stop; 10 photos incl. one at 00:40 inside the dinner stop and one outside every stop; one stop without a name (for `lookup_place`)

B) One day in Tokyo (UTC+09:00), same record mix, with a mixed English/Japanese note

C) One day in Kyoto, same record mix, with a mixed English/Chinese note

D) Other (please describe after [Answer]: tag below)

[Answer]: A
