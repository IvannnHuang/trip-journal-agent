# ADDED [PROMPT #25]: U3 JSON API tests (plan steps 13 and 18; FD T-O9 at the API).
# AI-assisted, Claude Opus 5.5. FakeLLMClient only, never real Ollama.
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.fixtures.organizer import (
    NEXT_DAY,
    SAMPLE_DAY,
    SAMPLE_DAY_LABELS,
    LabellingLLM,
    import_sample_trip,
    make_app_client,
    organizer_item,
    organizer_reply,
    two_day_trip_bytes,
    wait_job,
)
from trip_journal.agent.llm import FakeLLMClient, LLMReply, ModelStatus

DAY = SAMPLE_DAY


def organize_day(client: TestClient, trip_id: int) -> dict[str, Any]:
    started = client.post(f"/api/trips/{trip_id}/organize", json={"day": DAY})
    assert started.status_code == 202, started.text
    assert started.json()["kind"] == "organize" and started.json()["batches"] == 1
    job = wait_job(client, started.json()["job_id"])
    assert job["state"] == "done", job
    return job


def suggestions(client: TestClient, trip_id: int, day: str = DAY) -> list[dict[str, Any]]:
    listed = client.get(f"/api/trips/{trip_id}/days/{day}/suggestions")
    assert listed.status_code == 200
    rows: list[dict[str, Any]] = listed.json()
    return rows


@pytest.fixture
def api(organizer_client: TestClient) -> TestClient:
    return organizer_client


def test_organize_then_review_actions(api: TestClient) -> None:
    trip_id = import_sample_trip(api)
    job = organize_day(api, trip_id)
    assert job["result"]["total_suggested"] == 8
    rows = suggestions(api, trip_id)
    assert len(rows) == 8 and {r["status"] for r in rows} == {"pending"}
    sid = rows[0]["suggestion_id"]

    assert api.post(f"/api/suggestions/{sid}/accept").json()["status"] == "accepted"
    again = api.post(f"/api/suggestions/{sid}/accept")
    assert again.status_code == 409 and again.json()["code"] == "suggestion_state"
    assert api.post(f"/api/suggestions/{sid}/undo").json()["status"] == "pending"
    assert api.post(f"/api/suggestions/{sid}/reject").json()["status"] == "rejected"
    assert api.post(f"/api/suggestions/{sid}/undo").json()["status"] == "pending"

    bad = api.put(f"/api/suggestions/{sid}", json={"category": "lunch", "rating": 9})
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_edit"
    assert set(bad.json()["fields"]) == {"category", "rating"}
    good = api.put(f"/api/suggestions/{sid}", json={"category": "scene", "tip": "Go early."})
    assert good.status_code == 200
    assert good.json()["status"] == "edited" and good.json()["category"] == "scene"

    accepted = api.post(f"/api/trips/{trip_id}/days/{DAY}/suggestions/accept-all")
    assert accepted.status_code == 200 and accepted.json() == {"accepted": 7}

    # every note now has a decision -> no job (OR-RUN5)
    nothing = api.post(f"/api/trips/{trip_id}/organize", json={"day": DAY})
    assert nothing.status_code == 200
    assert nothing.json()["job_id"] is None and nothing.json()["message"]


def test_not_found_and_bad_dates(api: TestClient) -> None:
    trip_id = import_sample_trip(api)
    assert api.post("/api/trips/999/organize", json={}).json()["code"] == "trip_not_found"
    missing_day = api.post(f"/api/trips/{trip_id}/organize", json={"day": "2026-05-03"})
    assert missing_day.status_code == 404 and missing_day.json()["code"] == "day_not_found"
    bad = api.post(f"/api/trips/{trip_id}/organize", json={"day": "2026-5-2"})
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_date"
    for path in ("suggestions", "suggestions/accept-all"):
        method = api.get if path == "suggestions" else api.post
        assert method(f"/api/trips/{trip_id}/days/yesterday/{path}").status_code == 422
    unknown = api.post("/api/suggestions/999/accept")
    assert unknown.status_code == 404 and unknown.json()["code"] == "suggestion_not_found"
    assert api.put("/api/suggestions/999", json={"category": "food"}).status_code == 404


