# ADDED [PROMPT #17]: shared trip fixtures for U2-U6 tests. AI-assisted, Claude Opus 5.5.
"""Load the Lisbon sample trip through ImportService and map file ids to row ids."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from trip_journal.data.repositories import Repositories
from trip_journal.domain.views import TripSummary
from trip_journal.services.imports import ImportService
from trip_journal.services.jobs import JobRunner
from trip_journal.services.trips import TripService

MINIMAL_TRIP_PATH = Path(__file__).resolve().parents[2] / "sample_data" / "minimal_trip.json"
MINIMAL_SOURCE_ID = "minimal-lisbon-2026-05"


@dataclass
class Services:
    repos: Repositories
    jobs: JobRunner
    trips: TripService
    imports: ImportService


def make_services(conn: sqlite3.Connection, jobs: JobRunner | None = None) -> Services:
    repos = Repositories.from_connection(conn)
    runner = jobs or JobRunner()
    trips = TripService(repos, runner)
    return Services(repos, runner, trips, ImportService(conn, repos, trips))


def minimal_trip_bytes() -> bytes:
    return MINIMAL_TRIP_PATH.read_bytes()


def load_minimal_trip(services: Services) -> TripSummary:
    """Import `sample_data/minimal_trip.json` into the test database."""
    return services.imports.import_trip(minimal_trip_bytes(), "minimal_trip.json")


def minimal_trip_ids(conn: sqlite3.Connection) -> dict[str, int]:
    """File id (`"s4"`, `"n6"`, `"p10"`) -> row id for the loaded sample trip."""
    ids: dict[str, int] = {}
    for table in ("stops", "notes", "photos"):
        rows = conn.execute(
            f"SELECT x.source_id, x.id FROM {table} x JOIN trips t ON t.id = x.trip_id"
            " WHERE t.source_id = ?",
            (MINIMAL_SOURCE_ID,),
        )
        ids.update({str(r[0]): int(r[1]) for r in rows})
    return ids
