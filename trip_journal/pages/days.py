# ADDED [PROMPT #17]: day timeline page (frontend-components 2.3). AI-assisted, Claude Opus 5.5.
"""GET /trips/{trip_id}/days/{day}: 404 page for an unknown trip, unknown day or bad date."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from trip_journal.api.days import is_valid_day
from trip_journal.api.deps import AppState, get_state
from trip_journal.domain.views import DayView
from trip_journal.pages.render import organizer_area, render_page
from trip_journal.pages.trips import not_found_page
from trip_journal.services.errors import NotFoundError

router = APIRouter(include_in_schema=False)


# ADDED [PROMPT #25]: U3 organizer bar count (OR-AA2) and the shared day page render.
def pending_count(view: DayView) -> int:
    notes = [n for s in view.stops for n in s.notes] + list(view.unlinked_notes)
    return sum(1 for n in notes if n.review_status == "pending")


def accepted_message(count: int) -> str:
    return f"{count} {'suggestion' if count == 1 else 'suggestions'} accepted"


async def render_day(
    request: Request,
    state: AppState,
    trip_id: int,
    day: str,
    extra: dict[str, Any] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Day page; `extra` may set `edit`, `status_message` and the organizer area keys."""
    try:
        if not is_valid_day(day):
            state.trips.get_summary(trip_id)  # unknown trip wins over a bad date (TL-1)
            raise NotFoundError("bad date", code="day_not_found")  # TL-2: 404 on pages
        view = state.trips.get_day(trip_id, day)
        state.trips.set_active_trip(trip_id)  # AT-2
    except NotFoundError as exc:
        return await not_found_page(request, state, exc)
    context: dict[str, Any] = {
        "day": view,
        "active": "trips",
        "pending": pending_count(view),
        "status_message": None,
        "edit": None,
        "oob": False,
        **organizer_area(state, None, False),
        **(extra or {}),
    }
    return await render_page(request, state, "days/day.html", context, status_code=status_code)


@router.get("/trips/{trip_id}/days/{day}", response_class=HTMLResponse)
async def day_page(
    request: Request,
    trip_id: int,
    day: str,
    state: Annotated[AppState, Depends(get_state)],
    job: str | None = None,
    nothing: int = 0,
    accepted: int | None = None,
) -> HTMLResponse:
    # CHANGED [PROMPT #25]: plain-form organize / accept-all results come back as query values.
    extra = organizer_area(state, job, nothing == 1)
    if accepted is not None:
        extra["status_message"] = accepted_message(accepted)
    return await render_day(request, state, trip_id, day, extra)
