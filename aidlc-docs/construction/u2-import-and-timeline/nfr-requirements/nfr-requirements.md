# U2 Import and Timeline - NFR Requirements

**Stage**: Construction - NFR Requirements (plan step 4)
**Source**: `aidlc-docs/construction/plans/u2-import-and-timeline-nfr-requirements-plan.md` (10 answers, all A, owner, 2026-11-27), `requirements.md` NFR-1 to NFR-7, U2 Functional Design (`business-rules.md`, `business-logic-model.md`), U1 `nfr-requirements.md`
**Scope**: the non-functional requirements U2 code must meet. Ids `U2-NFR-<area>.<n>`. U1 requirements (U1-NFR-*) still apply and are not repeated unless U2 adds to them. Because NFR Design is skipped (Q10 A), section 9 gives implementation notes for Code Generation.

---

## 1. Performance

All speed numbers are **targets**, measured in Build and Test on the measured laptop (same rule as U1-NFR-P.1). A miss is recorded with the laptop model, memory and timing; it does not block the unit (Q1 A, Q3 A).

| Id | Requirement | Source |
|---|---|---|
| U2-NFR-P.1 | The minimal sample trip (`sample_data/minimal_trip.json`) imports in ≤ 1 s (request start to response). | Q1 A |
| U2-NFR-P.2 | The reference large trip (S.2, about 1-2 MB) imports in ≤ 5 s. | Q1 A |
| U2-NFR-P.3 | A file near the 20 MB limit (the reference trip with long note texts) imports in ≤ 15 s. | Q1 A, IM-1 |
| U2-NFR-P.4 | Server time for the trip list (`GET /trips`) and for one day page of the reference trip is ≤ 300 ms each. | Q3 A |
| U2-NFR-P.5 | The day index (DD-5) and photo placement (DD-6) are computed per request from SQL; there is no cache. Every query reads one trip (AT-5). | Q3 A, business-logic 3.3 |
| U2-NFR-P.6 | At most 20 MB + 1 byte of an upload is read into memory; the size check runs before decoding or parsing (IM-1). | business-logic 1 step 1 |
| U2-NFR-P.7 | Import, timeline and delete never call the model, PlaceLookup or JobRunner, so they are unaffected by model speed and work with Ollama down. | business-logic 1, TL-4 |

## 2. Scalability

| Id | Requirement | Source |
|---|---|---|
| U2-NFR-S.1 | Single user on one laptop (U1-NFR-S.1). No load target. | NFR-3.1 |
| U2-NFR-S.2 | **Reference large trip**: 14 days, 300 stops, 2,000 notes, 3,000 photos, generated from a fixed seed. The app must import, list and show it within P.2-P.4. | Q2 A |
| U2-NFR-S.3 | No limit on record counts beyond the 20 MB file limit. | Q2 A |

## 3. Reliability and transaction safety

Resiliency Baseline: opted out. These are the project's own rules.

| Id | Requirement | Source |
|---|---|---|
| U2-NFR-R.1 | The import write is one explicit transaction: `BEGIN IMMEDIATE`, all rows (trip, stops, notes, photos, FTS rows via U1 triggers), `COMMIT`; `ROLLBACK` on any exception. Nothing of the trip is stored if any step fails (IM-16). | Q5 A |
| U2-NFR-R.2 | A crash or killed server mid-import leaves nothing of that trip stored (SQLite rollback journal; no WAL change). | Q5 A |
| U2-NFR-R.3 | A parallel import of the same `trip_id` ends with 409 `trip_exists` from the `trips.source_id` unique constraint (`sqlite3.IntegrityError` mapped, IM-15). | Q5 A |
| U2-NFR-R.4 | The import runs inside the request, in the event loop, as U1 does (U1 NFR Design: `sqlite3` direct). Other requests wait while it runs; this is accepted for a single user. | Q4 A |
| U2-NFR-R.5 | Delete is refused while any job is running: the confirmation page (`GET` and `POST /trips/{id}/delete`) and `DELETE /api/trips/{id}` return 409 `job_running` with "A job is running. Wait for it to finish or cancel it, then delete the trip." The check uses `JobRunner.running`; nothing is deleted. | Q6 A |
| U2-NFR-R.6 | Delete is one statement (`DELETE FROM trips WHERE id = ?`) in one transaction; the cascade removes all child rows (DL-4). | DL-4 |
| U2-NFR-R.7 | Expected failures give the fixed 422 / 409 / 404 responses; an unexpected exception gives U1's `internal_error` (ER-1). The server keeps running and nothing is partly stored. | NFR-4.2, U1-NFR-R.4 |

