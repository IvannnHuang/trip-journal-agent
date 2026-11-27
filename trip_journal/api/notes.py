# ADDED [PROMPT #25]: U3 note organizer JSON API (IC-7, plan step 13). AI-assisted, Claude Opus 5.5.
"""Organize runs and suggestion review.

POST /api/trips/{trip_id}/organize               202 job, 200 nothing to send, 404, 429, 503
GET  /api/trips/{trip_id}/days/{day}/suggestions  200 list, 404, 422 invalid_date
POST /api/suggestions/{sid}/accept|reject|undo    200 view, 404, 409 suggestion_state
PUT  /api/suggestions/{sid}                       200 view, 404, 409, 422 invalid_edit
POST /api/trips/{trip_id}/days/{day}/suggestions/accept-all   200 {"accepted": n}, 404
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from trip_journal.api.days import is_valid_day
from trip_journal.api.deps import AppState, get_state
from trip_journal.api.trips import error_response
from trip_journal.domain.organizer import SuggestionView
from trip_journal.services.errors import (
    ModelBusyError,
    ModelUnavailableError,
    NotFoundError,
    SuggestionEditError,
    SuggestionStateError,
    to_user_facing,
)

router = APIRouter(prefix="/api", tags=["notes"])
StateDep = Annotated[AppState, Depends(get_state)]

NOTHING_TO_ORGANIZE = "Nothing to organize: every note already has a decision."


class OrganizeRequest(BaseModel):
    """`day` = one day (`YYYY-MM-DD`); None = the whole trip."""

    day: str | None = None


def invalid_date() -> JSONResponse:
    # Same body as GET /api/trips/{id}/days/{day} (TL-2).
    return JSONResponse(
        status_code=422,
        content={
            "code": "invalid_date",
            "message": "The date must be a real date written YYYY-MM-DD.",
            "action": "Use a date from the trip's day list.",
            "trace": [],
        },
    )


def invalid_edit(exc: SuggestionEditError) -> JSONResponse:
    """422 invalid_edit with one message per field (OR-E4)."""
    body: dict[str, Any] = to_user_facing(exc).model_dump()
    body["fields"] = exc.fields
    return JSONResponse(status_code=exc.http_status, content=body)


@router.post("/trips/{trip_id}/organize", status_code=202, response_model=None)
async def organize(
    trip_id: int, state: StateDep, body: Annotated[OrganizeRequest | None, Body()] = None
) -> JSONResponse:
    day = body.day if body is not None else None
    if day is not None and not is_valid_day(day):
        return invalid_date()
    try:
        started = await state.organizer.start(trip_id, day)
    except (NotFoundError, ModelBusyError, ModelUnavailableError) as exc:
        return error_response(exc)
    if started.job is None:  # OR-RUN5: no job starts
        return JSONResponse(
            status_code=200,
            content={
                "job_id": None,
                "kind": None,
                "notes_to_send": 0,
                "batches": 0,
                "message": NOTHING_TO_ORGANIZE,
            },
        )
    return JSONResponse(
        status_code=202,
        content={
            "job_id": started.job.job_id,
            "kind": started.job.kind,
            "notes_to_send": started.notes_to_send,
            "batches": started.batches,
        },
    )


@router.get("/trips/{trip_id}/days/{day}/suggestions", response_model=None)
async def list_suggestions(
    trip_id: int, day: str, state: StateDep
) -> list[SuggestionView] | JSONResponse:
    if not is_valid_day(day):
        return invalid_date()
    try:
        return state.organizer.list_for_day(trip_id, day)
    except NotFoundError as exc:
        return error_response(exc)


@router.post("/trips/{trip_id}/days/{day}/suggestions/accept-all", response_model=None)
async def accept_all(trip_id: int, day: str, state: StateDep) -> dict[str, int] | JSONResponse:
    if not is_valid_day(day):
        return invalid_date()
    try:
        return {"accepted": state.organizer.accept_all(trip_id, day)}
    except NotFoundError as exc:
        return error_response(exc)


@router.post("/suggestions/{suggestion_id}/accept", response_model=None)
async def accept(suggestion_id: int, state: StateDep) -> SuggestionView | JSONResponse:
    try:
        return state.organizer.accept(suggestion_id)
    except (NotFoundError, SuggestionStateError) as exc:
        return error_response(exc)


@router.post("/suggestions/{suggestion_id}/reject", response_model=None)
async def reject(suggestion_id: int, state: StateDep) -> SuggestionView | JSONResponse:
    try:
        return state.organizer.reject(suggestion_id)
    except (NotFoundError, SuggestionStateError) as exc:
        return error_response(exc)


@router.post("/suggestions/{suggestion_id}/undo", response_model=None)
async def undo(suggestion_id: int, state: StateDep) -> SuggestionView | JSONResponse:
    try:
        return state.organizer.undo(suggestion_id)
    except (NotFoundError, SuggestionStateError) as exc:
        return error_response(exc)


@router.put("/suggestions/{suggestion_id}", response_model=None)
async def edit(
    suggestion_id: int, state: StateDep, raw: Annotated[dict[str, Any], Body()]
) -> SuggestionView | JSONResponse:
    try:
        return state.organizer.edit_and_accept(suggestion_id, raw)
    except SuggestionEditError as exc:
        return invalid_edit(exc)
    except (NotFoundError, SuggestionStateError) as exc:
        return error_response(exc)
