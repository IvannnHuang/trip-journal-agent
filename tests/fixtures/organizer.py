# ADDED [PROMPT #25]: U3 organizer test helpers (plan step 16). AI-assisted, Claude Opus 5.5.
"""Scripted organizer replies, a FakeLLMClient that answers every batch, and app-client helpers.

FakeLLMClient only: no test reaches a real Ollama.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
from fastapi.testclient import TestClient

from tests.fixtures import minimal_trip_bytes
from trip_journal.agent.llm import FakeLLMClient, LLMReply
from trip_journal.main import create_app

SAMPLE_DAY = "2026-05-02"  # the sample trip day with 8 notes (one batch) and 4 stops
SAMPLE_DAY_LABELS = [f"n{i}" for i in range(1, 9)]
NEXT_DAY = "2026-05-03"  # the second day of `two_day_trip_bytes()`
_NOTE_LABEL = re.compile(r'<note id="(n\d+)">')


def organizer_item(label: str, **fields: Any) -> dict[str, Any]:
    """One reply item; every field defaults to none, category to food."""
    item: dict[str, Any] = {
        "note": label,
        "category": "food",
        "stop": None,
        "dish": None,
        "rating": None,
        "tip": None,
    }
    item.update(fields)
    return item


def organizer_reply(*labels: str, **fields: Any) -> LLMReply:
    """A valid reply with one item per label, all with the same fields."""
    items = [organizer_item(label, **fields) for label in labels]
    return LLMReply(content=json.dumps({"suggestions": items}))


class LabellingLLM(FakeLLMClient):
    """Answers every batch with one valid item per note label found in the user message.

    Records calls like FakeLLMClient, so multi-batch and whole-trip runs need no script.
    """

    def __init__(self, category: str = "food", **kwargs: Any) -> None:
        super().__init__([], **kwargs)
        self.category = category

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        reasoning_effort: str | None = None,
        timeout_s: float | None = None,
    ) -> LLMReply:
        labels = _NOTE_LABEL.findall(str(messages[-1]["content"]))
        self._script.append(organizer_reply(*labels, category=self.category))
        return await super().chat(messages, tools, response_format, reasoning_effort, timeout_s)


def make_app_client(http: httpx.AsyncClient, llm: FakeLLMClient) -> Iterator[TestClient]:
    """The full app on an in-memory database; every organize run uses `llm` (plan D-1)."""
    app = create_app(":memory:", http=http, env={}, llm_factory=lambda _s: llm)
    with TestClient(app) as c:
        yield c


def import_sample_trip(client: TestClient) -> int:
    """Import `sample_data/minimal_trip.json` through the API; returns the trip id."""
    reply = client.post("/api/trips", files={"file": ("t.json", minimal_trip_bytes())})
    assert reply.status_code == 201, reply.text
    value: int = reply.json()["trip_id"]
    return value


def wait_job(client: TestClient, job_id: str, limit_s: float = 10.0) -> dict[str, Any]:
    """Poll `/api/jobs/{id}` until the job leaves `running`."""
    deadline = time.monotonic() + limit_s
    while time.monotonic() < deadline:
        body: dict[str, Any] = client.get(f"/api/jobs/{job_id}").json()
        if body["state"] != "running":
            return body
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def two_day_trip_bytes() -> bytes:
    """The sample trip with its late-dinner stop s4 (notes n7, n8; photos p9, p10) a day later.

    Day 2026-05-02 keeps s1-s3 and n1-n6; day 2026-05-03 has s4 with n7, n8.
    """
    data = json.loads(minimal_trip_bytes())
    data["trip"]["trip_id"] = "two-days"

    def later(value: str) -> str:
        return value.replace("2026-05-03", "2026-05-04").replace("2026-05-02T2", "2026-05-03T2")

    for key in ("stops", "notes", "photos"):
        for row in data[key]:
            for name in ("start_utc", "end_utc", "time_utc"):
                if name in row:
                    row[name] = later(row[name])
    return json.dumps(data).encode()


# ADDED [PROMPT #25]: an app client usable inside Hypothesis examples (plan steps 19-20).
@contextmanager
def review_client(llm: FakeLLMClient) -> Iterator[TestClient]:
    """`make_app_client` without pytest fixtures: a fresh app per Hypothesis example.

    The HTTP client answers 404 to everything; the organizer only talks to `llm`.
    """
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(404)))
    yield from make_app_client(http, llm)


def run_organizer(client: TestClient, trip_id: int, day: str | None = None) -> None:
    """Start an organize run (one day or the whole trip) and wait for it, if one starts."""
    body = {"day": day} if day else {}
    reply = client.post(f"/api/trips/{trip_id}/organize", json=body)
    assert reply.status_code in (200, 202), reply.text
    job_id = reply.json()["job_id"]
    if job_id is not None:
        assert wait_job(client, job_id)["state"] == "done"


def import_two_day_trip(client: TestClient) -> int:
    reply = client.post("/api/trips", files={"file": ("t.json", two_day_trip_bytes())})
    assert reply.status_code == 201, reply.text
    value: int = reply.json()["trip_id"]
    return value
