# ADDED [PROMPT #17]: trip and day view models (IC-4). AI-assisted, Claude Opus 5.5.
"""What the trip list, overview, day page and their JSON API show."""

from __future__ import annotations

# ADDED [PROMPT #36]: journal view field types.
from typing import Literal

from pydantic import BaseModel, ConfigDict

from trip_journal.agent.loop import ToolCallRecord
from trip_journal.domain.grounding import CitationKind
from trip_journal.domain.journal_merge import Paragraph, Tone
from trip_journal.domain.organizer import OrganizedFields, SuggestionStatus, SuggestionView


class _View(BaseModel):
    model_config = ConfigDict(frozen=True)


class DaySummary(_View):
    local_date: str
    day_number: int
    stop_count: int
    note_count: int
    photo_count: int
    # ADDED [PROMPT #25]: U3 IC-3, pending suggestions of the day (overview counts).
    pending_suggestions: int = 0


class TripSummary(_View):
    trip_id: int
    source_id: str
    title: str
    imported_at: str
    first_date: str | None
    last_date: str | None
    days: list[DaySummary]
    is_active: bool
    route_summary: str | None = None
    stop_count: int = 0
    note_count: int = 0
    photo_count: int = 0


class PhotoMeta(_View):
    photo_id: int
    local_time: str
    days_after: int
    time_utc: str
    lat: float | None
    lon: float | None
    file_name: str | None


class NoteItem(_View):
    note_id: int
    local_time: str
    days_after: int
    time_utc: str
    text: str
    # ADDED [PROMPT #25]: U3 IC-2. `organized` only for accepted / edited rows (FR-3.4);
    # `suggestion` is the row in any status, for the review controls.
    organized: OrganizedFields | None = None
    suggestion: SuggestionView | None = None
    review_status: SuggestionStatus | None = None
    suggestion_id: int | None = None


class StopTimelineItem(_View):
    stop_id: int
    name: str | None
    lat: float
    lon: float
    start_local: str
    end_local: str
    start_utc: str
    end_utc: str
    ends_next_day: bool
    end_day_label: str
    offset_label: str
    notes: list[NoteItem]
    photos: list[PhotoMeta]
    photo_count: int
    # CHANGED [PROMPT #25]: the `organized` slot moved to NoteItem (U3 D-9).


class DayView(_View):
    # ADDED [PROMPT #36]: journal badge on the day timeline.
    journal_exists: bool = False
    trip_id: int
    trip_title: str
    local_date: str
    day_number: int
    day_count: int
    heading: str
    show_offsets: bool
    stops: list[StopTimelineItem]
    unlinked_notes: list[NoteItem]
    other_photos: list[PhotoMeta]
    prev_date: str | None
    next_date: str | None


# ADDED [PROMPT #36]: grounded reading views and journal API responses.
class SentenceView(_View):
    text_html: str
    supported: bool


class ParagraphView(Paragraph):
    heading: str
    sentences: list[SentenceView]
    state: Literal["written", "not_written", "removed"]


class JournalView(_View):
    trip_id: int
    day: str
    tone: Tone | None = None
    paragraphs: list[ParagraphView] = []
    unsupported_count: int = 0
    trace: list[ToolCallRecord] = []
    model_name: str | None = None
    prompt_version: str | None = None
    generated_at: str | None = None
    message: str | None = None


class ParagraphEditView(_View):
    paragraph: ParagraphView
    unsupported_count: int


class CitationTarget(_View):
    kind: CitationKind
    id: int
    found: bool
    title: str
    time_label: str
    body: str | None = None


class NothingToRegenerate(_View):
    nothing_to_regenerate: Literal[True] = True
    message: str = "Nothing to regenerate: every paragraph is yours."


class DeletePreview(_View):
    trip_id: int
    title: str
    stop_count: int
    note_count: int
    photo_count: int
