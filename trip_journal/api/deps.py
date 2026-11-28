# ADDED [PROMPT #13]: shared app state and FastAPI dependencies. AI-assisted, Claude Opus 5.5.
"""One AppState per app, built by `create_app`; routes get it through `get_state`."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import Request

from trip_journal.agent.llm import LLMClient
from trip_journal.data.repositories import Repositories
from trip_journal.places.lookup import PlaceLookup
from trip_journal.services.imports import ImportService
from trip_journal.services.jobs import JobRunner, JobStatus
from trip_journal.services.journal import JournalService  # ADDED [PROMPT #36]: journal service.
from trip_journal.services.organizer import OrganizerService
from trip_journal.services.settings import Settings, SettingsService
from trip_journal.services.trips import TripService


@dataclass(frozen=True)
class JobView:
    """How a finished job of one kind is shown; registered by the unit that owns the kind."""

    result_template: str
    retry_url: str | None = None
    # ADDED [PROMPT #36]: allow a finished-job fragment to refresh mutable data.
    fresh_context: Callable[[AppState, JobStatus], dict[str, Any]] | None = None


@dataclass
class AppState:
    conn: sqlite3.Connection
    repos: Repositories
    settings: SettingsService
    jobs: JobRunner
    places: PlaceLookup
    http: httpx.AsyncClient
    # ADDED [PROMPT #17]: U2 services (C03, C04).
    trips: TripService
    imports: ImportService
    # ADDED [PROMPT #25]: U3 organizer (IC-5) and the per-run LLM client factory (D-1).
    journal: JournalService  # ADDED [PROMPT #36]: daily journal operations.
    organizer: OrganizerService
    llm_factory: Callable[[Settings], LLMClient]
    job_views: dict[str, JobView] = field(default_factory=dict)


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.trip
    return state
