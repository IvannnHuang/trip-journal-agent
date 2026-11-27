# ADDED [PROMPT #17]: trip and day view models (IC-4). AI-assisted, Claude Opus 5.5.
"""What the trip list, overview, day page and their JSON API show."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

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


class DeletePreview(_View):
    trip_id: int
    title: str
    stop_count: int
    note_count: int
    photo_count: int
