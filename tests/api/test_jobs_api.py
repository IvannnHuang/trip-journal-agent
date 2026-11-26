# ADDED [PROMPT #13]: job status API and fragment tests (JB-7, ST-6). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import httpx
from fastapi.testclient import TestClient
from pydantic import BaseModel

from trip_journal.agent.loop import ToolCallRecord
from trip_journal.main import create_app
from trip_journal.services.errors import ModelCallError
from trip_journal.services.jobs import JobProgress


class Out(BaseModel):
    text: str


def test_unknown_job_is_404_json(client: TestClient) -> None:
    reply = client.get("/api/jobs/nope")
    assert reply.status_code == 404 and reply.json()["code"] == "job_not_found"


def test_unknown_job_fragment_shows_error(client: TestClient) -> None:
    reply = client.get("/jobs/nope/fragment")
    assert 'data-testid="job-error"' in reply.text and 'data-code="job_not_found"' in reply.text


async def test_finished_jobs_via_api_and_fragment(http: httpx.AsyncClient) -> None:
    app = create_app(":memory:", http=http, env={})
    runner = app.state.trip.jobs

    async def ok(progress: JobProgress) -> Out:
        return Out(text="hello")

    async def bad(progress: JobProgress) -> Out:
        progress.tool_call(ToolCallRecord(step=1, name="search_notes", arguments={"query": "x"}))
        raise ModelCallError("timeout")

    done = runner.start("demo", ok).job_id
    await runner.wait(done)
    failed = runner.start("demo", bad).job_id
    await runner.wait(failed)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as web:
        body = (await web.get(f"/api/jobs/{done}")).json()
        assert body["state"] == "done" and body["result"] == {"text": "hello"}
        html = (await web.get(f"/jobs/{failed}/fragment")).text
        assert 'data-state="failed"' in html and 'data-testid="trace-row"' in html
        assert "search_notes" in html
