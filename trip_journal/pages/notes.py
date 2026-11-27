# ADDED [PROMPT #25]: U3 note organizer pages (frontend-components 1 and 5.1, plan step 14).
# AI-assisted, Claude Opus 5.5.
"""Organize runs and suggestion review as plain forms; htmx only swaps regions.

POST /trips/{trip_id}/days/{day}/organize     htmx: job area | plain: 303 day (?job= / ?nothing=1)
POST /trips/{trip_id}/organize                htmx: job area | plain: 303 trip (?job= / ?nothing=1)
POST /trips/{trip_id}/days/{day}/accept-all   htmx: #day-stops + OOB bar | plain: 303 (?accepted=n)
POST /suggestions/{sid}/accept|reject|undo    htmx: #day-stops + OOB bar | plain: 303 day page
GET  /suggestions/{sid}/edit                  htmx: the note row with the form | plain: day page
POST /suggestions/{sid}/edit                  htmx: #day-stops; 422 the row with errors | plain: 303
GET  /suggestions/{sid}/row                   htmx: the note row (cancel) | plain: 303 day page
A 409 `suggestion_state` returns #day-stops with the message (retargeted) or the day page, 409.
Organize errors keep their status: 404, 429 `model_busy` (D-5), 503 (model not ready).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.datastructures import FormData

from trip_journal.api.days import is_valid_day
from trip_journal.api.deps import AppState, get_state
from trip_journal.domain.organizer import EDIT_FIELDS, SuggestionView
from trip_journal.domain.views import DayView, NoteItem
from trip_journal.pages.days import accepted_message, pending_count, render_day
from trip_journal.pages.render import NOTHING_TO_ORGANIZE, render_fragment
from trip_journal.pages.trips import is_htmx, not_found_page, render_overview
from trip_journal.services.errors import (
    AppError,
    NotFoundError,
    SuggestionEditError,
    SuggestionStateError,
    to_user_facing,
)

router = APIRouter(include_in_schema=False)
StateDep = Annotated[AppState, Depends(get_state)]


def day_url(trip_id: int, day: str) -> str:
    return f"/trips/{trip_id}/days/{day}"


def find_note(view: DayView, note_id: int) -> NoteItem:
    for note in [n for s in view.stops for n in s.notes] + list(view.unlinked_notes):
        if note.note_id == note_id:
            return note
    raise NotFoundError("suggestion not found", code="suggestion_not_found")


def edit_values(s: SuggestionView) -> dict[str, str]:
    """Form values (all text) from the row's current values."""
    return {
        "category": s.category,
        "stop_id": "" if s.stop_id is None else str(s.stop_id),
        "dish": s.dish or "",
        "rating": "" if s.rating is None else str(s.rating),
        "tip": s.tip or "",
    }


def form_values(form: FormData) -> dict[str, str]:
    return {name: v for name in EDIT_FIELDS if isinstance(v := form.get(name), str)}


def form_to_raw(values: dict[str, str]) -> dict[str, Any]:
    """Form text -> the edit mapping `check_edit` expects; "" = none, digits = int."""
    raw: dict[str, Any] = dict(values)
    for name in ("stop_id", "rating"):
        if name in raw:
            text = raw[name].strip()
            raw[name] = None if text == "" else int(text) if text.isdigit() else text
    return raw


def edit_context(s: SuggestionView, values: dict[str, str], errors: dict[str, str]) -> Any:
    return {
        "suggestion_id": s.suggestion_id,
        "note_id": s.note_id,
        "values": values,
        "errors": errors,
    }


async def missing(request: Request, state: AppState, exc: NotFoundError) -> Response:
    if is_htmx(request):
        response = render_fragment(
            request, "_partials/error.html", {"error": to_user_facing(exc), "retry_url": None}
        )
        response.status_code = 404
        return response
    return await not_found_page(request, state, exc)


