# ADDED [PROMPT #13]: repositories for U1 tables (C22). AI-assisted, Claude Opus 5.5.
"""Small repositories over one SQLite connection. Every query is scoped by trip id."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from trip_journal.domain.days import local_date as day_of
from trip_journal.domain.grounding import Citation

MIN_FTS_TERM_CHARS = 3


def utc_now_text() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text: str) -> datetime:
    """Parse stored UTC text into an aware datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def to_local(utc_text: str, offset_minutes: int) -> datetime:
    """UTC text + offset → naive local datetime."""
    return (parse_utc(utc_text) + timedelta(minutes=offset_minutes)).replace(tzinfo=None)


def local_iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class StopRow:
    id: int
    trip_id: int
    source_id: str
    name: str | None
    start_utc: str
    end_utc: str
    utc_offset_minutes: int
    local_date: str
    lat: float
    lon: float


@dataclass(frozen=True)
class NoteRow:
    id: int
    trip_id: int
    stop_id: int | None
    source_id: str
    text: str
    time_utc: str
    utc_offset_minutes: int
    local_date: str


@dataclass(frozen=True)
class PhotoRow:
    id: int
    trip_id: int
    source_id: str
    time_utc: str
    utc_offset_minutes: int
    local_time: str
    lat: float | None
    lon: float | None
    file_name: str | None


@dataclass(frozen=True)
class TripRow:
    id: int
    source_id: str
    title: str
    home_timezone: str | None
    route_summary: str | None
    imported_at: str


class TripRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        source_id: str,
        title: str,
        home_timezone: str | None = None,
        route_summary: str | None = None,
        commit: bool = True,
    ) -> int:
        # CHANGED [PROMPT #17]: `commit=False` lets ImportService write in one transaction (D-5).
        cur = self.conn.execute(
            "INSERT INTO trips (source_id, title, home_timezone, route_summary, imported_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (source_id, title, home_timezone, route_summary, utc_now_text()),
        )
        if commit:
            self.conn.commit()
        return int(cur.lastrowid or 0)

    def get(self, trip_id: int) -> TripRow | None:
        row = self.conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
        return TripRow(**dict(row)) if row else None

    def get_by_source_id(self, source_id: str) -> TripRow | None:
        row = self.conn.execute("SELECT * FROM trips WHERE source_id = ?", (source_id,)).fetchone()
        return TripRow(**dict(row)) if row else None

    def list(self) -> list[TripRow]:
        rows = self.conn.execute("SELECT * FROM trips ORDER BY imported_at DESC, id DESC")
        return [TripRow(**dict(r)) for r in rows]

    def delete(self, trip_id: int) -> None:
        self.conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        self.conn.commit()

    def known_citation_ids(self, trip_id: int) -> set[Citation]:
        """Every stop, note and photo id in the trip, for the grounding check."""
        known: set[Citation] = set()
        for kind, table in (("stop", "stops"), ("note", "notes"), ("photo", "photos")):
            rows = self.conn.execute(f"SELECT id FROM {table} WHERE trip_id = ?", (trip_id,))
            known.update(Citation(kind, int(r["id"])) for r in rows)
        return known

    # ADDED [PROMPT #17]: delete preview and summary counts (DL-2).
    def counts(self, trip_id: int) -> tuple[int, int, int]:
        """(stops, notes, photos) stored for the trip."""
        result: list[int] = []
        for table in ("stops", "notes", "photos"):
            row = self.conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE trip_id = ?", (trip_id,)
            ).fetchone()
            result.append(int(row[0]))
        return (result[0], result[1], result[2])


class StopRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        trip_id: int,
        source_id: str,
        name: str | None,
        start_utc: str,
        end_utc: str,
        utc_offset_minutes: int,
        lat: float,
        lon: float,
        commit: bool = True,
    ) -> int:
        # CHANGED [PROMPT #17]: one day rule (IC-3) and `commit` flag (D-5).
        local_date = day_of(start_utc, utc_offset_minutes)
        cur = self.conn.execute(
            "INSERT INTO stops (trip_id, source_id, name, start_utc, end_utc,"
            " utc_offset_minutes, local_date, lat, lon) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trip_id,
                source_id,
                name,
                start_utc,
                end_utc,
                utc_offset_minutes,
                local_date,
                lat,
                lon,
            ),
        )
        if commit:
            self.conn.commit()
        return int(cur.lastrowid or 0)

    def get(self, trip_id: int, stop_id: int) -> StopRow | None:
        row = self.conn.execute(
            "SELECT * FROM stops WHERE trip_id = ? AND id = ?", (trip_id, stop_id)
        ).fetchone()
        return StopRow(**dict(row)) if row else None

    # ADDED [PROMPT #17]: one query per record type for the day view (N-6).
    def list_for_trip(self, trip_id: int) -> list[StopRow]:
        rows = self.conn.execute(
            "SELECT * FROM stops WHERE trip_id = ? ORDER BY start_utc, end_utc, source_id",
            (trip_id,),
        )
        return [StopRow(**dict(r)) for r in rows]

    def list_for_day(self, trip_id: int, day: str) -> list[StopRow]:
        rows = self.conn.execute(
            "SELECT * FROM stops WHERE trip_id = ? AND local_date = ? ORDER BY start_utc, id",
            (trip_id, day),
        )
        return [StopRow(**dict(r)) for r in rows]

    def find_by_coordinates(self, trip_id: int, lat_key: str, lon_key: str) -> StopRow | None:
        """First stop whose rounded coordinates equal the keys (IC-9, PL-3).

        Rounding is done in Python with the same `cache_key` as the place cache, so
        both sides use one definition of "same place".
        """
        from trip_journal.places.lookup import cache_key  # local import: no cycle at load

        rows = self.conn.execute(
            "SELECT * FROM stops WHERE trip_id = ? ORDER BY start_utc, id", (trip_id,)
        )
        for r in rows:
            if cache_key(r["lat"]) == lat_key and cache_key(r["lon"]) == lon_key:
                return StopRow(**dict(r))
        return None

    def counts(self, trip_id: int, stop_id: int) -> tuple[int, int]:
        """(note_count, photo_count) for a stop. Photos count when inside the stop's time."""
        stop = self.get(trip_id, stop_id)
        if stop is None:
            return (0, 0)
        notes = self.conn.execute(
            "SELECT COUNT(*) FROM notes WHERE trip_id = ? AND stop_id = ?", (trip_id, stop_id)
        ).fetchone()[0]
        photos = self.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE trip_id = ? AND time_utc BETWEEN ? AND ?",
            (trip_id, stop.start_utc, stop.end_utc),
        ).fetchone()[0]
        return (int(notes), int(photos))


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_fts_query(terms: list[str]) -> str:
    """Each term as a quoted phrase (inner quotes doubled), joined by spaces (AND) (SN-2)."""
    return " ".join('"' + t.replace('"', '""') + '"' for t in terms)


def split_terms(query: str) -> list[str]:
    # CHANGED [PROMPT #13]: NUL ends a string inside SQLite (FTS "unterminated string",
    # LIKE "%\0%" matching everything), so treat it as whitespace. Found by P-Q1/P-Q2.
    return query.replace("\x00", " ").split()


class NoteRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        trip_id: int,
        source_id: str,
        text: str,
        time_utc: str,
        utc_offset_minutes: int,
        stop_id: int | None = None,
        local_date: str | None = None,
        commit: bool = True,
    ) -> int:
        # CHANGED [PROMPT #17]: a note on a stop takes the stop's day (DD-3), passed in as
        # `local_date`; otherwise its own time and offset decide (IC-3). `commit` flag (D-5).
        day = local_date or day_of(time_utc, utc_offset_minutes)
        cur = self.conn.execute(
            "INSERT INTO notes (trip_id, stop_id, source_id, text, time_utc,"
            " utc_offset_minutes, local_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trip_id, stop_id, source_id, text, time_utc, utc_offset_minutes, day),
        )
        if commit:
            self.conn.commit()
        return int(cur.lastrowid or 0)

    def update_text(self, note_id: int, text: str) -> None:
        self.conn.execute("UPDATE notes SET text = ? WHERE id = ?", (text, note_id))
        self.conn.commit()

    def delete(self, note_id: int) -> None:
        self.conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self.conn.commit()

    def list_for_stop(self, trip_id: int, stop_id: int) -> list[NoteRow]:
        rows = self.conn.execute(
            "SELECT * FROM notes WHERE trip_id = ? AND stop_id = ? ORDER BY time_utc, id",
            (trip_id, stop_id),
        )
        return [NoteRow(**dict(r)) for r in rows]

    # ADDED [PROMPT #17]: one query per record type for the day view (N-6).
    def list_for_trip(self, trip_id: int) -> list[NoteRow]:
        rows = self.conn.execute(
            "SELECT * FROM notes WHERE trip_id = ? ORDER BY time_utc, source_id",
            (trip_id,),
        )
        return [NoteRow(**dict(r)) for r in rows]

    def list_for_day(self, trip_id: int, day: str) -> list[NoteRow]:
        rows = self.conn.execute(
            "SELECT * FROM notes WHERE trip_id = ? AND local_date = ? ORDER BY time_utc, id",
            (trip_id, day),
        )
        return [NoteRow(**dict(r)) for r in rows]

    def search(self, trip_id: int, query: str, limit: int = 10) -> list[NoteRow]:
        """SN-1..SN-5. Raises ValueError when the query has no terms."""
        terms = split_terms(query)
        if not terms:
            raise ValueError("query has no search terms")
        if all(len(t) >= MIN_FTS_TERM_CHARS for t in terms):
            rows = self.conn.execute(
                "SELECT n.* FROM notes_fts JOIN notes n ON n.id = notes_fts.rowid"
                " WHERE notes_fts MATCH ? AND n.trip_id = ?"
                " ORDER BY bm25(notes_fts), n.time_utc, n.id LIMIT ?",
                (build_fts_query(terms), trip_id, limit),
            )
        else:
            where = " AND ".join("text LIKE ? ESCAPE '\\'" for _ in terms)
            params: list[object] = [trip_id, *(f"%{_escape_like(t)}%" for t in terms), limit]
            rows = self.conn.execute(
                f"SELECT * FROM notes WHERE trip_id = ? AND {where} ORDER BY time_utc, id LIMIT ?",
                params,
            )
        return [NoteRow(**dict(r)) for r in rows]


class PhotoRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        trip_id: int,
        source_id: str,
        time_utc: str,
        utc_offset_minutes: int,
        lat: float | None = None,
        lon: float | None = None,
        file_name: str | None = None,
        commit: bool = True,
    ) -> int:
        local_time = local_iso(to_local(time_utc, utc_offset_minutes))
        cur = self.conn.execute(
            "INSERT INTO photos (trip_id, source_id, time_utc, utc_offset_minutes, local_time,"
            " lat, lon, file_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (trip_id, source_id, time_utc, utc_offset_minutes, local_time, lat, lon, file_name),
        )
        # CHANGED [PROMPT #17]: `commit` flag (D-5).
        if commit:
            self.conn.commit()
        return int(cur.lastrowid or 0)

    # ADDED [PROMPT #17]: one query per record type for the day view (N-6).
    def list_for_trip(self, trip_id: int) -> list[PhotoRow]:
        rows = self.conn.execute(
            "SELECT * FROM photos WHERE trip_id = ? ORDER BY time_utc, source_id",
            (trip_id,),
        )
        return [PhotoRow(**dict(r)) for r in rows]

    def find_between(
        self, trip_id: int, start_local: datetime, end_local: datetime
    ) -> list[PhotoRow]:
        """Photos with start_local <= local_time <= end_local (TA-8, inclusive)."""
        rows = self.conn.execute(
            "SELECT * FROM photos WHERE trip_id = ? AND local_time BETWEEN ? AND ?"
            " ORDER BY local_time, id",
            (trip_id, local_iso(start_local), local_iso(end_local)),
        )
        return [PhotoRow(**dict(r)) for r in rows]


class SettingsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get_all(self) -> dict[str, str]:
        return {r["key"]: r["value"] for r in self.conn.execute("SELECT key, value FROM settings")}

    def set_many(self, values: dict[str, str]) -> None:
        """Save several keys in one transaction (SE-5: all or nothing)."""
        now = utc_now_text()
        with self.conn:
            self.conn.executemany(
                "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
                " updated_at = excluded.updated_at",
                [(k, v, now) for k, v in values.items()],
            )

    def set(self, key: str, value: str) -> None:
        self.set_many({key: value})


class PlaceCacheRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get(self, lat_key: str, lon_key: str) -> str | None:
        row = self.conn.execute(
            "SELECT name FROM place_cache WHERE lat_key = ? AND lon_key = ?", (lat_key, lon_key)
        ).fetchone()
        return str(row["name"]) if row else None

    def put(self, lat_key: str, lon_key: str, name: str) -> None:
        self.conn.execute(
            "INSERT INTO place_cache (lat_key, lon_key, name, fetched_at) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(lat_key, lon_key) DO UPDATE SET name = excluded.name,"
            " fetched_at = excluded.fetched_at",
            (lat_key, lon_key, name, utc_now_text()),
        )
        self.conn.commit()


@dataclass(frozen=True)
class Repositories:
    """All repositories over one connection; passed to tools through ToolContext."""

    trips: TripRepository
    stops: StopRepository
    notes: NoteRepository
    photos: PhotoRepository
    settings: SettingsRepository
    place_cache: PlaceCacheRepository

    @classmethod
    def from_connection(cls, conn: sqlite3.Connection) -> Repositories:
        return cls(
            trips=TripRepository(conn),
            stops=StopRepository(conn),
            notes=NoteRepository(conn),
            photos=PhotoRepository(conn),
            settings=SettingsRepository(conn),
            place_cache=PlaceCacheRepository(conn),
        )