## 4. Security and privacy

Security Baseline: opted out (skipped). Project rules still apply.

| Id | Requirement | Source |
|---|---|---|
| U2-NFR-SP.1 | Every import file and request body is validated by Pydantic models (`extra="forbid"`, strict types, FA-1). | NFR-3.2, IM-5, IM-6 |
| U2-NFR-SP.2 | No `eval`, `exec` or `pickle` on imported data; the file name and content type are never trusted (IM-3). | NFR-3.3, IM-16 |
| U2-NFR-SP.3 | Note text, titles and names are shown escaped (Jinja autoescape); never marked safe. | TL-8, NFR-3.4 |
| U2-NFR-SP.4 | SQL uses parameters only; no string-built SQL. | NFR-6.3 |
| U2-NFR-SP.5 | Upload size is capped before parsing (P.6), so a huge upload cannot exhaust memory. | IM-1 |

## 5. Usability

| Id | Requirement | Source |
|---|---|---|
| U2-NFR-U.1 | While an import runs, the submit button is disabled and shows "Importing…" (`hx-disabled-elt`, `hx-indicator`); a double click cannot send two imports. No progress bar. | Q7 A |
| U2-NFR-U.2 | Error messages use the fixed wording in IM-1..IM-15, TL-1, TL-2 and R.5; issues name the field and record. | NFR-5.2 |
| U2-NFR-U.3 | Semantic HTML, keyboard use, readable contrast; disabled prev/next links use `aria-disabled` (TL-7). | NFR-5.1, US-04 |

## 6. Logging

Same library, output and format as U1 (U1-NFR-L.1, U1 NFR Design key=value lines).

