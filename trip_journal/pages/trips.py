# ADDED [PROMPT #17]: trip list, import, overview, activate and delete pages
# (frontend-components 2.1, 2.2, 2.4, 2.5). AI-assisted, Claude Opus 5.5.
"""Server-rendered trip pages; they work without JavaScript, htmx only improves import."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from trip_journal.api.deps import AppState, get_state
from trip_journal.api.trips import read_upload
from trip_journal.pages.render import organizer_area, render_fragment, render_page
from trip_journal.services.errors import (
    ImportValidationError,
    JobRunningError,
    NotFoundError,
    TripAlreadyExistsError,
    to_user_facing,
)

router = APIRouter(include_in_schema=False)
StateDep = Annotated[AppState, Depends(get_state)]


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


async def not_found_page(request: Request, state: AppState, exc: NotFoundError) -> HTMLResponse:
    """2.5: shared 404 page with the fixed message and a link to the trip list."""
    return await render_page(
        request,
        state,
        "errors/404.html",
        {"error": to_user_facing(exc), "active": "trips"},
        status_code=404,
    )


def _import_context(state: AppState, exc: Exception | None = None) -> dict[str, Any]:
    context: dict[str, Any] = {"error": None, "issues": [], "more": 0, "existing_trip_id": None}
    if isinstance(exc, ImportValidationError):
        context.update(error=to_user_facing(exc), issues=exc.issues, more=exc.more)
    elif isinstance(exc, TripAlreadyExistsError):
        existing = state.repos.trips.get_by_source_id(exc.source_id)
        context.update(
            error=to_user_facing(exc), existing_trip_id=existing.id if existing else None
        )
    return context


async def _list_page(
    request: Request,
    state: AppState,
    exc: Exception | None = None,
    deleted: bool = False,
    status_code: int = 200,
) -> HTMLResponse:
    context = {
        "trips": state.trips.list_trips(),
        "deleted": deleted,
        "active": "trips",
        **_import_context(state, exc),
    }
    return await render_page(request, state, "trips/list.html", context, status_code=status_code)


@router.get("/trips", response_class=HTMLResponse)
async def trip_list(request: Request, state: StateDep, deleted: int = 0) -> HTMLResponse:
    return await _list_page(request, state, deleted=deleted == 1)


@router.post("/trips/import", response_model=None)
async def import_trip(
    request: Request, state: StateDep, file: Annotated[UploadFile, File()]
) -> Response:
    raw = await read_upload(file, state.imports.max_bytes)
    try:
        summary = state.imports.import_trip(raw, file.filename)
    except (ImportValidationError, TripAlreadyExistsError) as exc:
        if is_htmx(request):
            # U.1: htmx swaps only the import panel; the status code stays 422 / 409.
            response = render_fragment(
                request, "_partials/import_form.html", _import_context(state, exc)
            )
            response.status_code = exc.http_status
            return response
        return await _list_page(request, state, exc, status_code=exc.http_status)
    target = f"/trips/{summary.trip_id}"
    if is_htmx(request):
        return Response(status_code=200, headers={"HX-Redirect": target})
    return RedirectResponse(target, status_code=303)


@router.post("/trips/{trip_id}/activate", response_model=None)
async def activate_trip(request: Request, trip_id: int, state: StateDep) -> Response:
    try:
        state.trips.set_active_trip(trip_id)
    except NotFoundError as exc:
        return await not_found_page(request, state, exc)
    return RedirectResponse("/trips", status_code=303)


@router.get("/trips/{trip_id}", response_class=HTMLResponse)
async def trip_overview(
    request: Request, trip_id: int, state: StateDep, job: str | None = None, nothing: int = 0
) -> HTMLResponse:
    return await render_overview(request, state, trip_id, organizer_area(state, job, nothing == 1))


# CHANGED [PROMPT #25]: shared with the U3 "Organize the whole trip" form (organizer area keys).
async def render_overview(
    request: Request,
    state: AppState,
    trip_id: int,
    extra: dict[str, Any] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    try:
        state.trips.set_active_trip(trip_id)  # AT-2
        summary = state.trips.get_summary(trip_id)
    except NotFoundError as exc:
        return await not_found_page(request, state, exc)
    context = {
        "trip": summary,
        "active": "trips",
        **organizer_area(state, None, False),
        **(extra or {}),
    }
    return await render_page(
        request, state, "trips/overview.html", context, status_code=status_code
    )


async def _delete_page(
    request: Request, state: AppState, trip_id: int, error_exc: Exception | None = None
) -> HTMLResponse:
    preview = state.trips.get_delete_preview(trip_id)
    error = to_user_facing(error_exc) if error_exc is not None else None
    return await render_page(
        request,
        state,
        "trips/delete.html",
        {"preview": preview, "error": error, "active": "trips"},
        status_code=409 if isinstance(error_exc, JobRunningError) else 200,
    )


@router.get("/trips/{trip_id}/delete", response_class=HTMLResponse)
async def delete_confirm(request: Request, trip_id: int, state: StateDep) -> HTMLResponse:
    """DL-1: a GET never deletes. R.5: refused with 409 while a job runs."""
    try:
        state.trips.get_delete_preview(trip_id)
        try:
            state.trips.ensure_no_job_running()
        except JobRunningError as exc:
            return await _delete_page(request, state, trip_id, exc)
        return await _delete_page(request, state, trip_id)
    except NotFoundError as exc:
        return await not_found_page(request, state, exc)


@router.post("/trips/{trip_id}/delete", response_model=None)
async def delete_trip(request: Request, trip_id: int, state: StateDep) -> Response:
    try:
        state.trips.delete_trip(trip_id)
    except NotFoundError as exc:
        return await not_found_page(request, state, exc)
    except JobRunningError as exc:
        return await _delete_page(request, state, trip_id, exc)
    return RedirectResponse("/trips?deleted=1", status_code=303)
