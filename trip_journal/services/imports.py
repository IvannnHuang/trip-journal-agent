# ADDED [PROMPT #17]: ImportService (C03): validate, store in one transaction, set active.
# AI-assisted, Claude Opus 5.5.
"""Import one trip file (IM-1..IM-17, R.1..R.3, L.1, L.3).

The file is only parsed as JSON and checked by Pydantic; nothing in it is executed.
The file name is never used to decide the type (IM-3).
"""

from __future__ import annotations

import logging
import sqlite3
import time

from trip_journal.config import MAX_IMPORT_BYTES
from trip_journal.data.repositories import Repositories
from trip_journal.domain.days import local_date
from trip_journal.domain.import_schema import StopIn, TripFile, TripFileError, parse_trip_file
from trip_journal.domain.views import TripSummary
from trip_journal.logs import kv
from trip_journal.services.errors import ImportValidationError, TripAlreadyExistsError
from trip_journal.services.trips import TripService

log = logging.getLogger(__name__)


def _is_file_error(exc: TripFileError) -> bool:
    return len(exc.issues) == 1 and exc.issues[0].location == "file"


def _stop_key(stop: StopIn) -> tuple[str, str, str, str]:
    """DD-1 day, then the DD-4 order (start, end, file id)."""
    day = local_date(stop.start_utc, stop.utc_offset_minutes)
    return (day, stop.start_utc, stop.end_utc, stop.id)


class ImportService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        repos: Repositories,
        trips: TripService,
        max_bytes: int = MAX_IMPORT_BYTES,
    ) -> None:
        self.conn = conn
        self.repos = repos
        self.trips = trips
        self.max_bytes = max_bytes

    def import_trip(self, raw: bytes, filename: str | None = None) -> TripSummary:
        """Parse, refuse duplicates, store everything or nothing, make the trip active."""
        del filename  # kept for the C03 signature; never trusted (IM-3, U2-NFR-SP.2)
        started = time.perf_counter()
        try:
            trip_file = parse_trip_file(raw, self.max_bytes)
        except TripFileError as exc:
            result = "file_error" if _is_file_error(exc) else "invalid"
            self._log(started, result, issues=len(exc.issues) + exc.more)
            raise ImportValidationError(exc.issues, exc.more) from None
        source_id = trip_file.trip.trip_id
        if self.repos.trips.get_by_source_id(source_id) is not None:
            self._log(started, "exists", source_id)
            raise TripAlreadyExistsError(source_id)
        try:
            trip_id = self._store(trip_file)
        except sqlite3.IntegrityError as exc:
            if "trips.source_id" not in str(exc):
                raise
            self._log(started, "exists", source_id)  # a parallel import won the race (R.3)
            raise TripAlreadyExistsError(source_id) from None
        self.trips.set_active_trip(trip_id)  # AT-1
        self._log(
            started,
            "ok",
            source_id,
            stops=len(trip_file.stops),
            notes=len(trip_file.notes),
            photos=len(trip_file.photos),
        )
        return self.trips.get_summary(trip_id)

    def _store(self, data: TripFile) -> int:
        """R.1 / D-6: one explicit transaction; any failure stores nothing."""
        if self.conn.in_transaction:
            self.conn.commit()  # sqlite3 refuses BEGIN inside an open implicit transaction
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            trip_id = self.repos.trips.add(
                data.trip.trip_id,
                data.trip.title,
                home_timezone=data.trip.home_timezone,
                route_summary=data.route_summary,
                commit=False,
            )
            stops: dict[str, tuple[int, str]] = {}  # file id -> (row id, local day)
            for stop in sorted(data.stops, key=_stop_key):
                row_id = self.repos.stops.add(
                    trip_id,
                    stop.id,
                    stop.name,
                    stop.start_utc,
                    stop.end_utc,
                    stop.utc_offset_minutes,
                    stop.lat,
                    stop.lon,
                    commit=False,
                )
                stops[stop.id] = (row_id, _stop_key(stop)[0])
            for note in data.notes:
                linked = stops[note.stop_id] if note.stop_id is not None else None
                self.repos.notes.add(
                    trip_id,
                    note.id,
                    note.text,
                    note.time_utc,
                    note.utc_offset_minutes,
                    stop_id=linked[0] if linked else None,
                    local_date=linked[1] if linked else None,  # DD-3: the stop's day
                    commit=False,
                )
            for photo in data.photos:
                self.repos.photos.add(
                    trip_id,
                    photo.id,
                    photo.time_utc,
                    photo.utc_offset_minutes,
                    lat=photo.lat,
                    lon=photo.lon,
                    file_name=photo.file_name,
                    commit=False,
                )
        except BaseException:
            self.conn.rollback()
            raise
        self.conn.commit()
        return trip_id

    def _log(
        self,
        started: float,
        result: str,
        source_id: str = "-",
        stops: int = 0,
        notes: int = 0,
        photos: int = 0,
        issues: int = 0,
    ) -> None:
        # L.1 / L.3: ids, counts and timing only; never titles, text, messages or coordinates.
        log.info(
            kv(
                "trip.import",
                result=result,
                trip_id=source_id,
                stops=stops,
                notes=notes,
                photos=photos,
                issues=issues,
                duration_ms=round((time.perf_counter() - started) * 1000),
            )
        )
