# ADDED [PROMPT #17]: day view JSON API (TL-1, TL-2). AI-assisted, Claude Opus 5.5.
"""GET /api/trips/{trip_id}/days/{day}."""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from trip_journal.api.deps import AppState, get_state
from trip_journal.api.trips import error_response
from trip_journal.domain.views import DayView
from trip_journal.services.errors import NotFoundError

router = APIRouter(prefix="/api/trips", tags=["days"])
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def is_valid_day(text: str) -> bool:
    """A real calendar date written `YYYY-MM-DD` (TL-2)."""
    if not _DATE_RE.fullmatch(text):
        return False
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


@router.get("/{trip_id}/days/{day}", response_model=None)
async def get_day(
    trip_id: int, day: str, state: Annotated[AppState, Depends(get_state)]
) -> DayView | JSONResponse:
    if not is_valid_day(day):
        # TL-2: a malformed date is 422 in the API (404 on pages).
        return JSONResponse(
            status_code=422,
            content={
                "code": "invalid_date",
                "message": "The date must be a real date written YYYY-MM-DD.",
                "action": "Use a date from the trip's day list.",
                "trace": [],
            },
        )
    try:
        return state.trips.get_day(trip_id, day)
    except NotFoundError as exc:
        return error_response(exc)
