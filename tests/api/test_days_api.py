# ADDED [PROMPT #17]: day JSON API (TL-1, TL-2). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.fixtures import minimal_trip_bytes


@pytest.fixture
def trip_id(client: TestClient) -> int:
    reply = client.post("/api/trips", files={"file": ("t.json", minimal_trip_bytes())})
    value: int = reply.json()["trip_id"]
    return value


def test_day_view(client: TestClient, trip_id: int) -> None:
    reply = client.get(f"/api/trips/{trip_id}/days/2026-05-02")
    assert reply.status_code == 200
    body = reply.json()
    assert body["heading"] == "Day 1 - Sat 2 May 2026"
    assert [s["start_local"] for s in body["stops"]] == ["09:15", "10:40", "14:00", "23:10"]
    assert [p["file_name"] for p in body["other_photos"]] == ["IMG_0006.jpg"]
    assert len(body["unlinked_notes"]) == 1


@pytest.mark.parametrize("day", ["2026-5-2", "2026-02-30", "yesterday", "20260502"])
def test_bad_date_is_422(client: TestClient, trip_id: int, day: str) -> None:
    reply = client.get(f"/api/trips/{trip_id}/days/{day}")
    assert reply.status_code == 422 and reply.json()["code"] == "invalid_date"


def test_unknown_day_and_trip_are_404(client: TestClient, trip_id: int) -> None:
    day = client.get(f"/api/trips/{trip_id}/days/2026-05-03")
    assert day.status_code == 404 and day.json()["code"] == "day_not_found"
    trip = client.get("/api/trips/999/days/2026-05-02")
    assert trip.status_code == 404 and trip.json()["code"] == "trip_not_found"
