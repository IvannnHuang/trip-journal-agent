# ADDED [PROMPT #17]: trips JSON API (frontend-components 2.6). AI-assisted, Claude Opus 5.5.
"""GET/POST /api/trips, GET/DELETE /api/trips/{trip_id}."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse, Response

from trip_journal.api.deps import AppState, get_state
from trip_journal.domain.views import TripSummary
from trip_journal.services.errors import (
    AppError,
    ImportValidationError,
    JobRunningError,
    NotFoundError,
    TripAlreadyExistsError,
    to_user_facing,
)

router = APIRouter(prefix="/api/trips", tags=["trips"])
StateDep = Annotated[AppState, Depends(get_state)]


def error_response(exc: AppError) -> JSONResponse:
    """U1 error body (`code`, `message`, ...), plus `issues` and `more` for a refused import."""
    body: dict[str, Any] = to_user_facing(exc).model_dump()
    if isinstance(exc, ImportValidationError):
        body["issues"] = [{"location": i.location, "message": i.message} for i in exc.issues]
        body["more"] = exc.more
    return JSONResponse(status_code=exc.http_status, content=body)


async def read_upload(upload: UploadFile, max_bytes: int) -> bytes:
    """N-1: read at most `max_bytes + 1`, so the size check sees an oversize file."""
    return await upload.read(max_bytes + 1)


@router.get("")
async def list_trips(state: StateDep) -> list[TripSummary]:
    return state.trips.list_trips()


@router.post("", status_code=201, response_model=None)
async def import_trip(
    state: StateDep, file: Annotated[UploadFile, File()]
) -> TripSummary | JSONResponse:
    raw = await read_upload(file, state.imports.max_bytes)
    try:
        return state.imports.import_trip(raw, file.filename)
    except (ImportValidationError, TripAlreadyExistsError) as exc:
        return error_response(exc)


@router.get("/{trip_id}", response_model=None)
async def get_trip(trip_id: int, state: StateDep) -> TripSummary | JSONResponse:
    try:
        return state.trips.get_summary(trip_id)
    except NotFoundError as exc:
        return error_response(exc)


@router.delete("/{trip_id}", status_code=204, response_model=None)
async def delete_trip(trip_id: int, state: StateDep) -> Response:
    try:
        state.trips.delete_trip(trip_id)
    except (NotFoundError, JobRunningError) as exc:
        return error_response(exc)
    return Response(status_code=204)
