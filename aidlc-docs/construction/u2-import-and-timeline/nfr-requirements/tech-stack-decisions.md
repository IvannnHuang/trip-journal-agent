# U2 Import and Timeline - Tech Stack Decisions

**Stage**: Construction - NFR Requirements (plan step 5)
**Source**: U1 `tech-stack-decisions.md`, `pyproject.toml`, plan answers Q4, Q5, Q7, Q9 (all A, owner, 2026-11-27)
**Scope**: U2 adds **no new runtime or dev dependency**. This file records what U2 reuses and the U2-level choices.

---

## 1. Runtime (reused from U1)

| Area | Choice | U2 use |
|---|---|---|
| Language | Python 3.12+ | all code |
| Web | FastAPI, uvicorn, Jinja2, htmx 2.0.4 (vendored by U1) | trip list, import form, day page, delete confirmation, trips / days API |
| Uploads | `python-multipart` (already in `pyproject.toml`, `>=0.0.34`, locked in `uv.lock`) | `UploadFile` for the import form and API |
| Validation | Pydantic v2, strict types, `extra="forbid"` | `TripFile` import schema (C17) |
| Database | `sqlite3` direct, called in the event loop (U1 NFR Design); default rollback journal, no WAL | one explicit `BEGIN IMMEDIATE` transaction per import (Q5 A) |
| Concurrency | none added: import runs in the request (Q4 A); no thread pool, no JobRunner job | |
| Not used | anything under "Do NOT Use" in `technical-environment.md`; no new library for JSON, dates or caching | NFR-6.2 |

Rejected: parsing in a worker thread (Q4 B, more moving parts for a single user); import as a JobRunner job (Q4 C, would block model jobs and needs polling); WAL mode (Q5 B, no need with one writer); a day-index cache (Q3 B, invalidation cost, not needed at the reference size).

## 2. Testing (reused from U1)

| Decision | Value |
|---|---|
| Runner | pytest, pytest-cov (≥ 80% on U2 modules), FastAPI `TestClient` |
| PBT framework | Hypothesis (PBT-09 decided in U1) |
| Profiles | `default` 100 examples, `ci` 500, `print_blob=True`, `deadline=None`; `HYPOTHESIS_PROFILE`; seed passed in the pre-merge run. No new profile (Q9 A; `large` profile rejected) |
| Strategies | extend the shared `tests/strategies.py` with the `TripFile` strategy and its mutation strategies |
| Slow tests | a `slow` pytest marker, skipped by default, for the large-trip timing check (U2-NFR-T.7); registered in `pyproject.toml` at Code Generation |
| Lint / types | ruff, mypy strict |

## 3. Dependency versions

No change. `pyproject.toml` keeps lower bounds; `uv.lock` stays the source of exact versions (`uv sync --locked`). If Code Generation finds a library is missing, it is added with `uv add` and recorded, not assumed.

## 4. Logging

U1 setup (`logging`, console, key=value, `TRIP_JOURNAL_LOG_LEVEL`). U2 adds the import and delete lines in `nfr-requirements.md` §6.
