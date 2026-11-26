# ADDED [PROMPT #13]: shared app state and FastAPI dependencies. AI-assisted, Claude Opus 5.5.
"""One AppState per app, built by `create_app`; routes get it through `get_state`."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

import httpx
from fastapi import Request

from trip_journal.data.repositories import Repositories
from trip_journal.places.lookup import PlaceLookup
from trip_journal.services.jobs import JobRunner
from trip_journal.services.settings import SettingsService


@dataclass(frozen=True)
class JobView:
    """How a finished job of one kind is shown; registered by the unit that owns the kind."""

    result_template: str
    retry_url: str | None = None


@dataclass
class AppState:
    conn: sqlite3.Connection
    repos: Repositories
    settings: SettingsService
    jobs: JobRunner
    places: PlaceLookup
    http: httpx.AsyncClient
    job_views: dict[str, JobView] = field(default_factory=dict)


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.trip
    return state
