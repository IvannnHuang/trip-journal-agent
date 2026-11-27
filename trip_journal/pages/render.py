# ADDED [PROMPT #13]: shared page rendering with the model banner (LC-10, ST-1, ST-4).
# AI-assisted, Claude Opus 5.5.
"""Full pages run a fresh model-status check for the banner; fragments never do."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from trip_journal.agent.llm import ModelStatus
from trip_journal.api.deps import AppState
from trip_journal.config import PACKAGE_DIR
from trip_journal.domain.grounding import CITATION_RE
from trip_journal.services.errors import status_message

templates = Jinja2Templates(directory=PACKAGE_DIR / "pages" / "templates")


def cite_href(kind: str, record_id: int) -> str:
    """Record page URL; the pages themselves are added by U2."""
    return f"/{kind}s/{int(record_id)}"


def link_citations(text: str) -> Markup:
    """Escape `text`, then turn each `[kind:N]` into a citation link (FR-8.2)."""
    out: list[str] = []
    last = 0
    for match in CITATION_RE.finditer(text):
        out.append(str(escape(text[last : match.start()])))
        kind, record_id = match.group(1), int(match.group(2))
        out.append(
            f'<a class="cite" href="{cite_href(kind, record_id)}" '
            f'data-testid="cite-{kind}-{record_id}">[{kind}:{record_id}]</a>'
        )
        last = match.end()
    out.append(str(escape(text[last:])))
    return Markup("".join(out))


templates.env.filters["link_citations"] = link_citations
templates.env.globals["cite_href"] = cite_href


async def render_page(
    request: Request,
    state: AppState,
    name: str,
    context: dict[str, Any],
    status: ModelStatus | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Render a full page; `status` may be passed in when the page already checked it."""
    current = status or await state.settings.model_status()
    # CHANGED [PROMPT #17]: every full page shows the active trip (AT-3, D-8).
    full = {
        "banner": status_message(current),
        "model_status": current,
        "active_trip": state.trips.get_active_trip(),
        **context,
    }
    return templates.TemplateResponse(request, name, full, status_code=status_code)


def render_fragment(request: Request, name: str, context: dict[str, Any]) -> HTMLResponse:
    return templates.TemplateResponse(request, name, context)
