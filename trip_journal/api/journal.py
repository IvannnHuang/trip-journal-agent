# ADDED [PROMPT #36]: JSON journal operations and htmx form responses.
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, ValidationError

from trip_journal.api.days import is_valid_day
from trip_journal.api.deps import AppState, get_state
from trip_journal.api.notes import invalid_date
from trip_journal.domain.journal_merge import Tone
from trip_journal.pages.render import render_fragment
from trip_journal.pages.trips import is_htmx
from trip_journal.services.errors import AppError, UserFacingError, to_user_facing
from trip_journal.services.jobs import JobRef

router = APIRouter(prefix="/api/trips/{trip_id}/days/{day}/journal", tags=["journal"])
StateDep = Annotated[AppState, Depends(get_state)]


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tone: Tone


class EditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


async def body[T: BaseModel](request: Request, model: type[T]) -> T:
    if is_htmx(request) and "application/json" not in request.headers.get("content-type", ""):
        return model.model_validate(dict(await request.form()))
    return model.model_validate_json(await request.body())


def respond(
    request: Request, model: BaseModel, template: str, context: dict[str, Any], status: int = 200
) -> Response:
    if is_htmx(request):
        fragment = render_fragment(request, template, context)
        fragment.status_code = status
        return fragment
    return JSONResponse(model.model_dump(mode="json"), status_code=status)


def error(request: Request, exc: AppError | ValidationError) -> Response:
    if isinstance(exc, AppError):
        view = to_user_facing(exc)
        status = exc.http_status
        # CHANGED [PROMPT #36]: use the journal's busy copy on the page (D-1).
        if view.code == "model_busy" and is_htmx(request):
            view = view.model_copy(
                update={
                    "message": "Another job is running. Try again when it finishes.",
                    "action": "",
                }
            )
    else:
        status = 422
        view = UserFacingError(
            code="invalid_request",
            message="Invalid journal request.",
            action="Check the submitted fields.",
        )
    return respond(request, view, "_partials/error.html", {"error": view}, status)


def date_error(request: Request) -> Response:
    response = invalid_date()
    if is_htmx(request):
        view = UserFacingError.model_validate_json(bytes(response.body))
        return respond(request, view, "_partials/error.html", {"error": view}, 422)
    return response


@router.get("")
async def get_journal(trip_id: int, day: str, state: StateDep, request: Request) -> Response:
    if not is_valid_day(day):
        return date_error(request)
    try:
        view = state.journal.get_journal(trip_id, day)
    except AppError as exc:
        return error(request, exc)
    # CHANGED [PROMPT #36]: empty bodies distinguish photo-only days.
    context: dict[str, Any] = {"journal": view}
    if is_htmx(request) and not view.paragraphs:
        timeline = state.trips.get_day(trip_id, day)
        context["has_records"] = bool(
            timeline.stops or state.repos.notes.list_for_day(trip_id, day)
        )
    return respond(request, view, "_partials/journal_body.html", context)


@router.post("", status_code=202)
async def generate(trip_id: int, day: str, state: StateDep, request: Request) -> Response:
    if not is_valid_day(day):
        return date_error(request)
    try:
        options = await body(request, GenerateRequest)
        result = await state.journal.start_generation(trip_id, day, options.tone)
    except (AppError, ValidationError) as exc:
        return error(request, exc)
    if isinstance(result, JobRef):
        return respond(
            request,
            result,
            "_partials/job_progress.html",
            {"job": state.jobs.status(result.job_id), "view": state.job_views["journal"]},
            202,
        )
    return respond(request, result, "journal/status.html", {"message": result.message})


@router.put("/paragraphs/{slot}")
async def edit(trip_id: int, day: str, slot: str, state: StateDep, request: Request) -> Response:
    if not is_valid_day(day):
        return date_error(request)
    try:
        values = await body(request, EditRequest)
        result = state.journal.edit_paragraph(trip_id, day, slot, values.text)
    except (AppError, ValidationError) as exc:
        return error(request, exc)
    return respond(request, result, "journal/status.html", {"message": "Saved", "edit": result})
