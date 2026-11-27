# ADDED [PROMPT #17]: day rules DD-1..DD-7 (C18). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from trip_journal.domain import days


@dataclass(frozen=True)
class Stop:
    source_id: str
    start_utc: str
    end_utc: str
    utc_offset_minutes: int = 0


@dataclass(frozen=True)
class Timed:
    source_id: str
    time_utc: str
    utc_offset_minutes: int = 0


def test_parse_and_format_round_trip() -> None:
    value = days.parse_utc("2026-05-02T08:15:00Z")
    assert value == datetime(2026, 5, 2, 8, 15, tzinfo=UTC)
    assert days.format_utc(value.replace(microsecond=999)) == "2026-05-02T08:15:00Z"


@pytest.mark.parametrize(
    ("time_utc", "offset", "day", "hm"),
    [
        ("2026-05-02T23:50:00Z", 60, "2026-05-03", "00:50"),
        ("2026-05-02T23:50:00Z", 0, "2026-05-02", "23:50"),
        ("2026-05-02T02:00:00Z", -300, "2026-05-01", "21:00"),
        ("2026-05-02T18:30:00Z", 345, "2026-05-03", "00:15"),
    ],
)
def test_local_date_and_time(time_utc: str, offset: int, day: str, hm: str) -> None:
    assert days.local_date(time_utc, offset) == day
    assert days.local_hm(time_utc, offset) == hm


def test_stop_day_uses_start_only() -> None:
    stop = Stop("s4", "2026-05-02T22:10:00Z", "2026-05-03T00:30:00Z", 60)
    assert days.stop_day(stop) == "2026-05-02"
    assert days.end_day_span(stop) == 1


@pytest.mark.parametrize(("n", "label"), [(0, ""), (-1, ""), (1, "+1 day"), (3, "+3 days")])
def test_day_span_label(n: int, label: str) -> None:
    assert days.day_span_label(n) == label


@pytest.mark.parametrize(
    ("minutes", "label"),
    [(60, "UTC+01:00"), (0, "UTC+00:00"), (-300, "UTC-05:00"), (345, "UTC+05:45")],
)
def test_offset_label(minutes: int, label: str) -> None:
    assert days.offset_label(minutes) == label


def test_show_offsets_only_when_mixed() -> None:
    a = Stop("a", "2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z", 60)
    b = Stop("b", "2026-01-01T02:00:00Z", "2026-01-01T03:00:00Z", 120)
    assert not days.show_offsets([a, a])
    assert days.show_offsets([a, b])
    assert not days.show_offsets([])


def test_day_heading() -> None:
    assert days.day_heading(1, "2026-05-02") == "Day 1 - Sat 2 May 2026"
    assert days.day_heading(12, "2026-12-31") == "Day 12 - Thu 31 Dec 2026"


def test_days_after() -> None:
    assert days.days_after("2026-05-02", "2026-05-02T23:40:00Z", 60) == 1
    assert days.days_after("2026-05-02", "2026-05-02T10:00:00Z", 60) == 0


def test_group_stops_by_day_orders_by_start_end_id() -> None:
    late = Stop("z", "2026-01-02T10:00:00Z", "2026-01-02T11:00:00Z")
    tie_b = Stop("b", "2026-01-01T10:00:00Z", "2026-01-01T11:00:00Z")
    tie_a = Stop("a", "2026-01-01T10:00:00Z", "2026-01-01T11:00:00Z")
    short = Stop("c", "2026-01-01T10:00:00Z", "2026-01-01T10:30:00Z")
    groups = days.group_stops_by_day([late, tie_b, tie_a, short])
    assert list(groups) == ["2026-01-01", "2026-01-02"]
    assert [s.source_id for s in groups["2026-01-01"]] == ["c", "a", "b"]


def test_timed_order() -> None:
    a = Timed("b", "2026-01-01T10:00:00Z")
    b = Timed("a", "2026-01-01T10:00:00Z")
    assert sorted([a, b], key=days.timed_order) == [b, a]


def test_assign_photos_latest_start_wins_and_edges_count() -> None:
    outer = Stop("outer", "2026-01-01T08:00:00Z", "2026-01-01T12:00:00Z")
    inner = Stop("inner", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z")
    photos = [
        Timed("p-start", "2026-01-01T08:00:00Z"),
        Timed("p-inner", "2026-01-01T09:30:00Z"),
        Timed("p-after-inner", "2026-01-01T11:00:00Z"),
        Timed("p-end", "2026-01-01T12:00:00Z"),
        Timed("p-out", "2026-01-01T13:00:00Z"),
        Timed("p-before", "2026-01-01T07:00:00Z"),
    ]
    placed, other = days.assign_photos([outer, inner], photos)
    assert [p.source_id for p in placed["outer"]] == ["p-start", "p-after-inner", "p-end"]
    assert [p.source_id for p in placed["inner"]] == ["p-inner"]
    assert [p.source_id for p in other] == ["p-before", "p-out"]


def test_assign_photos_same_start_latest_id_wins() -> None:
    a = Stop("a", "2026-01-01T08:00:00Z", "2026-01-01T09:00:00Z")
    b = Stop("b", "2026-01-01T08:00:00Z", "2026-01-01T09:00:00Z")
    placed, _ = days.assign_photos([b, a], [Timed("p", "2026-01-01T08:30:00Z")])
    assert list(placed) == ["b"]


def test_build_day_index_and_neighbours() -> None:
    stop = Stop("s", "2026-01-02T10:00:00Z", "2026-01-02T11:00:00Z")
    note = Timed("n", "2026-01-04T10:00:00Z")
    in_stop = Timed("p1", "2026-01-02T10:30:00Z")
    loose = Timed("p2", "2026-01-01T10:00:00Z")
    index = days.build_day_index([stop], [note], [in_stop, loose])
    assert index == ["2026-01-01", "2026-01-02", "2026-01-04"]
    assert days.neighbours(index, "2026-01-01") == (None, "2026-01-02")
    assert days.neighbours(index, "2026-01-02") == ("2026-01-01", "2026-01-04")
    assert days.neighbours(index, "2026-01-04") == ("2026-01-02", None)
