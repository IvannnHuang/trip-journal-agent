# U2 Import and Timeline - Code Generation Plan

**Unit**: U2 Import and Timeline
**Stories**: see `aidlc-docs/inception/application-design/unit-of-work-story-map.md` (U2 rows)
**Inputs**: `construction/u2-import-and-timeline/functional-design/` (4 files), `construction/u2-import-and-timeline/nfr-requirements/` (2 files), U1 code summary, `unit-of-work.md`
**Status**: Part 1 approved 2026-11-27T02:02:34Z (CI-3 in U2, FA-3 last key wins); Part 2 in progress (steps 1-17 done; tests and verification steps 18-26 open)
**Layout**: monolith package `trip_journal/` + `tests/` (U1 deviation D-1 still holds). No new runtime dependency. No schema change.

Legend: **[U1]** = the step edits a file that U1 created. Every other path is new.

## Deviations and decisions

| ID | Item | Decision | Why |
|---|---|---|---|
| D-1 | Sample path | `sample_data/minimal_trip.json` (unit-of-work), not `samples/minimal-lisbon-2026-05.json` (frontend design 4) | unit-of-work is the source of record; frontend text is updated to match |
| D-2 | `/` route **[U1]** | 307 to `/trips` instead of `/settings`; U1 test `test_root_redirects_to_settings` renamed and updated | U1 comment said U2 replaces it |
| D-3 | `NotFoundError` **[U1]** | gets an optional `code` (default `job_not_found`), so U2 raises `trip_not_found` / `day_not_found` with no change to U1 behaviour | IC-5 |
| D-4 | New errors **[U1 errors.py]** | `ImportValidationError` 422 `import_invalid`, `TripAlreadyExistsError` 409 `trip_exists`, `JobRunningError` 409 `job_running`; file-level refusals (size / encoding / JSON / XML) are a `TripFileError` with one issue at location `file`, wrapped into `ImportValidationError` (`import_invalid`, message = that issue) | IC-5, R.5 |
| D-5 | Repositories **[U1]** | `add` methods get `commit: bool = True`; `NoteRepository.add` gets `local_date: str \| None = None`; local dates come from `domain.days.local_date` | IC-1..IC-3; defaults keep U1 callers and tests unchanged |
| D-6 | Transaction | `services/imports.py` commits any open implicit transaction, then runs `BEGIN IMMEDIATE`, inserts with `commit=False`, `COMMIT`; `ROLLBACK` on `BaseException` | R.1; Python sqlite3 errors on BEGIN inside an open transaction |
| D-7 | Port **[U1 config.py, main.py]** | `TRIP_JOURNAL_PORT` env, default 8000, invalid value logs a warning and uses 8000 | CI-1 |
| D-8 | `base.html` **[U1]** | adds the active-trip indicator (title or "No trip selected"); `render_page` **[U1]** passes `active_trip` into every full page | AT-5 |
| D-9 | `pyproject.toml` **[U1]** | adds pytest marker `slow`, deselected by default with `-m "not slow"` in addopts | NFR timing test |
| D-10 | FA-3 duplicate JSON keys | parse with `json.loads(object_pairs_hook=...)` that keeps the last value (same as stdlib default); no issue raised. A test pins the behaviour | owner confirmed last key wins |
| D-11 | CI-3 `job_cancelled` **[U1 jobs.py, errors.py, 2 U1 tests]** | **Approved: lands in U2.** new `JobCancelledError` -> code `job_cancelled`, message "The job was cancelled. Nothing was changed."; `JobRunner._run` uses it on `CancelledError`; `test_jobs.py` and `test_errors.py` updated | carry-in from U1 build and test |

## Steps

