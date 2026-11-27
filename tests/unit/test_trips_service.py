# ADDED [PROMPT #17]: TripService (C04): active trip, summaries, day view, delete.
# AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3

import pytest
from pydantic import BaseModel

from tests.fixtures import Services, load_minimal_trip, minimal_trip_bytes
from trip_journal.services.errors import JobRunningError, NotFoundError
from trip_journal.services.jobs import JobProgress
from trip_journal.services.trips import ACTIVE_TRIP_KEY

LOGGER = "trip_journal.services.trips"


def second_trip(services: Services, source_id: str = "second") -> int:
    data = json.loads(minimal_trip_bytes())
    data["trip"]["trip_id"] = source_id
    data["trip"]["title"] = "Second"
    return services.imports.import_trip(json.dumps(data).encode()).trip_id


def test_no_trips_means_no_active_trip(services: Services) -> None:
    assert services.trips.get_active_trip_id() is None
    assert services.trips.get_active_trip() is None
    assert services.trips.list_trips() == []


def test_active_trip_follows_import_and_set(services: Services) -> None:
    first = load_minimal_trip(services).trip_id
    second = second_trip(services)
    assert services.trips.get_active_trip_id() == second
    services.trips.set_active_trip(first)
    trip = services.trips.get_active_trip()
    assert trip is not None and trip.id == first
    flags = {t.trip_id: t.is_active for t in services.trips.list_trips()}
    assert flags == {first: True, second: False}


def test_set_active_unknown_trip(services: Services) -> None:
    with pytest.raises(NotFoundError) as info:
        services.trips.set_active_trip(999)
    assert info.value.code == "trip_not_found"


def test_stale_or_bad_setting_falls_back_to_newest(services: Services) -> None:
    load_minimal_trip(services)
    newest = second_trip(services)
    for raw in ("999", "abc"):
        services.repos.settings.set(ACTIVE_TRIP_KEY, raw)
        assert services.trips.get_active_trip_id() == newest
        assert services.repos.settings.get_all()[ACTIVE_TRIP_KEY] == str(newest)


def test_summary_of_sample(services: Services) -> None:
    summary = services.trips.get_summary(load_minimal_trip(services).trip_id)
    assert summary.title == "A day in Lisbon"
    assert (summary.first_date, summary.last_date) == ("2026-05-02", "2026-05-02")
    assert [d.model_dump() for d in summary.days] == [
        {
            "local_date": "2026-05-02",
            "day_number": 1,
            "stop_count": 4,
            "note_count": 8,
            "photo_count": 10,
        }
    ]
    assert summary.route_summary is not None


def test_get_day_unknown_trip_and_day(services: Services) -> None:
    trip_id = load_minimal_trip(services).trip_id
    with pytest.raises(NotFoundError) as trip_err:
        services.trips.get_day(999, "2026-05-02")
    assert trip_err.value.code == "trip_not_found"
    with pytest.raises(NotFoundError) as day_err:
        services.trips.get_day(trip_id, "2026-05-03")
    assert day_err.value.code == "day_not_found"


def test_multi_day_navigation_and_offsets(services: Services) -> None:
    data = json.loads(minimal_trip_bytes())
    data["trip"]["trip_id"] = "multi"
    data["stops"][3]["utc_offset_minutes"] = 0  # s4 keeps its day, offset differs
    data["notes"].append(
        {
            "id": "late",
            "text": "Next morning",
            "time_utc": "2026-05-04T08:00:00Z",
            "utc_offset_minutes": 60,
        }
    )
    trip_id = services.imports.import_trip(json.dumps(data).encode()).trip_id
    first = services.trips.get_day(trip_id, "2026-05-02")
    assert first.show_offsets
    assert (first.prev_date, first.next_date, first.day_count) == (None, "2026-05-04", 2)
    last = services.trips.get_day(trip_id, "2026-05-04")
    assert (last.prev_date, last.next_date, last.day_number) == ("2026-05-02", None, 2)
    assert last.stops == []
    assert [n.text for n in last.unlinked_notes] == ["Next morning"]


def test_delete_preview_and_delete(
    services: Services, conn: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    first = load_minimal_trip(services).trip_id
    second = second_trip(services)
    preview = services.trips.get_delete_preview(second)
    assert (preview.title, preview.stop_count, preview.note_count, preview.photo_count) == (
        "Second",
        4,
        8,
        10,
    )
    caplog.set_level(logging.INFO, logger=LOGGER)
    services.trips.delete_trip(second)
    assert services.trips.get_active_trip_id() == first  # AT-4
    left = conn.execute("SELECT COUNT(*) FROM stops WHERE trip_id = ?", (second,)).fetchone()[0]
    assert left == 0
    line = caplog.records[-1].getMessage()
    assert line.startswith("trip.delete result=ok") and "Second" not in line
    with pytest.raises(NotFoundError):
        services.trips.delete_trip(second)
    with pytest.raises(NotFoundError):
        services.trips.get_delete_preview(second)


async def test_delete_refused_while_a_job_runs(
    services: Services, caplog: pytest.LogCaptureFixture
) -> None:
    trip_id = load_minimal_trip(services).trip_id
    release = asyncio.Event()

    async def work(_progress: JobProgress) -> BaseModel:
        await release.wait()
        return BaseModel()

    ref = services.jobs.start("organize", work)
    await asyncio.sleep(0)
    caplog.set_level(logging.INFO, logger=LOGGER)
    with pytest.raises(JobRunningError):
        services.trips.delete_trip(trip_id)
    assert "trip.delete result=job_running" in caplog.records[-1].getMessage()
    assert services.repos.trips.get(trip_id) is not None
    release.set()
    await services.jobs.wait(ref.job_id)
    services.trips.delete_trip(trip_id)
    assert services.repos.trips.get(trip_id) is None