| Id | Requirement | Source |
|---|---|---|
| U2-NFR-L.1 | One INFO line per import: `result` (`ok`, `invalid`, `exists`, `file_error`), `trip_id` (the file's `trip.trip_id` when known), `stops`, `notes`, `photos` counts, `issues` count, `duration_ms`. | Q8 A |
| U2-NFR-L.2 | One INFO line per delete: trip row id, `source_id`, counts of stops, notes and photos; a refused delete logs `result=job_running`. | Q8 A, R.5 |
| U2-NFR-L.3 | Never logged: issue messages, note text, titles, file content, coordinates. | Q8 A, U1-NFR-L.2 |

## 7. Maintainability

| Id | Requirement | Source |
|---|---|---|
| U2-NFR-M.1 | ruff (lint, format) and mypy strict pass on `trip_journal` and `tests`. | NFR-6.5, U2 DoD |
| U2-NFR-M.2 | Day derivation lives only in `domain/days.py` (`local_date` one function, IC-3); repositories call it. | IC-3 |
| U2-NFR-M.3 | Layers call downward only: pages / api → services → domain, repositories. | NFR-6.3 |
| U2-NFR-M.4 | `docs/import-format.md` documents the schema and uses the minimal sample trip as its full example. | US-01 rule |

## 8. Testability

| Id | Requirement | Source |
|---|---|---|
| U2-NFR-T.1 | pytest, ≥ 80% line coverage of U2 modules (`domain/import_schema.py`, `domain/days.py`, `services/imports.py`, `services/trips.py`, `api/trips.py`, `api/days.py`, `pages/trips.py`, `pages/days.py`). | NFR-7.1, U2 DoD |
| U2-NFR-T.2 | API and page tests (FastAPI `TestClient`) cover 201, 409 `trip_exists`, 409 `job_running`, 422 (file and record issues), 404 (`trip_not_found`, `day_not_found`), 204 and the confirmation flow; `GET /trips` returns 200 (CI-2). | NFR-7.3, U2 DoD |
| U2-NFR-T.3 | A transaction test injects a failure after some rows are written (for example the photo insert raises) and checks that zero rows of that trip remain and the 409 check still passes for a later import. | Q5 A |
| U2-NFR-T.4 | **PBT generators (PBT-07)**: the valid `TripFile` strategy in the shared `tests/strategies.py` as Functional Design §6 (1-10 stops, 0-15 notes, 0-15 photos; times 2000-01-01..2099-12-31 UTC whole seconds; offsets multiples of 15 in -720..840; stop durations 0-36 h; unique ids per type; notes optionally linked to generated stop ids; printable Unicode incl. non-Latin text). Invalid cases come from **mutation strategies** built on it: add an unknown key at a random object (P-I3), set a stop's `end_utc` before `start_utc` (P-I4), inject many issues (P-I5). Generators only produce inputs the business rules define as valid (or exactly one known defect for mutations). | Q9 A, PBT-07 |
| U2-NFR-T.5 | **Properties**: round trip P-I1 (PBT-02, blocking) and P-I2 (advisory; a fresh in-memory database per example); validation invariants P-I3..P-I5 and day invariants P-D1..P-D8 (PBT-03, blocking). | Q9 A, business-rules §6 |
| U2-NFR-T.6 | **Reproducibility (PBT-08)**: same `default` (100 examples) and `ci` (500) profiles as U1, `print_blob=True`, `deadline=None`, shrinking on; the pre-merge run passes `--hypothesis-seed`. No new profile. | Q9 A, U1-NFR-T.3/T.4 |
| U2-NFR-T.7 | **Timing check**: a script or test helper writes the reference large trip (S.2) and a near-20 MB variant from a fixed seed (not committed); a timing test marked `slow` is skipped in the normal run and run in Build and Test for P.1-P.4. | Q2 A, plan note |
| U2-NFR-T.8 | No test needs Ollama or network. | NFR-7.2 |

## 9. Implementation notes for Code Generation (NFR Design skipped, Q10 A)

| # | Note | From |
|---|---|---|
| N-1 | Import path: `await upload.read(20 * 1024 * 1024 + 1)` → size check → decode → hint → `TripFile.model_validate_json`-style parse with issue mapping → cross-record checks → duplicate check → write. All in the request handler. | P.6, R.4 |
| N-2 | Write: `conn.execute("BEGIN IMMEDIATE")`, repository `add` calls with `commit=False` (IC-2), `conn.commit()`; `except BaseException: conn.rollback(); raise`. Map `IntegrityError` on `trips.source_id` to `TripAlreadyExistsError`. | R.1, R.3 |
| N-3 | Delete: check `job_runner.running is not None` → raise a 409 error `job_running` (new code in `services/errors.py`, next to IC-5); else delete and pick the next active trip (AT-4). | R.5 |
| N-4 | Log lines with `time.perf_counter()` around the whole import; fields as L.1. | L.1 |
| N-5 | Import form: `hx-post`, `hx-encoding="multipart/form-data"`, `hx-disabled-elt="find button"`, `hx-indicator` text "Importing…"; the page also works without htmx (plain form post). | U.1 |
| N-6 | Day page: one query per record type for the trip, then pure functions `build_day_index`, `group_stops_by_day`, `assign_photos` in Python. U1's `schema.sql` already has `idx_stops_trip_day`, `idx_notes_trip_day` and `idx_photos_trip_time`; if P.4 is missed, check the query plans against these first, before any cache. | P.4, P.5 |

## 10. Changes to Functional Design

| Rule | Change | Source |
|---|---|---|
| DL-1, DL-3 | Delete (page and API) refused with 409 `job_running` while a job runs | Q6 A |
| IC-5 | Adds the error code `job_running` (409) | Q6 A |
| Frontend import form | Adds the disabled button and "Importing…" indicator | Q7 A |

## 11. Extension compliance

| Extension / rule | Status | Note |
|---|---|---|
| Security Baseline | N/A (opted out) | Skipped per `aidlc-state.md` |
| Resiliency Baseline | N/A (opted out) | Skipped per `aidlc-state.md` |
| PBT-09 framework selection (blocking) | Compliant | Hypothesis, decided in U1 and reused (`tech-stack-decisions.md` §2) |
| PBT-07 generator quality (blocking) | Compliant at requirements level | Generators specified in T.4; built and checked at Code Generation |
| PBT-08 shrinking and reproducibility (blocking) | Compliant at requirements level | T.6 |
| PBT-02, PBT-03 (blocking) | N/A at this stage | Properties listed in T.5; implemented at Code Generation |
| Other PBT rules (advisory) | N/A at this stage | P-I2 advisory |
