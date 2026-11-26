# ADDED [PROMPT #13]: settings JSON API (US-18, SE-5, ST-1). AI-assisted, Claude Opus 5.5.
"""GET/PUT /api/settings and GET /api/settings/model-status."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from trip_journal.agent.llm import ModelStatus
from trip_journal.api.deps import AppState, get_state
from trip_journal.pages.render import templates
from trip_journal.services.errors import SettingsValidationError, status_message
from trip_journal.services.settings import Settings, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])
StateDep = Annotated[AppState, Depends(get_state)]


@router.get("")
async def read_settings(state: StateDep) -> Settings:
    return state.settings.get()


@router.put("", response_model=None)
async def update_settings(change: SettingsUpdate, state: StateDep) -> Settings | JSONResponse:
    try:
        return state.settings.update(change)
    except SettingsValidationError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "code": "invalid_settings",
                "message": "Some settings are not valid. Nothing was saved.",
                "issues": exc.issues,
            },
        )


@router.get("/model-status", response_model=None)
async def model_status(request: Request, state: StateDep) -> ModelStatus | Response:
    status = await state.settings.model_status()
    if request.headers.get("HX-Request") == "true":
        html = templates.get_template("_partials/status_panel.html").render(
            status=status, warning=status_message(status)
        )
        return HTMLResponse(html)
    return status
