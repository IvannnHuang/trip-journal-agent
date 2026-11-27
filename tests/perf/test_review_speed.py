# ADDED [PROMPT #25]: review action speed U3-NFR-P.5 (plan step 20). Slow: run with `-m slow`.
# AI-assisted, Claude Opus 5.5.
"""Each review action, with its re-rendered stop region, on the busiest day of the reference
large trip (U2-NFR-S.2): target <= 300 ms server time. Timings are printed (`-s`).

FakeLLMClient only (LabellingLLM): the run is set-up; review actions never call the model.
"""

from __future__ import annotations

import importlib.util
import time
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Protocol

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.organizer import LabellingLLM, review_client, run_organizer

pytestmark = pytest.mark.slow
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "make_reference_trip.py"
HX = {"HX-Request": "true"}
TARGET_S = 0.3


class Reply(Protocol):  # TestClient's response type (httpx or httpx2, by Starlette version)
    @property
    def status_code(self) -> int: ...
    @property
    def text(self) -> str: ...


def _generator() -> ModuleType:  # same loader as test_import_speed (D-38: no cross imports)
    spec = importlib.util.spec_from_file_location("make_reference_trip", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _timed(name: str, call: Callable[[], Reply]) -> float:
    begin = time.perf_counter()
    reply = call()
    elapsed = time.perf_counter() - begin
    assert reply.status_code == 200, reply.text[:300]
    assert 'id="day-stops"' in reply.text  # the stop region is re-rendered
    verdict = "ok" if elapsed <= TARGET_S else "MISS"
    print(f"\nP.5 {name}: {elapsed * 1000:.0f} ms (target {TARGET_S * 1000:.0f} ms) {verdict}")
    return elapsed


def test_p5_review_actions_on_reference_day() -> None:
    llm = LabellingLLM()
    with review_client(llm) as client:
        gen = _generator()
        reply = client.post("/api/trips", files={"file": ("t.json", gen.encode(gen.build_trip()))})
        assert reply.status_code == 201
        trip_id: int = reply.json()["trip_id"]
        days = client.get(f"/api/trips/{trip_id}").json()["days"]
        day = max(days, key=lambda d: d["stop_count"] + d["note_count"])["local_date"]
        run_organizer(client, trip_id, day)
        sids = [r["suggestion_id"] for r in _rows(client, trip_id, day)]
        assert len(sids) >= 5
        print(f"\nreference day {day}: {len(sids)} suggestions, {len(llm.calls)} batches")
        a, b, c, d = sids[:4]
        timings = [
            _timed("accept", lambda: client.post(f"/suggestions/{a}/accept", headers=HX)),
            _timed("reject", lambda: client.post(f"/suggestions/{b}/reject", headers=HX)),
            _timed(
                "edit and accept",
                lambda: client.post(
                    f"/suggestions/{c}/edit", data={"category": "scene", "tip": "Go"}, headers=HX
                ),
            ),
            _timed("undo", lambda: client.post(f"/suggestions/{a}/undo", headers=HX)),
            _timed(
                "accept all",
                lambda: client.post(f"/trips/{trip_id}/days/{day}/accept-all", headers=HX),
            ),
        ]
        statuses = {r["suggestion_id"]: r["status"] for r in _rows(client, trip_id, day)}
        assert (statuses[b], statuses[c], statuses[d]) == ("rejected", "edited", "accepted")
        assert max(timings) <= TARGET_S


def _rows(client: TestClient, trip_id: int, day: str) -> list[dict[str, object]]:
    reply = client.get(f"/api/trips/{trip_id}/days/{day}/suggestions")
    assert reply.status_code == 200
    rows: list[dict[str, object]] = reply.json()
    return rows
