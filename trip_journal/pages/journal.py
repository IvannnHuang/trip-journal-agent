# ADDED [PROMPT #36]: journal reading page, editor and citation fragments.
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from trip_journal.api.deps import AppState, get_state
from trip_journal.domain.grounding import CitationKind
from trip_journal.pages.render import render_fragment, render_page
from trip_journal.pages.trips import not_found_page
from trip_journal.services.errors import NotFoundError, to_user_facing
from trip_journal.services.jobs import JobStatus

router = APIRouter(prefix="/trips/{trip_id}", include_in_schema=False)
BASE = "/days/{day}/journal"
StateDep = Annotated[AppState, Depends(get_state)]


def finished(state: AppState, job: JobStatus) -> dict[str, Any]:
    assert job.result is not None
    journal = state.journal.get_journal(job.result["trip_id"], job.result["day"])
    return {"journal": journal, "message": job.result.get("message")}


def missing(request: Request, exc: NotFoundError) -> HTMLResponse:
    response = render_fragment(request, "_partials/error.html", {"error": to_user_facing(exc)})
    response.status_code = 404
    return response


def body_context(state: AppState, trip_id: int, day: str) -> dict[str, Any]:
    journal = state.journal.get_journal(trip_id, day)
    timeline = state.trips.get_day(trip_id, day)
    return {
        "journal": journal,
        "has_records": bool(timeline.stops or state.repos.notes.list_for_day(trip_id, day)),
    }


@router.get(BASE)
async def page(request: Request, state: StateDep, trip_id: int, day: str) -> HTMLResponse:
    try:
        context = body_context(state, trip_id, day)
        state.trips.set_active_trip(trip_id)
    except NotFoundError as exc:
        return await not_found_page(request, state, exc)
    status = await state.llm_factory(state.settings.get()).status()
    return await render_page(request, state, "journal/page.html", context, status=status)


@router.get(BASE + "/fragment")
async def fragment(request: Request, state: StateDep, trip_id: int, day: str) -> HTMLResponse:
    try:
        context = body_context(state, trip_id, day)
    except NotFoundError as exc:
        return missing(request, exc)
    return render_fragment(request, "_partials/journal_body.html", context)


@router.get(BASE + "/paragraphs/{slot}/edit", name="journal_editor")
@router.get(BASE + "/paragraphs/{slot}", name="journal_paragraph")
async def paragraph(
    request: Request, state: StateDep, trip_id: int, day: str, slot: str
) -> HTMLResponse:
    try:
        journal = state.journal.get_journal(trip_id, day)
        item = next((p for p in journal.paragraphs if p.slot == slot), None)
        if item is None:
            raise NotFoundError(code="slot_not_found" if journal.tone else "journal_not_found")
    except NotFoundError as exc:
        return missing(request, exc)
    template = (
        "journal_editor" if request.scope["route"].name == "journal_editor" else "journal_paragraph"
    )
    return render_fragment(
        request, f"_partials/{template}.html", {"journal": journal, "paragraph": item}
    )


@router.get("/citations/{kind}/{cid}")
async def citation(
    request: Request, state: StateDep, trip_id: int, kind: CitationKind, cid: int
) -> HTMLResponse:
    target = state.journal.get_citation(trip_id, kind, cid)
    return render_fragment(request, "_partials/citation_panel.html", {"citation": target})
