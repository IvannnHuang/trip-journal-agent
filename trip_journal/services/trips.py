# ADDED [PROMPT #17]: TripService (C04): trip list, day view, active trip, delete.
# AI-assisted, Claude Opus 5.5.
"""Read trips and days, keep the active trip, delete a trip (AT-1..AT-5, TL-1..TL-7, DL-1..DL-4).

Every read takes one trip id (AT-5). Nothing here calls the model, PlaceLookup or the
JobRunner's work (U2-NFR-P.7); delete only reads `JobRunner.running` (U2-NFR-R.5).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from trip_journal.data.repositories import NoteRow, PhotoRow, Repositories, StopRow, TripRow
from trip_journal.domain.days import (
    assign_photos,
    build_day_index,
    day_heading,
    day_span_label,
    days_after,
    end_day_span,
    group_stops_by_day,
    local_date,
    local_hm,
    neighbours,
    offset_label,
    show_offsets,
    timed_order,
)
from trip_journal.domain.views import (
    DaySummary,
    DayView,
    DeletePreview,
    NoteItem,
    PhotoMeta,
    StopTimelineItem,
    TripSummary,
)
from trip_journal.logs import kv
from trip_journal.services.errors import JobRunningError, NotFoundError
from trip_journal.services.jobs import JobRunner

log = logging.getLogger(__name__)

ACTIVE_TRIP_KEY = "active_trip_id"


@dataclass(frozen=True)
class _TripData:
    """All records of one trip, read with one query per record type (N-6)."""

    stops: list[StopRow]
    notes: list[NoteRow]
    photos: list[PhotoRow]
    index: list[str]
    placed: dict[str, list[PhotoRow]]
    other: list[PhotoRow]


class TripService:
    def __init__(self, repos: Repositories, jobs: JobRunner) -> None:
        self.repos = repos
        self.jobs = jobs

    # ----- active trip (AT-1..AT-4) -----

    def get_active_trip_id(self) -> int | None:
        """The stored trip if it exists; else the newest import (stored); else None (AT-4)."""
        raw = self.repos.settings.get_all().get(ACTIVE_TRIP_KEY)
        if raw is not None and raw.isdigit() and self.repos.trips.get(int(raw)) is not None:
            return int(raw)
        trips = self.repos.trips.list()
        if not trips:
            return None
        self.set_active_trip(trips[0].id)
        return trips[0].id

    def set_active_trip(self, trip_id: int) -> None:
        self._trip(trip_id)
        self.repos.settings.set(ACTIVE_TRIP_KEY, str(trip_id))

    def get_active_trip(self) -> TripRow | None:
        trip_id = self.get_active_trip_id()
        return self.repos.trips.get(trip_id) if trip_id is not None else None

    # ----- summaries -----

    def list_trips(self) -> list[TripSummary]:
        active = self.get_active_trip_id()
        return [self._summary(t, active) for t in self.repos.trips.list()]

    def get_summary(self, trip_id: int) -> TripSummary:
        trip = self._trip(trip_id)
        return self._summary(trip, self.get_active_trip_id())

    # ----- day view (TL-1..TL-7) -----

    def get_day(self, trip_id: int, day: str) -> DayView:
        trip = self._trip(trip_id)
        data = self._load(trip_id)
        if day not in data.index:
            raise NotFoundError("day not found", code="day_not_found")
        day_stops = group_stops_by_day(data.stops).get(day, [])
        notes_by_stop: dict[int, list[NoteRow]] = {}
        unlinked: list[NoteRow] = []
        for note in data.notes:
            if note.stop_id is None:
                if note.local_date == day:
                    unlinked.append(note)
            else:
                notes_by_stop.setdefault(note.stop_id, []).append(note)
        items = [
            self._stop_item(
                day,
                stop,
                sorted(notes_by_stop.get(stop.id, []), key=timed_order),
                data.placed.get(stop.source_id, []),
            )
            for stop in day_stops
        ]
        other = [p for p in data.other if local_date(p.time_utc, p.utc_offset_minutes) == day]
        prev_day, next_day = neighbours(data.index, day)
        number = data.index.index(day) + 1
        return DayView(
            trip_id=trip.id,
            trip_title=trip.title,
            local_date=day,
            day_number=number,
            day_count=len(data.index),
            heading=day_heading(number, day),
            show_offsets=show_offsets(day_stops),
            stops=items,
            unlinked_notes=[_note_item(day, n) for n in sorted(unlinked, key=timed_order)],
            other_photos=[_photo_meta(day, p) for p in other],
            prev_date=prev_day,
            next_date=next_day,
        )

    # ----- delete (DL-1..DL-4, R.5) -----

    def get_delete_preview(self, trip_id: int) -> DeletePreview:
        trip = self._trip(trip_id)
        stops, notes, photos = self.repos.trips.counts(trip_id)
        return DeletePreview(
            trip_id=trip.id,
            title=trip.title,
            stop_count=stops,
            note_count=notes,
            photo_count=photos,
        )

    def ensure_no_job_running(self) -> None:
        """R.5: refuse a delete while any job runs; nothing is deleted."""
        if self.jobs.running is not None:
            log.info(kv("trip.delete", result="job_running"))
            raise JobRunningError("a job is running")

    def delete_trip(self, trip_id: int) -> None:
        self.ensure_no_job_running()
        trip = self._trip(trip_id)
        stops, notes, photos = self.repos.trips.counts(trip_id)
        self.repos.trips.delete(trip_id)  # one statement; the cascade removes the rest (DL-4)
        self.get_active_trip_id()  # AT-4: falls back to the newest remaining trip
        log.info(
            kv(
                "trip.delete",
                result="ok",
                trip=trip.id,
                source_id=trip.source_id,
                stops=stops,
                notes=notes,
                photos=photos,
            )
        )

    # ----- helpers -----

    def _trip(self, trip_id: int) -> TripRow:
        trip = self.repos.trips.get(trip_id)
        if trip is None:
            raise NotFoundError("trip not found", code="trip_not_found")
        return trip

    def _load(self, trip_id: int) -> _TripData:
        stops = self.repos.stops.list_for_trip(trip_id)
        notes = self.repos.notes.list_for_trip(trip_id)
        photos = self.repos.photos.list_for_trip(trip_id)
        unlinked = [n for n in notes if n.stop_id is None]
        placed, other = assign_photos(stops, photos)
        return _TripData(
            stops=stops,
            notes=notes,
            photos=photos,
            index=build_day_index(stops, unlinked, photos),
            placed=placed,
            other=other,
        )

    def _summary(self, trip: TripRow, active_id: int | None) -> TripSummary:
        data = self._load(trip.id)
        stop_days = {s.source_id: s.local_date for s in data.stops}
        counts: dict[str, list[int]] = {day: [0, 0, 0] for day in data.index}
        for stop in data.stops:
            counts[stop.local_date][0] += 1
        for note in data.notes:
            if note.local_date in counts:  # always true for rows written by ImportService
                counts[note.local_date][1] += 1
        for source_id, photos in data.placed.items():
            counts[stop_days[source_id]][2] += len(photos)
        for photo in data.other:
            counts[local_date(photo.time_utc, photo.utc_offset_minutes)][2] += 1
        days = [
            DaySummary(
                local_date=day,
                day_number=i + 1,
                stop_count=c[0],
                note_count=c[1],
                photo_count=c[2],
            )
            for i, (day, c) in enumerate(counts.items())
        ]
        return TripSummary(
            trip_id=trip.id,
            source_id=trip.source_id,
            title=trip.title,
            imported_at=trip.imported_at,
            first_date=data.index[0] if data.index else None,
            last_date=data.index[-1] if data.index else None,
            days=days,
            is_active=trip.id == active_id,
            route_summary=trip.route_summary,
            stop_count=len(data.stops),
            note_count=len(data.notes),
            photo_count=len(data.photos),
        )

    def _stop_item(
        self, day: str, stop: StopRow, notes: list[NoteRow], photos: list[PhotoRow]
    ) -> StopTimelineItem:
        span = end_day_span(stop)
        return StopTimelineItem(
            stop_id=stop.id,
            name=stop.name,
            lat=stop.lat,
            lon=stop.lon,
            start_local=local_hm(stop.start_utc, stop.utc_offset_minutes),
            end_local=local_hm(stop.end_utc, stop.utc_offset_minutes),
            start_utc=stop.start_utc,
            end_utc=stop.end_utc,
            ends_next_day=span > 0,
            end_day_label=day_span_label(span),
            offset_label=offset_label(stop.utc_offset_minutes),
            notes=[_note_item(day, n) for n in notes],
            photos=[_photo_meta(day, p) for p in photos],
            photo_count=len(photos),
        )


def _note_item(day: str, note: NoteRow) -> NoteItem:
    return NoteItem(
        note_id=note.id,
        local_time=local_hm(note.time_utc, note.utc_offset_minutes),
        days_after=days_after(day, note.time_utc, note.utc_offset_minutes),
        time_utc=note.time_utc,
        text=note.text,
    )


def _photo_meta(day: str, photo: PhotoRow) -> PhotoMeta:
    return PhotoMeta(
        photo_id=photo.id,
        local_time=local_hm(photo.time_utc, photo.utc_offset_minutes),
        days_after=days_after(day, photo.time_utc, photo.utc_offset_minutes),
        time_utc=photo.time_utc,
        lat=photo.lat,
        lon=photo.lon,
        file_name=photo.file_name,
    )
