# ADDED [PROMPT #17]: ImportService (C03), incl. the T.3 transaction test. AI-assisted,
# Claude Opus 5.5.
from __future__ import annotations

import json
import logging
import sqlite3

import pytest

from tests.fixtures import (
    MINIMAL_SOURCE_ID,
    Services,
    load_minimal_trip,
    minimal_trip_bytes,
    minimal_trip_ids,
)
from trip_journal.services.errors import ImportValidationError, TripAlreadyExistsError

LOGGER = "trip_journal.services.imports"


def row_count(conn: sqlite3.Connection) -> int:
    return sum(
        conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("trips", "stops", "notes", "photos")
    )


def test_import_stores_everything_and_sets_active(
    services: Services, conn: sqlite3.Connection
) -> None:
    summary = load_minimal_trip(services)
    assert summary.source_id == MINIMAL_SOURCE_ID
    assert (summary.stop_count, summary.note_count, summary.photo_count) == (4, 8, 10)
    assert summary.is_active
    assert services.trips.get_active_trip_id() == summary.trip_id
    ids = minimal_trip_ids(conn)
    assert len(ids) == 22
    stop = services.repos.stops.get(summary.trip_id, ids["s2"])
    assert stop is not None and stop.name is None


def test_note_on_stop_takes_the_stop_day(services: Services, conn: sqlite3.Connection) -> None:
    load_minimal_trip(services)
    ids = minimal_trip_ids(conn)
    day = conn.execute("SELECT local_date FROM notes WHERE id = ?", (ids["n8"],)).fetchone()[0]
    assert day == "2026-05-02"  # local 00:50 on 3 May, but its stop starts on 2 May (DD-3)


def test_invalid_file_stores_nothing_and_logs(
    services: Services, conn: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    data = json.loads(minimal_trip_bytes())
    data["stops"][0]["lat"] = 200
    caplog.set_level(logging.INFO, logger=LOGGER)
    with pytest.raises(ImportValidationError) as info:
        services.imports.import_trip(json.dumps(data).encode())
    assert info.value.issues[0].location == "stops[0].lat"
    assert row_count(conn) == 0
    (line,) = [r.getMessage() for r in caplog.records if r.name == LOGGER]
    assert line.startswith("trip.import result=invalid trip_id=- ")
    assert "issues=1" in line


def test_file_error_result(services: Services, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    with pytest.raises(ImportValidationError):
        services.imports.import_trip(b"")
    assert "result=file_error" in caplog.records[-1].getMessage()


def test_duplicate_is_refused(services: Services, caplog: pytest.LogCaptureFixture) -> None:
    load_minimal_trip(services)
    caplog.set_level(logging.INFO, logger=LOGGER)
    with pytest.raises(TripAlreadyExistsError) as info:
        load_minimal_trip(services)
    assert info.value.source_id == MINIMAL_SOURCE_ID
    assert "result=exists" in caplog.records[-1].getMessage()
    assert len(services.repos.trips.list()) == 1


def test_race_integrity_error_becomes_trip_exists(
    services: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    load_minimal_trip(services)
    monkeypatch.setattr(services.repos.trips, "get_by_source_id", lambda _sid: None)
    with pytest.raises(TripAlreadyExistsError):
        load_minimal_trip(services)


def test_t3_photo_insert_failure_rolls_back_everything(
    services: Services, conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """U2-NFR-T.3: a failure after trip, stops and notes were written leaves 0 rows."""
    calls = 0
    real_add = services.repos.photos.add

    def failing_add(*args: object, **kwargs: object) -> int:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise sqlite3.OperationalError("disk I/O error (injected)")
        return real_add(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(services.repos.photos, "add", failing_add)
    with pytest.raises(sqlite3.OperationalError):
        load_minimal_trip(services)
    assert calls == 3
    assert row_count(conn) == 0
    assert not conn.in_transaction
    monkeypatch.undo()
    summary = load_minimal_trip(services)  # the 409 check does not see a ghost trip
    assert summary.photo_count == 10


def test_other_integrity_error_is_not_swallowed(
    services: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_a: object, **_k: object) -> int:
        raise sqlite3.IntegrityError("FOREIGN KEY constraint failed")

    monkeypatch.setattr(services.repos.notes, "add", boom)
    with pytest.raises(sqlite3.IntegrityError):
        load_minimal_trip(services)


def test_open_implicit_transaction_is_committed_first(
    services: Services, conn: sqlite3.Connection
) -> None:
    conn.execute("INSERT INTO settings (key, value, updated_at) VALUES ('k', 'v', 'now')")
    assert conn.in_transaction
    load_minimal_trip(services)
    assert services.repos.settings.get_all()["k"] == "v"


def test_log_line_never_holds_content(services: Services, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    load_minimal_trip(services)
    line = caplog.records[-1].getMessage()
    assert line.startswith(f"trip.import result=ok trip_id={MINIMAL_SOURCE_ID} stops=4 notes=8")
    for secret in ("Lisbon", "Pastel", "38.71", "-9.14", "IMG_0001"):
        assert secret not in line
