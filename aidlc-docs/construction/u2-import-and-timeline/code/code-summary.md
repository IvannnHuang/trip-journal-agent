# U2 Import and Timeline - Code Summary

**Stage**: Code Generation (Part 2 done 2026-11-27). Build and Test not started.
**Plan**: `aidlc-docs/construction/plans/u2-import-and-timeline-code-generation-plan.md` (26/26 steps ticked)
**Tag**: new files carry `ADDED [PROMPT #17]`; changed U1 files carry `CHANGED [PROMPT #17]` (test steps 18-26 were done under the same prompt tag, PROMPT_LOG #18).

## Application code (`trip_journal/`, steps 1-17)
| Package | Files | Role |
|---|---|---|
| `domain/` | `import_schema.py`, `days.py`, `views.py` | strict Pydantic trip-file schema, ordered issues (max 50 + `more`), duplicate keys keep the last value (FA-3); local-date and day rules DD-1..DD-6, photo placement; frozen view models |
| `services/` | `imports.py`, `trips.py`; `errors.py`, `jobs.py` (U1, changed) | all-or-nothing import in one `BEGIN IMMEDIATE` transaction, 409 `trip_exists`; trip list, active trip with fallback, day view, delete refused with 409 `job_running`; `job_cancelled` (CI-3) |
| `data/` | `repositories.py` (U1, changed) | trip/stop/note/photo insert and list helpers |
| `api/` | `trips.py`, `days.py`; `deps.py` (U1, changed) | `/api/trips` (list, import, get, delete), `/api/trips/{id}/days/{date}` (422 `invalid_date`) |
| `pages/` | `trips.py`, `days.py`, templates `trips/*`, `days/day.html`, `errors/404.html`, `_partials/{import_form,import_issues,stop_item}.html`; `render.py`, `base.html`, `app.css` (U1, changed) | trip list + import, overview, day timeline (`[` / `]` keys), delete confirmation, 404 page |
| root | `main.py`, `config.py` (U1, changed) | `/` -> `/trips` (D-2), `TRIP_JOURNAL_PORT` override (CI-1) |
| docs / data | `docs/import-format.md`, `sample_data/minimal_trip.json` | file format for users; the Lisbon sample trip |

## Tests (`tests/`, steps 18-24)
- `strategies.py` (U1, changed): `trip_files()` plus mutations `with_unknown_key`, `with_end_before_start`, `with_many_issues`.
- `fixtures/__init__.py`: `minimal_trip_bytes`, `make_services`, sample loaders.
- `unit/`: `test_days.py`, `test_import_schema.py`, `test_imports_service.py` (incl. T.3 injected photo-insert failure -> rollback), `test_trips_service.py`, `test_views.py` (sample golden values); U1 `test_jobs.py` gains the cancel -> `job_cancelled` test, `test_errors.py` maps `JobCancelledError`.
- `api/`: `test_trips_api.py`, `test_days_api.py`, `test_trip_pages.py`; U1 `test_pages.py` renamed to `test_root_redirects_to_trips` (D-2).
- `property/`: `test_import_props.py` (P-I1 round trip, P-I2 read-back, P-I3 unknown key, P-I4 end before start + nothing stored, P-I5 issue cap), `test_days_props.py` (P-D1..P-D8, `show_offsets` iff mixed).
- `perf/test_import_speed.py` (`@pytest.mark.slow`, deselected by default via `pyproject.toml` D-9) and `scripts/make_reference_trip.py` (seed 5940; writes git-ignored `sample_data/generated/`).

## Results (2026-11-27, Windows laptop)
| Check | Result |
|---|---|
| `uv run pytest --cov` | 275 passed, 3 deselected (slow), 1 warning, 98 s; total coverage 97% |
| U2 module coverage | 100%: `api/days.py`, `api/trips.py`, `domain/days.py`, `domain/views.py`, `pages/days.py`, `pages/trips.py`, `services/imports.py`; `domain/import_schema.py` 98%; `services/trips.py` 99% (target >= 80%, T.1) |
| `HYPOTHESIS_PROFILE=ci pytest tests/property` | 33 passed, 347.9 s (500 examples per property) |
| `ruff check` / `ruff format --check` on `trip_journal tests` | clean (77 files formatted) |
| `mypy --strict trip_journal tests scripts/make_reference_trip.py` | clean (77 files) |

### Speed (`pytest -m slow -s`, 3 passed in 6.3 s; targets from U2-NFR P.1-P.4)
| Check | Time | Target |
|---|---|---|
| P.1 sample import | 0.146 s | 1 s |
| P.2 reference import (14 days, 300 stops, 2,000 notes, 3,000 photos; 0.83 MB) | 0.308 s | 5 s |
| P.3 19.71 MB import | 1.739 s | 15 s |
| P.4 `GET /trips` | 0.069 s | 0.3 s |
| P.4 busiest day page | 0.077 s | 0.3 s |

Timings are in-process (`TestClient`, in-memory SQLite), so they leave out network and disk; Build and Test can repeat them against a file DB.

## Deviations
- No app bugs were found by the U2 tests; no app code changed in steps 18-26.
- Tests that need "a job is running" monkeypatch the `JobRunner.running` property instead of starting a real job (simpler and deterministic).
- Removed one unused `type: ignore` in `tests/unit/test_views.py` found by `mypy --strict` on `tests`.

## Notes and known gaps
- `scripts/model_spike.py` (U1 spike, out of scope) still has 4 ruff E501 errors; `trip_journal`, `tests` and the new generator script are clean.
- Observation for review (not a bug): TL-5 may expect each photo to show its coordinates or "no location"; the day page lists photos by time and file name only. Owner to decide if this is a spec gap.
- Not verified: the pages in a real browser (htmx swap of 422/409, `[` / `]` keys, "Importing…" indicator). This belongs to Build and Test.
