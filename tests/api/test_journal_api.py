# ADDED [PROMPT #36]: journal JSON / htmx validation and concurrent edits.
import asyncio
import re
from typing import Any

from fastapi.testclient import TestClient

from tests.fixtures.organizer import wait_job
from trip_journal.agent.llm import FakeLLMClient, LLMReply, ModelStatus
from trip_journal.api.deps import AppState

DAY = "2026-06-01"
HX = {"HX-Request": "true"}


def test_running_job_allows_edit(organizer_client: TestClient) -> None:
    client = organizer_client
    state: AppState = client.app.state.trip  # type: ignore[attr-defined]
    trip = state.repos.trips.add("running", "Trip")
    state.repos.notes.add(trip, "n", "Record", DAY + "T12:00:00Z", 0)
    state.repos.journals.save_generated(
        trip, DAY, ["summary"], {"summary": "Existing"}, "casual", [], "v", "fake"
    )
    url = f"/api/trips/{trip}/days/{DAY}/journal"
    release = asyncio.Event()

    class PausedModel(FakeLLMClient):
        async def chat(self, *args: Any, **kwargs: Any) -> LLMReply:
            await release.wait()
            return await super().chat(*args, **kwargs)

    state.journal.llm_factory = lambda _: PausedModel([LLMReply(content="## summary\nReplacement")])
    started = client.post(url, headers=HX, data={"tone": "concise"})
    assert started.status_code == 202 and 'hx-trigger="every 1s"' in started.text
    poll = re.search(r"/jobs/([\w-]+)/fragment", started.text)
    assert poll
    assert client.post(url, json={"tone": "casual"}).status_code == 429
    busy = client.post(url, headers=HX, data={"tone": "casual"})
    assert (
        busy.status_code == 429
        and "Another job is running. Try again when it finishes." in busy.text
    )
    assert client.get(f"/api/jobs/{poll[1]}").json()["state"] == "running"
    edited = client.put(url + "/paragraphs/summary", json={"text": "While running"})
    assert edited.status_code == 200 and edited.json()["unsupported_count"] == 1
    assert client.portal
    client.portal.call(release.set)
    assert wait_job(client, poll[1])["state"] == "done"
    assert client.get(url).json()["paragraphs"][0]["text"] == "While running"
    assert "While running" in client.get(url, headers=HX).text
    nothing = client.post(url, json={"tone": "casual"})
    assert nothing.status_code == 200 and nothing.json()["nothing_to_regenerate"]
    assert "Nothing to regenerate" in client.post(url, headers=HX, data={"tone": "casual"}).text


def test_api_errors(organizer_client: TestClient) -> None:
    client = organizer_client
    state: AppState = client.app.state.trip  # type: ignore[attr-defined]
    trip = state.repos.trips.add("errors", "Trip")
    url = f"/api/trips/{trip}/days/{DAY}/journal"
    options = {"tone": "casual"}
    assert client.get(url).status_code == client.post(url, json=options).status_code == 404
    state.repos.photos.add(trip, "only", DAY + "T08:00:00Z", 0)
    none = client.post(url, json=options)
    assert none.status_code == 422 and none.json()["code"] == "no_records"
    state.repos.notes.add(trip, "note", "Text", DAY + "T09:00:00Z", 0)
    down = ModelStatus(reachable=False, model_installed=False, model_name="fake", base_url="local")
    state.journal.llm_factory = lambda _: FakeLLMClient([], status_value=down)
    assert client.post(url, headers=HX, data=options).status_code == 503
    assert client.post(url, json={"tone": "other"}).status_code == 422
    assert client.post(url, json={**options, "extra": 1}).status_code == 422
    state.repos.journals.save_generated(trip, DAY, ["summary"], {}, "casual", [], "v", "fake")
    assert client.put(url + "/paragraphs/bogus", json={"text": "x"}).status_code == 404
    edit = url + "/paragraphs/summary"
    too_long = {"text": "x" * 5001}
    for response in (
        client.put(edit, json=too_long),
        client.put(edit, headers=HX, data=too_long),
    ):
        assert response.status_code == 422 and "Paragraph is too long" in response.text
    assert client.get(url).json()["paragraphs"][0]["text"] == ""