### A. Domain (pure)
- [x] 1. `trip_journal/domain/days.py` - `local_date`, `local_time`, `group_stops_by_day`, `build_day_index`, `assign_photos`, `ends_next_day` / day-span label, `offset_label`, `show_offsets`, `day_heading`, prev/next helpers. Pure, no I/O.
- [x] 2. `trip_journal/domain/import_schema.py` - Pydantic v2 strict models TripMeta, StopIn, NoteIn, PhotoIn, TripFile, ImportIssue; `parse_trip_file(raw, max_bytes) -> TripFile` raising `ImportValidationError`; IM-1..IM-17 checks (size, BOM, UTF-8, XML sniff, JSON position, single object, schema message map, cross-record checks, sort by file position, cap 50 + `more`), FA-2 time normalisation.
- [x] 3. `trip_journal/domain/views.py` - frozen dataclasses DaySummary, TripSummary, PhotoMeta, NoteItem, StopTimelineItem, DayView, DeletePreview (IC-4).

### B. Data and errors (U1 edits)
- [x] 4. **[U1]** `trip_journal/data/repositories.py` - D-5; plus small read helpers U2 needs: `StopRepository.list_for_trip`, `NoteRepository.list_for_trip`, `PhotoRepository.list_for_trip`, `TripRepository.counts(trip_id)`. One query per record type (N-6).
- [x] 5. **[U1]** `trip_journal/services/errors.py` - D-3, D-4 and their `to_user_facing` mappings and D-11.
- [x] 6. **[U1]** `trip_journal/services/jobs.py` - D-11.

### C. Services
- [x] 7. `trip_journal/services/imports.py` - `ImportService.import_trip(raw: bytes, filename: str) -> TripSummary`: parse, duplicate check, D-6 transaction, DD-4 stop order, IntegrityError -> `TripAlreadyExistsError`, sets active trip, L.1 log line (no content, L.3).
- [x] 8. `trip_journal/services/trips.py` - `TripService`: `list_trips`, `get_summary`, `get_active_trip_id` (AT-3 fallback), `set_active_trip`, `get_day` -> DayView, `get_delete_preview`, `delete_trip` (refuses with `JobRunningError` while `JobRunner.running` is set; L.2 log line).
- [x] 9. **[U1]** `trip_journal/api/deps.py` + `trip_journal/main.py` - add `imports` and `trips` services to AppState; include the four new routers; D-2; D-7. **[U1]** `trip_journal/config.py` - `PORT_ENV`, `MAX_IMPORT_BYTES = 20 * 1024 * 1024`.

### D. API
- [x] 10. `trip_journal/api/trips.py` - GET/POST `/api/trips` (201, 422 `{code, message, issues, more}`, 409), GET `/api/trips/{id}`, DELETE `/api/trips/{id}` (204, 404, 409 `job_running`). Upload read is capped at `MAX_IMPORT_BYTES + 1` (N-1).
- [x] 11. `trip_journal/api/days.py` - GET `/api/trips/{id}/days/{date}` (404 trip / day, 422 bad date).

### E. Pages and templates
- [x] 12. `trip_journal/pages/trips.py` - GET `/trips` (CI-2), POST `/trips/import` (303 or re-render with 422/409), POST `/trips/{id}/activate`, GET `/trips/{id}`, GET and POST `/trips/{id}/delete` ("Trip deleted." flash via query flag).
- [x] 13. `trip_journal/pages/days.py` - GET `/trips/{id}/days/{date}` (404 page on bad date / unknown trip / empty day).
- [x] 14. **[U1]** `trip_journal/pages/render.py` + **[U1]** `pages/templates/base.html` - D-8.
- [x] 15. Templates `pages/templates/trips/list.html`, `trips/overview.html`, `trips/delete.html`, `days/day.html`, `_partials/import_form.html`, `_partials/import_issues.html`, `_partials/stop_item.html`; htmx form (U.1), `<details>` photos (TL-5), `<time datetime>`, `data-testid` `{component}-{element-role}`, `[` / `]` shortcuts in a small inline script; **[U1]** `static/app.css` - timeline classes only.

### F. Sample and docs
- [x] 16. `sample_data/minimal_trip.json` - the Lisbon trip exactly as in the functional design.
- [x] 17. `docs/import-format.md` - schema, limits, error messages, sample as example.

