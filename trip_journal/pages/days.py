# ADDED [PROMPT #17]: day timeline page (frontend-components 2.3). AI-assisted, Claude Opus 5.5.
"""GET /trips/{trip_id}/days/{day}: 404 page for an unknown trip, unknown day or bad date."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from trip_journal.api.days import is_valid_day
from trip_journal.api.deps import AppState, get_state
from trip_journal.pages.render import render_page
from trip_journal.pages.trips import not_found_page
from trip_journal.services.errors import NotFoundError

router = APIRouter(include_in_schema=False)


@router.get("/trips/{trip_id}/days/{day}", response_class=HTMLResponse)
async def day_page(
    request: Request, trip_id: int, day: str, state: Annotated[AppState, Depends(get_state)]
) -> HTMLResponse:
    try:
        if not is_valid_day(day):
            state.trips.get_summary(trip_id)  # unknown trip wins over a bad date (TL-1)
            raise NotFoundError("bad date", code="day_not_found")  # TL-2: 404 on pages
        view = state.trips.get_day(trip_id, day)
        state.trips.set_active_trip(trip_id)  # AT-2
    except NotFoundError as exc:
        return await not_found_page(request, state, exc)
    return await render_page(request, state, "days/day.html", {"day": view, "active": "trips"})