def day_stops(
    request: Request,
    state: AppState,
    trip_id: int,
    day: str,
    message: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """The #day-stops region plus out-of-band Accept all button and status (FA-6)."""
    view = state.trips.get_day(trip_id, day)
    context = {
        "day": view,
        "pending": pending_count(view),
        "status_message": message,
        "edit": None,
        "oob": True,
    }
    response = render_fragment(request, "_partials/day_stops.html", context)
    response.status_code = status_code
    if status_code != 200:
        response.headers["HX-Retarget"] = "#day-stops"
        response.headers["HX-Reswap"] = "outerHTML"
    return response


def note_row(
    request: Request,
    state: AppState,
    s: SuggestionView,
    edit: Any = None,
    status_code: int = 200,
) -> HTMLResponse:
    view = state.trips.get_day(s.trip_id, s.local_date)
    context = {"day": view, "note": find_note(view, s.note_id), "edit": edit}
    response = render_fragment(request, "_partials/note_item.html", context)
    response.status_code = status_code
    if status_code != 200:
        response.headers["HX-Retarget"] = f"#note-{s.note_id}"
        response.headers["HX-Reswap"] = "outerHTML"
    return response


async def state_conflict(
    request: Request, state: AppState, s: SuggestionView, exc: SuggestionStateError
) -> Response:
    message = to_user_facing(exc).message
    if is_htmx(request):
        return day_stops(request, state, s.trip_id, s.local_date, message, 409)
    extra = {"status_message": message}
    return await render_day(request, state, s.trip_id, s.local_date, extra, status_code=409)


# ----- organize runs -----


async def organize(
    request: Request, state: AppState, trip_id: int, day: str | None, back: str
) -> Response:
    try:
        started = await state.organizer.start(trip_id, day)
    except NotFoundError as exc:
        return await missing(request, state, exc)
    except AppError as exc:  # 429 model_busy, 503 model not ready, 409 job_running
        area = {"error": to_user_facing(exc), "retry_url": None, "nothing_message": None}
        if is_htmx(request):
            area.update(job=None, view=None)
            response = render_fragment(request, "_partials/organizer_job.html", area)
            response.status_code = exc.http_status
            return response
        if day is None:
            return await render_overview(request, state, trip_id, area, exc.http_status)
        return await render_day(request, state, trip_id, day, area, exc.http_status)
    if started.job is None:  # OR-RUN5
        if is_htmx(request):
            nothing = {"job": None, "error": None, "nothing_message": NOTHING_TO_ORGANIZE}
            return render_fragment(request, "_partials/organizer_job.html", nothing)
        return RedirectResponse(f"{back}?nothing=1", status_code=303)
    if is_htmx(request):
        job = state.jobs.status(started.job.job_id)
        context: dict[str, Any] = {
            "job": job,
            "view": state.job_views.get(job.kind),
            "retry_url": None,  # D-29: the Organize button stays next to the job box
            "error": None,
            "nothing_message": None,
        }
        return render_fragment(request, "_partials/organizer_job.html", context)
    return RedirectResponse(f"{back}?job={started.job.job_id}", status_code=303)


@router.post("/trips/{trip_id}/days/{day}/organize", response_model=None)
async def organize_day(request: Request, trip_id: int, day: str, state: StateDep) -> Response:
    if not is_valid_day(day):
        return await missing(request, state, NotFoundError("bad date", code="day_not_found"))
    return await organize(request, state, trip_id, day, day_url(trip_id, day))


@router.post("/trips/{trip_id}/organize", response_model=None)
async def organize_trip(request: Request, trip_id: int, state: StateDep) -> Response:
    return await organize(request, state, trip_id, None, f"/trips/{trip_id}")


# ----- review -----


@router.post("/trips/{trip_id}/days/{day}/accept-all", response_model=None)
async def accept_all(request: Request, trip_id: int, day: str, state: StateDep) -> Response:
    try:
        if not is_valid_day(day):
            raise NotFoundError("bad date", code="day_not_found")
        count = state.organizer.accept_all(trip_id, day)
    except NotFoundError as exc:
        return await missing(request, state, exc)
    if is_htmx(request):
        return day_stops(request, state, trip_id, day, accepted_message(count))
    return RedirectResponse(f"{day_url(trip_id, day)}?accepted={count}", status_code=303)


async def review(request: Request, state: AppState, sid: int, action: str) -> Response:
    try:
        s = state.organizer.get_view(sid)
    except NotFoundError as exc:
        return await missing(request, state, exc)
    try:
        if action == "accept":
            state.organizer.accept(sid)
        elif action == "reject":
            state.organizer.reject(sid)
        else:
            state.organizer.undo(sid)
    except SuggestionStateError as exc:
        return await state_conflict(request, state, s, exc)
    if is_htmx(request):
        return day_stops(request, state, s.trip_id, s.local_date)
    return RedirectResponse(day_url(s.trip_id, s.local_date), status_code=303)


@router.post("/suggestions/{sid}/accept", response_model=None)
async def accept(request: Request, sid: int, state: StateDep) -> Response:
    return await review(request, state, sid, "accept")


@router.post("/suggestions/{sid}/reject", response_model=None)
async def reject(request: Request, sid: int, state: StateDep) -> Response:
    return await review(request, state, sid, "reject")


@router.post("/suggestions/{sid}/undo", response_model=None)
async def undo(request: Request, sid: int, state: StateDep) -> Response:
    return await review(request, state, sid, "undo")


@router.get("/suggestions/{sid}/edit", response_model=None)
async def edit_form(request: Request, sid: int, state: StateDep) -> Response:
    try:
        s = state.organizer.get_view(sid)
    except NotFoundError as exc:
        return await missing(request, state, exc)
    if s.status != "pending":  # OR-ST: only a pending row can be edited
        return await state_conflict(request, state, s, SuggestionStateError(s.status))
    edit = edit_context(s, edit_values(s), {})
    if is_htmx(request):
        return note_row(request, state, s, edit)
    return await render_day(request, state, s.trip_id, s.local_date, {"edit": edit})


@router.post("/suggestions/{sid}/edit", response_model=None)
async def edit_save(request: Request, sid: int, state: StateDep) -> Response:
    try:
        s = state.organizer.get_view(sid)
    except NotFoundError as exc:
        return await missing(request, state, exc)
    values = form_values(await request.form())
    try:
        state.organizer.edit_and_accept(sid, form_to_raw(values))
    except SuggestionStateError as exc:
        return await state_conflict(request, state, s, exc)
    except SuggestionEditError as exc:  # OR-E4: the form again with one message per field
        edit = edit_context(s, values, exc.fields)
        if is_htmx(request):
            return note_row(request, state, s, edit, status_code=422)
        extra = {"edit": edit}
        return await render_day(request, state, s.trip_id, s.local_date, extra, status_code=422)
    if is_htmx(request):
        return day_stops(request, state, s.trip_id, s.local_date)
    return RedirectResponse(day_url(s.trip_id, s.local_date), status_code=303)


@router.get("/suggestions/{sid}/row", response_model=None)
async def row(request: Request, sid: int, state: StateDep) -> Response:
    try:
        s = state.organizer.get_view(sid)
    except NotFoundError as exc:
        return await missing(request, state, exc)
    if is_htmx(request):
        return note_row(request, state, s)
    return RedirectResponse(day_url(s.trip_id, s.local_date), status_code=303)
