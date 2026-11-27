# ADDED [PROMPT #17]: import and page speed (U2-NFR-P.1..P.4). Slow: run with `-m slow`.
# AI-assisted, Claude Opus 5.5.
"""Timings are printed (`-s`) so Build and Test can record them against the targets."""

from __future__ import annotations

import importlib.util
import time
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from tests.fixtures import minimal_trip_bytes

pytestmark = pytest.mark.slow
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "make_reference_trip.py"


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("make_reference_trip", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _timed_import(client: TestClient, raw: bytes) -> tuple[float, int]:
    begin = time.perf_counter()
    reply = client.post("/api/trips", files={"file": ("t.json", raw)})
    elapsed = time.perf_counter() - begin
    assert reply.status_code == 201, reply.text[:500]
    trip_id: int = reply.json()["trip_id"]
    return elapsed, trip_id


def _report(name: str, seconds: float, target: float) -> None:
    verdict = "ok" if seconds <= target else "MISS"
    print(f"\n{name}: {seconds:.3f} s (target {target} s) {verdict}")


def test_p1_sample_import(client: TestClient) -> None:
    elapsed, _ = _timed_import(client, minimal_trip_bytes())
    _report("P.1 sample import", elapsed, 1.0)
    assert elapsed <= 1.0


def test_p2_p4_reference_trip(client: TestClient) -> None:
    gen = _generator()
    elapsed, trip_id = _timed_import(client, gen.encode(gen.build_trip()))
    _report("P.2 reference import", elapsed, 5.0)
    begin = time.perf_counter()
    assert client.get("/trips").status_code == 200
    list_s = time.perf_counter() - begin
    _report("P.4 GET /trips", list_s, 0.3)
    days = client.get(f"/api/trips/{trip_id}").json()["days"]
    busiest = max(days, key=lambda d: d["stop_count"] + d["note_count"] + d["photo_count"])
    begin = time.perf_counter()
    assert client.get(f"/trips/{trip_id}/days/{busiest['local_date']}").status_code == 200
    day_s = time.perf_counter() - begin
    _report("P.4 busiest day page", day_s, 0.3)
    assert elapsed <= 5.0 and list_s <= 0.3 and day_s <= 0.3


def test_p3_large_file(client: TestClient) -> None:
    raw = _generator().build_large()
    print(f"\nlarge file {len(raw) / 1e6:.2f} MB")
    elapsed, _ = _timed_import(client, raw)
    _report("P.3 ~20 MB import", elapsed, 15.0)
    assert elapsed <= 15.0
