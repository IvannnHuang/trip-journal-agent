# ADDED [PROMPT #13]: shared fixtures and Hypothesis profiles (NP-8). AI-assisted, Claude Opus 5.5.
"""Fixtures: in-memory database, seeded trip, a mocked HTTP client, and the app.

No test touches the network or a real Ollama: every HTTP call goes through
`httpx.MockTransport`.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import httpx
import pytest
from fastapi.testclient import TestClient
from hypothesis import settings

from tests.fixtures import Services, make_services
from tests.fixtures.organizer import SAMPLE_DAY_LABELS, make_app_client, organizer_reply
from trip_journal.agent.llm import FakeLLMClient
from trip_journal.agent.prompts import PromptLibrary
from trip_journal.data.db import connect, init_schema
from trip_journal.data.repositories import Repositories
from trip_journal.main import create_app
from trip_journal.places.lookup import PlaceLookup

# ADDED [PROMPT #36]: offline journal fixtures.
from trip_journal.services.journal import JournalService
from trip_journal.services.settings import SettingsService

settings.register_profile("default", max_examples=100, deadline=None, print_blob=True)
settings.register_profile("ci", max_examples=500, deadline=None, print_blob=True)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))

INSTALLED = ["qwen3:8b", "llama3.2:latest"]


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    c = connect(":memory:")
    init_schema(c)
    yield c
    c.close()


@pytest.fixture
def repos(conn: sqlite3.Connection) -> Repositories:
    return Repositories.from_connection(conn)


# ADDED [PROMPT #17]: U2 services over the in-memory database.
@pytest.fixture
def services(conn: sqlite3.Connection) -> Services:
    return make_services(conn)


@dataclass
class Seed:
    trip_id: int
    other_trip_id: int
    stops: list[int]
    notes: list[int]
    photos: list[int]


@pytest.fixture
def seed(repos: Repositories) -> Seed:
    """Trip 1: two stops on 2026-06-01 (UTC+2), notes and photos; trip 2 has one note."""
    trip = repos.trips.add("trip-a", "Alps")
    other = repos.trips.add("trip-b", "Coast")
    s1 = repos.stops.add(
        trip,
        "s1",
        "Lake Bled",
        "2026-06-01T07:00:00Z",
        "2026-06-01T09:00:00Z",
        120,
        46.3625,
        14.0938,
    )
    s2 = repos.stops.add(
        trip, "s2", None, "2026-06-01T11:00:00Z", "2026-06-01T12:00:00Z", 120, 46.5, 14.2
    )
    n1 = repos.notes.add(
        trip, "n1", "Swam in the lake, water was cold", "2026-06-01T07:30:00Z", 120, s1
    )
    n2 = repos.notes.add(trip, "n2", "Lunch: cream cake", "2026-06-01T11:15:00Z", 120, s2)
    n3 = repos.notes.add(trip, "n3", "Train was late", "2026-06-02T08:00:00Z", 120)
    repos.notes.add(other, "o1", "Lake swim at the coast", "2026-07-01T08:00:00Z", 0)
    p1 = repos.photos.add(trip, "p1", "2026-06-01T07:45:00Z", 120, 46.36, 14.09, "IMG_1.jpg")
    p2 = repos.photos.add(trip, "p2", "2026-06-01T11:30:00Z", 120)
    return Seed(trip, other, [s1, s2], [n1, n2, n3], [p1, p2])


@dataclass
class FakeOllama:
    """A scripted `/api/tags` endpoint. Set `up=False` to simulate Ollama not running."""

    up: bool = True
    models: list[str] = field(default_factory=lambda: list(INSTALLED))
    requests: list[httpx.Request] = field(default_factory=list)
    nominatim: Callable[[httpx.Request], httpx.Response] | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == "nominatim.openstreetmap.org":
            if self.nominatim is None:
                return httpx.Response(500)
            return self.nominatim(request)
        if not self.up:
            raise httpx.ConnectError("connection refused", request=request)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": m} for m in self.models]})
        return httpx.Response(404)


@pytest.fixture
def ollama() -> FakeOllama:
    return FakeOllama()


@pytest.fixture
def http(ollama: FakeOllama) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(ollama.handler))


@pytest.fixture
def client(http: httpx.AsyncClient) -> Iterator[TestClient]:
    app = create_app(":memory:", http=http, env={})
    with TestClient(app) as c:
        yield c


# ADDED [PROMPT #25]: U3 organizer fixtures (plan step 16). FakeLLMClient only.
@pytest.fixture
def fake_llm() -> FakeLLMClient:
    """One valid reply for the sample day (8 notes, one batch), category food."""
    return FakeLLMClient([organizer_reply(*SAMPLE_DAY_LABELS)])


@pytest.fixture
def organizer_client(http: httpx.AsyncClient, fake_llm: FakeLLMClient) -> Iterator[TestClient]:
    """The app built with `llm_factory` returning `fake_llm`."""
    yield from make_app_client(http, fake_llm)


# ADDED [PROMPT #36]: two multi-chunk days with distinct stop and note records.
@pytest.fixture
def journal_trip(repos: Repositories) -> int:
    trip = repos.trips.add("journal-trip", "Journal trip")
    for day, count in [("2026-06-01", 8), ("2026-06-02", 13)]:
        for i in range(count):
            stamp = f"{day}T{i:02}:00:00Z"
            source = f"{day}-{i}"
            stop = repos.stops.add(trip, source, f"Stop {i}", stamp, stamp, 0, 0, 0)
            repos.notes.add(trip, source, f"Private note {i}", stamp, 0, stop)
    return trip


@pytest.fixture
def journal_service(
    services: Services, http: httpx.AsyncClient, fake_llm: FakeLLMClient
) -> JournalService:
    repos = services.repos
    return JournalService(
        repos,
        services.jobs,
        SettingsService(repos.settings, env={}, http=http),
        services.trips,
        lambda _: fake_llm,
        PromptLibrary(),
        PlaceLookup(lambda: False, repos.place_cache, http),
    )