### G. Tests
- [x] 18. **[U1]** `tests/strategies.py` - `trip_files()` strategy and mutation strategies (unknown key, end before start, many issues).
- [x] 19. `tests/fixtures/__init__.py` - `load_minimal_trip(services)`, `minimal_trip_ids(conn)`.
- [x] 20. Unit tests: `tests/unit/test_days.py`, `test_import_schema.py`, `test_imports_service.py` (incl. T.3 injected photo-insert failure), `test_trips_service.py`, `test_views.py` (sample golden values).
- [x] 21. API / page tests: `tests/api/test_trips_api.py`, `test_days_api.py`, `test_trip_pages.py`; **[U1]** `tests/api/test_pages.py` (D-2).
- [x] 22. Property tests: `tests/property/test_import_props.py` (P-I1..P-I5), `tests/property/test_days_props.py` (P-D1..P-D8).
- [x] 23. `tests/perf/test_import_speed.py` (`@pytest.mark.slow`) + `scripts/make_reference_trip.py` (fixed seed; output not committed, path git-ignored). **[U1]** `pyproject.toml` D-9; **[U1]** `.gitignore` adds `/sample_data/generated/`.
- [x] 24. **[U1]** `tests/unit/test_jobs.py`, `tests/unit/test_errors.py`.

### H. Verify and record
- [x] 25. `uv run pytest --cov` (U2 modules >= 80%, T.1), `HYPOTHESIS_PROFILE=ci` in background, `ruff check trip_journal tests`, `ruff format --check`, `mypy --strict`.
- [x] 26. `aidlc-docs/construction/u2-import-and-timeline/code/code-summary.md`; tick this plan; aidlc-state; audit; PROMPT_LOG #17+.

## Test list (T.2 traceability)

| Case | Test file |
|---|---|
| POST /api/trips 201 + summary counts 4/8/10 | test_trips_api |
| 422 import_invalid with issues, more | test_trips_api, test_trip_pages (page re-render 422) |
| 409 trip_exists (repeat import, and IntegrityError race) | test_trips_api, test_imports_service |
| 409 job_running on DELETE / delete page | test_trips_api, test_trip_pages |
| 404 trip_not_found / day_not_found; 422 bad date in API, 404 on page | test_days_api, test_trip_pages |
| 204 DELETE, then 404 | test_trips_api |
| Delete confirmation text and 303 "Trip deleted." | test_trip_pages |
| GET /trips 200 (CI-2), `/` -> /trips | test_trip_pages, test_pages |
| Active trip set by import / open / activate, fallback after delete | test_trips_service, test_trip_pages |
| File errors: empty, >20 MB, non-UTF-8, BOM, XML, bad JSON position, array top level | test_import_schema |
| Field messages, duplicate id, missing stop, end before start, 50 cap | test_import_schema |
| FA-2 fractions cut, FA-3 last key wins | test_import_schema |
| Sample day view: s4 "+1 day", n6 unlinked, p6 other, show_offsets false | test_views / test_trips_service |
| T.3 rollback leaves 0 rows, next import works | test_imports_service |
| Logs: one line, no content (L.1-L.3) | test_imports_service, test_trips_service (caplog) |
| Text escaping (TL-8) | test_trip_pages |

## PBT mapping

| Rule | Property | Test |
|---|---|---|
| PBT-02 round trip (blocking) | P-I1 `parse_trip_file(dump(t)) == t` | test_import_props |
| PBT-02 (advisory) | P-I2 import then read back equals input | test_import_props |
| PBT-03 invariants (blocking) | P-D1 partition, P-D2 key = local date of start, P-D3 sorted, P-D4 date/offset monotonic and +24 h, P-D5 day index sorted unique with prev/next inverse, P-D6 notes on their stop's day, P-D7 photo in at most one containing window, P-D8 count sums | test_days_props |
| PBT-03 error invariants | P-I3 unknown key located, P-I4 end before start located and nothing stored, P-I5 `len(issues) + more == total`, len <= 50 | test_import_props |
| PBT-07 generators | `tests/strategies.py` trip_files + mutations | - |
| PBT-08 shrinking / repro | `print_blob=True`, profiles `default` / `ci` | conftest (U1) |
| PBT-09 framework | Hypothesis (U1 decision) | - |

## Owner answers (Part 1)
- CI-3: answered - lands in U2 (D-11). FA-3: answered - last key wins (D-10).
