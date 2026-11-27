# ADDED [PROMPT #13]: app factory and entry point (wiring, schema init, localhost bind).
# AI-assisted, Claude Opus 5.5.
"""`create_app()` wires the parts; `run()` serves on 127.0.0.1 only."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from trip_journal.agent.llm import LLMClient, OllamaClient
from trip_journal.agent.prompts import PromptLibrary
from trip_journal.api import days as days_api
from trip_journal.api import jobs as jobs_api
from trip_journal.api import notes as notes_api
from trip_journal.api import settings as settings_api
from trip_journal.api import trips as trips_api
from trip_journal.api.deps import AppState, JobView
from trip_journal.config import DEFAULT_DB_PATH, ENV_DB_PATH, HOST, PACKAGE_DIR, PORT, PORT_ENV
from trip_journal.data.db import connect, init_schema
from trip_journal.data.repositories import Repositories
from trip_journal.logs import kv, setup_logging
from trip_journal.pages import days as days_pages
from trip_journal.pages import notes as notes_pages  # ADDED [PROMPT #25]
from trip_journal.pages import settings as settings_pages
from trip_journal.pages import trips as trips_pages
from trip_journal.places.lookup import PlaceLookup
from trip_journal.services.imports import ImportService
from trip_journal.services.jobs import JobRunner
from trip_journal.services.organizer import JOB_KIND as ORGANIZE_JOB_KIND
from trip_journal.services.organizer import OrganizerService
from trip_journal.services.settings import Settings, SettingsService
from trip_journal.services.trips import TripService


def create_app(
    db_path: Path | str | None = None,
    http: httpx.AsyncClient | None = None,
    env: Mapping[str, str] | None = None,
    jobs: JobRunner | None = None,
    # ADDED [PROMPT #25]: D-1, tests pass a factory that returns a FakeLLMClient.
    llm_factory: Callable[[Settings], LLMClient] | None = None,
) -> FastAPI:
    environ = os.environ if env is None else env
    path = db_path or environ.get(ENV_DB_PATH) or DEFAULT_DB_PATH
    conn = connect(path)
    init_schema(conn)
    repos = Repositories.from_connection(conn)
    owns_http = http is None
    client = http or httpx.AsyncClient()
    settings = SettingsService(repos.settings, env=environ, http=client)
    runner = jobs or JobRunner()
    trips = TripService(repos, runner)

    # ADDED [PROMPT #25]: D-1, called per organize run so a settings change applies next run.
    def ollama_factory(current: Settings) -> LLMClient:
        return OllamaClient(current.ollama_base_url, current.model_name, http=client)

    factory = llm_factory or ollama_factory
    organizer = OrganizerService(repos, runner, settings, trips, factory, PromptLibrary())
    state = AppState(
        conn=conn,
        repos=repos,
        settings=settings,
        jobs=runner,
        places=PlaceLookup(
            is_enabled=lambda: settings.get().place_lookup_enabled,
            cache=repos.place_cache,
            http=client,
        ),
        http=client,
        trips=trips,
        imports=ImportService(conn, repos, trips),
        organizer=organizer,
        llm_factory=factory,
    )
    # ADDED [PROMPT #25]: finished organize jobs show the run summary (step 15 template).
    # No retry URL: JobView is static and the run's trip / day is not known here (D-29);
    # the Organize button next to the job box is the retry.
    state.job_views[ORGANIZE_JOB_KIND] = JobView("organizer/summary.html", retry_url=None)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if owns_http:
                await client.aclose()
            conn.close()

    app = FastAPI(title="Trip Journal Agent", lifespan=lifespan)
    app.state.trip = state
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "pages" / "static"), name="static")
    app.include_router(settings_api.router)
    app.include_router(jobs_api.router)
    app.include_router(settings_pages.router)
    # ADDED [PROMPT #17]: U2 routers.
    app.include_router(trips_api.router)
    app.include_router(days_api.router)
    app.include_router(trips_pages.router)
    app.include_router(days_pages.router)
    # ADDED [PROMPT #25]: U3 JSON API and pages (IC-7, plan steps 13-14).
    app.include_router(notes_api.router)
    app.include_router(notes_pages.router)

    @app.get("/", include_in_schema=False)
    async def home() -> RedirectResponse:
        # CHANGED [PROMPT #17]: the trip list is the home page (D-2).
        return RedirectResponse("/trips", status_code=307)

    return app


# ADDED [PROMPT #17]: CI-1 port override (D-7).
def resolve_port(env: Mapping[str, str] | None = None) -> int:
    """`TRIP_JOURNAL_PORT` when it is a port number (1-65535); otherwise PORT with a warning."""
    raw = (os.environ if env is None else env).get(PORT_ENV)
    if raw is None or raw.strip() == "":
        return PORT
    text = raw.strip()
    if text.isdigit() and 1 <= int(text) <= 65535:
        return int(text)
    logging.getLogger(__name__).warning(kv("port.invalid", value=text[:20], used=PORT))
    return PORT


def run() -> None:
    import uvicorn

    setup_logging()
    # CHANGED [PROMPT #17]: port from TRIP_JOURNAL_PORT (CI-1).
    uvicorn.run(create_app(), host=HOST, port=resolve_port(), log_config=None)


if __name__ == "__main__":
    run()
