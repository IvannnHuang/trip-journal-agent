# U2 Import and Timeline - NFR Requirements Plan

**Stage**: Construction - NFR Requirements (unit U2 Import and Timeline)
**Inputs**: `aidlc-docs/construction/u2-import-and-timeline/functional-design/` (4 files), `aidlc-docs/construction/u1-foundation/nfr-requirements/` (2 files, stack reused), `aidlc-docs/inception/requirements/requirements.md` (NFR-1 to NFR-7), `unit-of-work.md` U2 section
**Outputs**: `aidlc-docs/construction/u2-import-and-timeline/nfr-requirements/nfr-requirements.md`, `aidlc-docs/construction/u2-import-and-timeline/nfr-requirements/tech-stack-decisions.md`
**Extensions**: Security Baseline and Resiliency Baseline opted out (skipped). PBT Partial: PBT-02, 03, 07, 08, 09 blocking. PBT-09 (Hypothesis) was decided in U1 and is reused.

## Plan steps

- [x] 1. Analyze the U2 Functional Design artifacts and U1's NFR decisions (Step 1)
- [x] 2. Write this plan with questions (Steps 2-4)
- [x] 3. Collect the owner's answers and check them for ambiguity (Step 5)
- [x] 4. Write `nfr-requirements.md`: performance, scalability, reliability and transaction safety, security, usability, logging, testability incl. PBT generators (Step 6)
- [x] 5. Write `tech-stack-decisions.md`: reused U1 stack, any U2 additions, test tooling (Step 6)
- [x] 6. Record the NFR Design execute / skip decision (Question 10)
- [x] 7. Present the completion message and wait for approval (Steps 7-8)

## Already decided (no question)

| Topic | Decision | Source |
|---|---|---|
| Stack | Python 3.12+, FastAPI, Jinja2 + htmx, Pydantic v2, `sqlite3` direct; no new runtime library. `python-multipart` (needed for uploads) is already in `pyproject.toml` from U1 | U1 tech-stack §1, `pyproject.toml` |
| Model use | Import, timeline and delete never call the model or JobRunner, so they work with Ollama down | business-logic-model §1 |
| File size | 1 B to 20 MB; at most 20 MB + 1 byte is read from the upload | IM-1 |
| Errors | 422 before 409; 404 codes `trip_not_found`, `day_not_found` | IM-14, IM-15, TL-1, TL-2 |
| Security | Security Baseline opted out. Localhost only; Pydantic for every input; no `eval` / `exec` / `pickle`; Jinja autoescape | NFR-3.2, NFR-3.3, IM-16, TL-8 |
| Scalability | Single user on one laptop | NFR-3.1 (U1-NFR-S.1) |
| PBT framework | Hypothesis, profiles `default` (100) and `ci` (500), `print_blob=True`, `deadline=None`, seed passed in the pre-merge run | U1-NFR-T.3, T.4, U1 NFR Design |
| Logging format | Python `logging`, console, key=value lines; no note text | U1-NFR-L.1, L.2 |
| Coverage | ≥ 80% line coverage of U2 modules | unit-of-work U2 DoD |

---

## Question 1
What speed target applies to import?

A) Targets, not hard limits: the minimal sample trip imports in ≤ 1 s, the reference large trip (Question 2, about 1-2 MB) in ≤ 5 s, and a file near the 20 MB limit (the reference trip with long note texts) in ≤ 15 s on the measured laptop. Measured in Build and Test; a miss is recorded with the laptop, like U1-NFR-P.1

B) Same numbers, but a failing timing test blocks the unit

C) No import speed target

D) A tighter target: 20 MB in ≤ 5 s

E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
What "large trip" should the app be shown to handle (used for the timing check in Question 1 and Question 3)?

A) A generated reference trip of 14 days, 300 stops, 2,000 notes and 3,000 photos (well under 20 MB). No record-count limit in the import beyond the 20 MB file limit

B) The same reference trip, and also a hard cap on record counts (for example 5,000 stops, 50,000 notes, 50,000 photos) reported as an import issue

C) No reference trip; only the minimal sample trip is tested

D) A larger reference: 60 days, 2,000 stops, 20,000 notes, 20,000 photos

