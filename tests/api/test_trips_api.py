# ADDED [PROMPT #17]: trips JSON API (frontend-components 2.6). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from tests.fixtures import MINIMAL_SOURCE_ID, minimal_trip_bytes
from trip_journal.services.jobs import JobRunner


def import_sample(client: TestClient) -> int:
    reply = client.post("/api/trips", files={"file": ("t.json", minimal_trip_bytes())})
    assert reply.status_code == 201
    trip_id: int = reply.json()["trip_id"]
    return trip_id


def test_import_list_and_get(client: TestClient) -> None:
    assert client.get("/api/trips").json() == []
    trip_id = import_sample(client)
    listed = client.get("/api/trips").json()
    assert [t["source_id"] for t in listed] == [MINIMAL_SOURCE_ID]
    assert listed[0]["is_active"] is True
    one = client.get(f"/api/trips/{trip_id}").json()
    assert (one["stop_count"], one["note_count"], one["photo_count"]) == (4, 8, 10)
    assert [d["local_date"] for d in one["days"]] == ["2026-05-02"]


def test_import_invalid_returns_issues(client: TestClient) -> None:
    data = json.loads(minimal_trip_bytes())
    data["stops"][0]["lat"] = 200
    reply = client.post("/api/trips", files={"file": ("t.json", json.dumps(data).encode())})
    assert reply.status_code == 422
    body = reply.json()
    assert body["code"] == "import_invalid"
    assert body["issues"] == [{"location": "stops[0].lat", "message": "must be between -90 and 90"}]
    assert body["more"] == 0
    assert {"message", "action", "trace"} <= set(body)
    assert client.get("/api/trips").json() == []


def test_import_not_json_and_too_large(client: TestClient) -> None:
    reply = client.post("/api/trips", files={"file": ("t.gpx", b"<?xml version='1.0'?><gpx/>")})
    assert reply.status_code == 422 and reply.json()["issues"][0]["location"] == "file"
    big = b" " * (20 * 1024 * 1024 + 10)
    reply = client.post("/api/trips", files={"file": ("big.json", big)})
    assert reply.status_code == 422
    assert reply.json()["issues"][0]["message"] == "The file is larger than 20 MB."


def test_import_duplicate_is_409(client: TestClient) -> None:
    import_sample(client)
    reply = client.post("/api/trips", files={"file": ("t.json", minimal_trip_bytes())})
    assert reply.status_code == 409 and reply.json()["code"] == "trip_exists"


def test_import_without_file_is_422(client: TestClient) -> None:
    assert client.post("/api/trips").status_code == 422


def test_get_unknown_trip_is_404(client: TestClient) -> None:
    reply = client.get("/api/trips/999")
    assert reply.status_code == 404 and reply.json()["code"] == "trip_not_found"


def test_delete(client: TestClient) -> None:
    trip_id = import_sample(client)
    assert client.delete(f"/api/trips/{trip_id}").status_code == 204
    assert client.get(f"/api/trips/{trip_id}").status_code == 404
    reply = client.delete(f"/api/trips/{trip_id}")
    assert reply.status_code == 404 and reply.json()["code"] == "trip_not_found"


def test_delete_refused_while_job_runs(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    trip_id = import_sample(client)
    monkeypatch.setattr(JobRunner, "running", property(lambda _self: object()))
    reply = client.delete(f"/api/trips/{trip_id}")
    assert reply.status_code == 409 and reply.json()["code"] == "job_running"
    monkeypatch.undo()
    assert client.get(f"/api/trips/{trip_id}").status_code == 200