def test_model_not_ready_is_503(http: httpx.AsyncClient) -> None:
    down = ModelStatus(
        reachable=False, model_installed=False, model_name="fake", base_url="http://localhost/v1"
    )
    llm = FakeLLMClient([], status_value=down)
    for client in make_app_client(http, llm):
        trip_id = import_sample_trip(client)
        reply_ = client.post(f"/api/trips/{trip_id}/organize")
        assert reply_.status_code == 503 and reply_.json()["code"] == "ollama_unreachable"
        assert llm.calls == []


def test_second_run_while_one_runs_is_429_model_busy(http: httpx.AsyncClient) -> None:
    # plan D-5: busy stays 429 model_busy, and it is checked before the model probe
    llm = FakeLLMClient([organizer_reply(*SAMPLE_DAY_LABELS)], delay_s=0.5)
    for client in make_app_client(http, llm):
        trip_id = import_sample_trip(client)
        first = client.post(f"/api/trips/{trip_id}/organize", json={"day": DAY})
        assert first.status_code == 202
        busy = client.post(f"/api/trips/{trip_id}/organize", json={"day": DAY})
        assert busy.status_code == 429 and busy.json()["code"] == "model_busy"
        assert wait_job(client, first.json()["job_id"])["state"] == "done"
        assert len(llm.calls) == 1  # the refused run sent nothing


def test_whole_trip_run_covers_every_day(http: httpx.AsyncClient) -> None:
    llm = LabellingLLM(category="scene")
    for client in make_app_client(http, llm):
        trip = client.post("/api/trips", files={"file": ("t.json", two_day_trip_bytes())})
        trip_id = trip.json()["trip_id"]
        started = client.post(f"/api/trips/{trip_id}/organize")  # no body: the whole trip
        assert started.status_code == 202 and started.json()["batches"] == 2
        result = wait_job(client, started.json()["job_id"])["result"]
        assert [d["day"] for d in result["days"]] == [DAY, NEXT_DAY]
        assert result["scope_day"] is None and result["total_suggested"] == 8
        assert len(suggestions(client, trip_id, DAY)) == 6
        assert {r["category"] for r in suggestions(client, trip_id, NEXT_DAY)} == {"scene"}


def test_stop_link_and_edit_stop_rules(http: httpx.AsyncClient) -> None:
    # Note n6 has no stop in the file. Labels follow time order (11:45 is the 4th note), so the
    # model sees it as "n4" and links it to "s3". An edit may only pick a stop of the day (OR-S1).
    items = [organizer_item(label) for label in SAMPLE_DAY_LABELS]
    items[3] = organizer_item("n4", stop="s3", dish="Bifana", rating=4.0, tip="  ")
    llm = FakeLLMClient([LLMReply(content=json.dumps({"suggestions": items}))])
    for client in make_app_client(http, llm):
        trip_id = import_sample_trip(client)
        organize_day(client, trip_id)
        rows = {r["note_source_id"]: r for r in suggestions(client, trip_id)}
        n6 = rows["n6"]
        assert n6["stop_source_id"] == "s3" and n6["stop_label"] == "Museu Nacional do Azulejo"
        assert (n6["dish"], n6["rating"], n6["tip"]) == ("Bifana", 4, None)

        day = client.get(f"/api/trips/{trip_id}/days/{DAY}").json()
        stop_ids = [s["stop_id"] for s in day["stops"]]
        sid = n6["suggestion_id"]
        wrong = client.put(f"/api/suggestions/{sid}", json={"category": "food", "stop_id": 999})
        assert wrong.status_code == 422 and set(wrong.json()["fields"]) == {"stop_id"}
        unknown_key = client.put(f"/api/suggestions/{sid}", json={"category": "food", "x": 1})
        assert unknown_key.status_code == 422
        moved = client.put(
            f"/api/suggestions/{sid}", json={"category": "food", "stop_id": stop_ids[0]}
        )
        assert moved.status_code == 200 and moved.json()["stop_id"] == stop_ids[0]
        # the model's values stay on the row for the "edited" comparison
        assert moved.json()["model_values"]["dish"] == "Bifana"


def test_organize_job_view_is_registered(api: TestClient) -> None:
    app: Any = api.app
    view = app.state.trip.job_views["organize"]
    assert view.result_template == "organizer/summary.html"
