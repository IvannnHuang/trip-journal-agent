# ADDED [PROMPT #36]: service precedence, grounding, diagnostics, JSON and htmx contracts.
import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import Seed
from trip_journal.agent.llm import FakeLLMClient, LLMReply, ModelStatus, ToolCall
from trip_journal.api.deps import AppState
from trip_journal.domain.views import NothingToRegenerate
from trip_journal.services.errors import (
    ModelBusyError,
    ModelUnavailableError,
    NoRecordsError,
    NotFoundError,
)
from trip_journal.services.jobs import JobRef
from trip_journal.services.journal import JournalService

DAY = "2026-06-01"


async def test_job_and_edit(
    journal_service: JournalService, seed: Seed, caplog: pytest.LogCaptureFixture
) -> None:
    service = journal_service
    trip = seed.trip_id
    other_note = seed.notes[-1]
    text = f"Private journal <b> [note:{other_note}]."
    llm = FakeLLMClient(
        [
            LLMReply(
                content=None, tool_calls=[ToolCall(id="bad", name="unknown", arguments_json="{}")]
            ),
            LLMReply(content="## summary\n" + text),
        ]
    )
    service.llm_factory = lambda _: llm
    caplog.set_level(logging.INFO)
    job = await service.start_generation(trip, DAY, "casual")
    assert isinstance(job, JobRef)
    done = await service.jobs.wait(job.job_id)
    assert done.result and "did not write 2 paragraphs" in done.result["message"]
    assert "1 tool call failed" in done.result["message"]
    assert done.trace[-1].error and done.trace[-1].group == "part 1"
    journal = service.get_journal(trip, DAY)
    assert journal.unsupported_count == 1
    assert service.trips.get_day(trip, DAY).journal_exists
    assert journal.paragraphs[1].state == "not_written"
    assert "&lt;b&gt;" in journal.paragraphs[0].sentences[0].text_html
    edited = service.edit_paragraph(trip, DAY, "summary", text + " ")
    assert edited.unsupported_count == 0 and edited.paragraph.owner == "user"
    assert service.edit_paragraph(trip, DAY, "summary", "").paragraph.state == "removed"
    assert all(
        name in caplog.text
        for name in ["journal.start", "journal.chunk", "journal.end", "journal.edit"]
    )
    assert "Private journal" not in caplog.text and "Swam in the lake" not in caplog.text
    assert service.get_citation(trip, "stop", seed.stops[0]).title == "Lake Bled"
    assert (
        service.get_citation(trip, "note", seed.notes[0]).body == "Swam in the lake, water was cold"
    )
    assert service.get_citation(trip, "photo", seed.photos[0]).title == "IMG_1.jpg"
    assert not service.get_citation(seed.other_trip_id, "note", seed.notes[0]).found


async def test_precheck_order(journal_service: JournalService, seed: Seed) -> None:
    service = journal_service
    trip = seed.trip_id
    down = FakeLLMClient(
        [],
        status_value=ModelStatus(
            reachable=False, model_installed=False, model_name="fake", base_url="local"
        ),
    )
    service.llm_factory = lambda _: down
    with pytest.raises(NotFoundError):
        await service.start_generation(trip, "1900-01-01", "casual")
    service.repos.photos.add(trip, "only-photo", "2026-07-15T08:00:00Z", 0)
    with pytest.raises(NoRecordsError):
        await service.start_generation(trip, "2026-07-15", "casual")
    with pytest.raises(ModelUnavailableError):
        await service.start_generation(trip, DAY, "casual")
    day = "2026-06-02"
    service.repos.journals.save_generated(trip, day, ["summary"], {}, "casual", [], "v", "m")
    service.edit_paragraph(trip, day, "summary", "mine")
    assert isinstance(await service.start_generation(trip, day, "casual"), NothingToRegenerate)


async def test_limit_and_busy(journal_service: JournalService, journal_trip: int) -> None:
    service = journal_service
    llm = FakeLLMClient([LLMReply(content="missing")] * 3 + [LLMReply(content="## summary\nDraft")])
    service.llm_factory = lambda _: llm
    # ADDED [PROMPT #36]: a PUT-equivalent edit during the running job wins at commit.
    day = "2026-06-02"
    slots = [
        "summary",
        *(f"stop:{s.id}" for s in service.repos.stops.list_for_day(journal_trip, day)),
    ]
    service.repos.journals.save_generated(journal_trip, day, slots, {}, "casual", [], "v", "fake")
    with patch.object(service.jobs, "start", wraps=service.jobs.start) as start:
        job = await service.start_generation(journal_trip, "2026-06-02", "concise")
        assert start.call_args.kwargs["timeout_s"] == 1200
        assert isinstance(job, JobRef)
        with pytest.raises(ModelBusyError):
            await service.start_generation(journal_trip, DAY, "casual")
        service.edit_paragraph(journal_trip, day, "summary", "Written while generating")
        completed = await service.jobs.wait(job.job_id)
        assert completed.state == "done"
        summary = service.get_journal(journal_trip, day).paragraphs[0]
        assert summary.text == "Written while generating" and summary.owner == "user"


def test_journal_routes(organizer_client: TestClient) -> None:
    client = organizer_client
    state: AppState = client.app.state.trip  # type: ignore[attr-defined]
    trip = state.repos.trips.add("api", "Test")
    state.repos.notes.add(trip, "n", "Note", "2026-06-01T12:00:00Z", 0)
    state.journal.llm_factory = lambda _: FakeLLMClient([LLMReply(content="## summary\nFirst")])
    url = f"/api/trips/{trip}/days/{DAY}/journal"
    hx = {"HX-Request": "true"}
    assert client.get(url).json()["tone"] is None
    assert client.put(url + "/paragraphs/summary", json={"text": "x"}).status_code == 404
    response = client.post(url, json={"tone": "casual"})
    assert response.status_code == 202 and response.json()["kind"] == "journal"
    assert client.portal
    assert client.portal.call(state.jobs.wait, response.json()["job_id"]).state == "done"
    # ADDED [PROMPT #36]: finished htmx jobs can render the C1 result fragment.
    fragment = client.get(f"/jobs/{response.json()['job_id']}/fragment")
    assert fragment.status_code == 200 and "Draft ready" in fragment.text
    assert client.get(url).json()["paragraphs"][0]["text"] == "First"
    assert client.get(url, headers=hx).text.find("First") >= 0
    assert client.put(url + "/paragraphs/junk", json={"text": "x"}).status_code == 404
    assert (
        client.put(url + "/paragraphs/summary", json={"text": "x" * 5001}).json()["code"]
        == "invalid_edit"
    )
    assert (
        client.put(url + "/paragraphs/summary", json={"text": "My edit"}).json()["paragraph"][
            "owner"
        ]
        == "user"
    )
    assert client.post(url, json={"tone": "casual"}).json()["nothing_to_regenerate"]
    assert (
        "Saved"
        in client.put(url + "/paragraphs/summary", headers=hx, data={"text": "Updated"}).text
    )
    assert "Nothing to regenerate" in client.post(url, headers=hx, data={"tone": "casual"}).text
    for body in ({"tone": "loud"}, {"tone": "casual", "extra": True}):
        assert client.post(url, json=body).status_code == 422
    assert client.post(url, headers=hx, data={"tone": "invalid"}).status_code == 422
    for headers in ({}, hx):
        assert client.get(url.replace(DAY, "invalid"), headers=headers).status_code == 422
