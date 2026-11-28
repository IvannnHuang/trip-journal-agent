# ADDED [PROMPT #13]: Settings page and the job progress fragment (US-18, US-19, ST-6).
# AI-assisted, Claude Opus 5.5.
"""GET/POST /settings and GET /jobs/{job_id}/fragment."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from trip_journal.api.deps import AppState, get_state
from trip_journal.pages.render import render_fragment, render_page
from trip_journal.services.errors import (
    NotFoundError,
    SettingsValidationError,
    status_message,
    to_user_facing,
)
from trip_journal.services.settings import SettingsUpdate

router = APIRouter(include_in_schema=False)
StateDep = Annotated[AppState, Depends(get_state)]


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, state: StateDep) -> HTMLResponse:
    current = state.settings.get()
    status = await state.settings.model_status(current)
    form = current.model_dump()
    return await render_page(
        request,
        state,
        "settings.html",
        {
            "form": form,
            "issues": {},
            "saved": False,
            "warning": status_message(status),
            "status": status,
            "active": "settings",
        },
        status=status,
    )


@router.post("/settings", response_class=HTMLResponse)
async def save_settings(
    request: Request,
    state: StateDep,
    model_name: Annotated[str, Form()] = "",
    ollama_base_url: Annotated[str, Form()] = "",
    place_lookup_enabled: Annotated[str | None, Form()] = None,
) -> HTMLResponse:
    change = SettingsUpdate(
        model_name=model_name,
        ollama_base_url=ollama_base_url,
        place_lookup_enabled=place_lookup_enabled is not None,  # unchecked box sends nothing
    )
    issues: dict[str, str] = {}
    saved = False
    try:
        current = state.settings.update(change)
        form = current.model_dump()
        saved = True
    except SettingsValidationError as exc:
        issues = exc.issues
        current = state.settings.get()
        form = {
            "model_name": model_name,
            "ollama_base_url": ollama_base_url,
            "place_lookup_enabled": place_lookup_enabled is not None,
        }
    status = await state.settings.model_status(current)
    return await render_page(
        request,
        state,
        "settings.html",
        {
            "form": form,
            "issues": issues,
            "saved": saved,
            "warning": status_message(status),
            "status": status,
            "active": "settings",
        },
        status=status,
    )


@router.get("/jobs/{job_id}/fragment", response_class=HTMLResponse)
async def job_fragment(job_id: str, request: Request, state: StateDep) -> HTMLResponse:
    try:
        job = state.jobs.status(job_id)
    except NotFoundError as exc:
        return render_fragment(
            request, "_partials/error.html", {"error": to_user_facing(exc), "retry_url": None}
        )
    view = state.job_views.get(job.kind)
    # CHANGED [PROMPT #36]: resolve the journal body at poll time.
    try:
        fresh = (
            view.fresh_context(state, job)
            if view and view.fresh_context and job.state == "done"
            else {}
        )
    except NotFoundError as exc:
        return render_fragment(request, "_partials/error.html", {"error": to_user_facing(exc)})
    return render_fragment(
        request,
        "_partials/job_progress.html",
        {"job": job, "view": view, "retry_url": view.retry_url if view else None, **fresh},
    )