E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
What speed target applies to the trip list and the day-timeline page?

A) Targets: server time ≤ 300 ms for the trip list and for one day page of the reference trip (Question 2). The day index and photo placement are computed per request from SQL (no cache), as Functional Design says (DD-6, "computed at view time")

B) Same targets, plus a cache of the day index per trip (invalidated on import and delete)

C) No page speed target

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
How should a large import run, given U1 NFR Design calls `sqlite3` directly in the event loop?

A) Run the import in the request, as U1 does: parsing and the one transaction block the server for the few seconds a large file takes. Single user, so other pages simply wait. A busy indicator covers it (Question 7)

B) Run the parse in a worker thread (`run_in_threadpool`) and only the database write in the event loop, so other requests (for example job polling) are not blocked during parsing

C) Run the whole import as a JobRunner job with progress polling

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
What transaction safety does import need (IM-16 says "one transaction")?

A) One explicit transaction (`BEGIN IMMEDIATE` ... `COMMIT`, `ROLLBACK` on any exception) on the shared connection; SQLite's rollback journal guarantees that a crash or a killed server mid-import leaves nothing stored. A test injects a failure after some rows are written and checks that zero rows of that trip remain. A parallel import of the same `trip_id` ends with the 409 from the unique constraint (IM-15)

B) Same, plus switch the database to WAL mode

C) Rely on Python's default `sqlite3` implicit transactions, with one `commit()` at the end

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6
What happens when the user deletes a trip while a model job (journal or Q&A, later units) is running?

A) Refuse the delete while any job is running: the confirmation page and `DELETE /api/trips/{id}` return 409 `job_running` with "A job is running. Wait for it to finish or cancel it, then delete the trip." (JobRunner already exposes `running`; no trip id needed on the job)

B) Allow it; the running job's tools then find no rows, or `save_journal` fails on the foreign key, and the job ends with its normal error message

C) Allow it, and cancel the running job first

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7
What feedback does the import form give while a file is being imported?

A) The submit button is disabled and shows "Importing…" (htmx `hx-indicator` / `hx-disabled-elt`), so a double click cannot send two imports; no progress bar

B) A progress bar based on upload bytes

C) No feedback beyond the browser's own loading state

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8
What does U2 log?

A) INFO one line per import: result (`ok`, `invalid`, `exists`, `file_error`), `trip_id` (the file's id), counts of stops / notes / photos, issue count and duration in ms; one line per delete with the trip id and counts. Issue messages, note text and file content are never logged

B) Same, plus the issue list at DEBUG level (issue messages can contain ids and field values from the file)

C) No U2-specific logging

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9
Which property-based test generators and settings does U2 use (PBT-07, PBT-08)?

A) As Functional Design §6: a valid `TripFile` strategy (1-10 stops, 0-15 notes, 0-15 photos, times 2000-2099 whole seconds, offsets in steps of 15 in -720..840, stop durations 0-36 h, unique ids, printable Unicode incl. non-Latin text) in the shared `tests/strategies.py`; plus mutation strategies built from it for the invalid cases (unknown key, end before start, many issues for P-I5). P-I2 (import then read back) uses a fresh in-memory database per example. Same `default` / `ci` profiles as U1; no new profile

B) Same, plus a `large` profile that generates up to 300 stops for the round trip

C) Only P-I1 and P-D1..P-D3 as property tests; the rest as example tests

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10
Does U2 need the NFR Design stage? (`unit-of-work.md` expects it to be skipped: no NFR patterns beyond validation.)

A) Skip NFR Design for U2. The answers above (in-request import, one explicit transaction, 409 on a running job, per-request day index, logging lines) are concrete enough to code directly; they are written as implementation notes in `nfr-requirements.md`. Next stage: Code Generation

B) Execute NFR Design, because of the transaction and large-file handling choices

C) Decide after reading the NFR Requirements artifacts

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## How to check the large-trip targets (for reference, not a question)
If Question 2 is A or B, Code Generation adds a script `scripts/make_large_trip.py` (or a test helper) that writes the reference trip file from a fixed seed, and a timing test marked `slow` that is skipped in the normal run and run in Build and Test. The generated file is not committed.
