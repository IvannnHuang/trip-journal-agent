# ADDED [PROMPT #17]: day derivation rules DD-1..DD-7 (C18). AI-assisted, Claude Opus 5.5.
"""Pure day rules: which local day a record is on, order within a day, photo placement.

Every record carries its own UTC offset; `home_timezone` is never used (DD-2).
UTC times are canonical text `YYYY-MM-DDTHH:MM:SSZ`, which sorts like the times it holds.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class StopLike(Protocol):
    @property
    def source_id(self) -> str: ...
    @property
    def start_utc(self) -> str: ...
    @property
    def end_utc(self) -> str: ...
    @property
    def utc_offset_minutes(self) -> int: ...


class TimedLike(Protocol):
    @property
    def source_id(self) -> str: ...
    @property
    def time_utc(self) -> str: ...
    @property
    def utc_offset_minutes(self) -> int: ...


def parse_utc(text: str) -> datetime:
    """Canonical UTC text -> aware datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def format_utc(value: datetime) -> str:
    """Aware datetime -> canonical UTC text; fractional seconds are cut (FA-2)."""
    return value.astimezone(UTC).strftime(UTC_FORMAT)


def local_datetime(time_utc: str, utc_offset_minutes: int) -> datetime:
    """UTC text + the record's own offset -> naive local datetime (DD-2)."""
    return (parse_utc(time_utc) + timedelta(minutes=utc_offset_minutes)).replace(tzinfo=None)


def local_date(time_utc: str, utc_offset_minutes: int) -> str:
    """The only implementation of "which local day" (IC-3): `YYYY-MM-DD`."""
    return local_datetime(time_utc, utc_offset_minutes).date().isoformat()


def local_hm(time_utc: str, utc_offset_minutes: int) -> str:
    return local_datetime(time_utc, utc_offset_minutes).strftime("%H:%M")


def stop_day(stop: StopLike) -> str:
    """DD-1: a stop's day is the local date of its start; the end never moves it."""
    return local_date(stop.start_utc, stop.utc_offset_minutes)


def stop_order(stop: StopLike) -> tuple[str, str, str]:
    """DD-4 order of stops within a day."""
    return (stop.start_utc, stop.end_utc, stop.source_id)


def timed_order(record: TimedLike) -> tuple[str, str]:
    """DD-4 order of notes and photos."""
    return (record.time_utc, record.source_id)


def days_after(day: str, time_utc: str, utc_offset_minutes: int) -> int:
    """How many days a local time lies after `day` (0 on the same day)."""
    return (
        date.fromisoformat(local_date(time_utc, utc_offset_minutes)) - date.fromisoformat(day)
    ).days


def end_day_span(stop: StopLike) -> int:
    """DD-7: days between the stop's start day and its local end date."""
    return days_after(stop_day(stop), stop.end_utc, stop.utc_offset_minutes)


def day_span_label(days: int) -> str:
    """`+1 day` / `+N days`; empty when on the same day."""
    if days <= 0:
        return ""
    return "+1 day" if days == 1 else f"+{days} days"


def offset_label(utc_offset_minutes: int) -> str:
    """`UTC+01:00`, `UTC-05:00`, `UTC+05:45` (TL-3)."""
    sign = "-" if utc_offset_minutes < 0 else "+"
    hours, minutes = divmod(abs(utc_offset_minutes), 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def show_offsets(stops: Iterable[StopLike]) -> bool:
    """TL-3: show offset labels only when the day's stops use more than one offset."""
    return len({s.utc_offset_minutes for s in stops}) > 1


def day_heading(day_number: int, day: str) -> str:
    """`Day 1 - Sat 2 May 2026` with fixed English names (FA-4)."""
    d = date.fromisoformat(day)
    return f"Day {day_number} - {_WEEKDAYS[d.weekday()]} {d.day} {_MONTHS[d.month - 1]} {d.year}"


def group_stops_by_day[S: StopLike](stops: Iterable[S]) -> dict[str, list[S]]:
    """DD-1 and DD-4: day -> stops in order; keys in date order."""
    groups: dict[str, list[S]] = {}
    for stop in stops:
        groups.setdefault(stop_day(stop), []).append(stop)
    return {day: sorted(groups[day], key=stop_order) for day in sorted(groups)}


def assign_photos[S: StopLike, T: TimedLike](
    stops: Sequence[S], photos: Iterable[T]
) -> tuple[dict[str, list[T]], list[T]]:
    """DD-6: place each photo in at most one stop.

    A stop holds a photo when `start_utc <= time_utc <= end_utc`. With several such stops,
    the latest start wins (ties: latest `source_id`). Returns (stop source_id -> photos,
    other photos), each list in DD-4 order.
    """
    ordered = sorted(stops, key=lambda s: (s.start_utc, s.source_id))
    starts = [s.start_utc for s in ordered]
    # max_end[i] = latest end among ordered[0..i], so the backward scan can stop early.
    max_end: list[str] = []
    for s in ordered:
        max_end.append(max(s.end_utc, max_end[-1]) if max_end else s.end_utc)
    placed: dict[str, list[T]] = {}
    other: list[T] = []
    for photo in sorted(photos, key=timed_order):
        t = photo.time_utc
        i = bisect.bisect_right(starts, t) - 1
        owner: S | None = None
        while i >= 0 and max_end[i] >= t:
            if ordered[i].end_utc >= t:
                owner = ordered[i]
                break
            i -= 1
        if owner is None:
            other.append(photo)
        else:
            placed.setdefault(owner.source_id, []).append(photo)
    return placed, other


def build_day_index(
    stops: Sequence[StopLike], unlinked_notes: Iterable[TimedLike], photos: Iterable[TimedLike]
) -> list[str]:
    """DD-5: sorted unique days of stops, notes without a stop, and photos in no stop."""
    days = {stop_day(s) for s in stops}
    days.update(local_date(n.time_utc, n.utc_offset_minutes) for n in unlinked_notes)
    _, other = assign_photos(stops, photos)
    days.update(local_date(p.time_utc, p.utc_offset_minutes) for p in other)
    return sorted(days)


def neighbours(index: Sequence[str], day: str) -> tuple[str | None, str | None]:
    """TL-7: (previous day, next day) in the day index; None at either end."""
    pos = index.index(day)
    prev_day = index[pos - 1] if pos > 0 else None
    next_day = index[pos + 1] if pos + 1 < len(index) else None
    return prev_day, next_day
