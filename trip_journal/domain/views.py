# ADDED [PROMPT #17]: trip and day view models (IC-4). AI-assisted, Claude Opus 5.5.
"""What the trip list, overview, day page and their JSON API show."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _View(BaseModel):
    model_config = ConfigDict(frozen=True)


class DaySummary(_View):
    local_date: str
    day_number: int
    stop_count: int
    note_count: int
    photo_count: int


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
    organized: None = None  # slot U3 fills


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
