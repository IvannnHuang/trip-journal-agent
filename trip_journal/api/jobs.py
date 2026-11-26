# ADDED [PROMPT #13]: job status JSON API (JB-7). AI-assisted, Claude Opus 5.5.
"""GET /api/jobs/{job_id}."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from trip_journal.api.deps import AppState, get_state
from trip_journal.services.errors import NotFoundError, to_user_facing
from trip_journal.services.jobs import JobStatus

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=None)
async def job_status(
    job_id: str, state: Annotated[AppState, Depends(get_state)]
) -> JobStatus | JSONResponse:
    try:
        return state.jobs.status(job_id)
    except NotFoundError as exc:
        return JSONResponse(status_code=404, content=to_user_facing(exc).model_dump())
