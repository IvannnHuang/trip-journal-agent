# ADDED [PROMPT #13]: app factory and entry point (wiring, schema init, localhost bind).
# AI-assisted, Claude Opus 5.5.
"""`create_app()` wires the parts; `run()` serves on 127.0.0.1 only."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from trip_journal.api import jobs as jobs_api
from trip_journal.api import settings as settings_api
from trip_journal.api.deps import AppState
from trip_journal.config import DEFAULT_DB_PATH, ENV_DB_PATH, HOST, PACKAGE_DIR, PORT
from trip_journal.data.db import connect, init_schema
from trip_journal.data.repositories import Repositories
from trip_journal.logs import setup_logging
from trip_journal.pages import settings as settings_pages
from trip_journal.places.lookup import PlaceLookup
from trip_journal.services.jobs import JobRunner
from trip_journal.services.settings import SettingsService


def create_app(
    db_path: Path | str | None = None,
    http: httpx.AsyncClient | None = None,
    env: Mapping[str, str] | None = None,
    jobs: JobRunner | None = None,
) -> FastAPI:
    environ = os.environ if env is None else env
    path = db_path or environ.get(ENV_DB_PATH) or DEFAULT_DB_PATH
    conn = connect(path)
    init_schema(conn)
    repos = Repositories.from_connection(conn)
    owns_http = http is None
    client = http or httpx.AsyncClient()
    settings = SettingsService(repos.settings, env=environ, http=client)
    state = AppState(
        conn=conn,
        repos=repos,
        settings=settings,
        jobs=jobs or JobRunner(),
        places=PlaceLookup(
            is_enabled=lambda: settings.get().place_lookup_enabled,
            cache=repos.place_cache,
            http=client,
        ),
        http=client,
    )

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

    @app.get("/", include_in_schema=False)
    async def home() -> RedirectResponse:
        # U1 has no trips page yet; U2 replaces this with the trip list.
        return RedirectResponse("/settings", status_code=307)

    return app


def run() -> None:
    import uvicorn

    setup_logging()
    uvicorn.run(create_app(), host=HOST, port=PORT, log_config=None)


if __name__ == "__main__":
    run()
