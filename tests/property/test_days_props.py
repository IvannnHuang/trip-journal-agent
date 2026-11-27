# ADDED [PROMPT #17]: day-grouping properties P-D1..P-D8 (business-rules §6, DD-1..DD-6).
# AI-assisted, Claude Opus 5.5.
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from tests.fixtures import make_services
from tests.strategies import TripDict, encode, offsets, trip_files, utc_seconds, utc_text
from trip_journal.data.db import connect, init_schema
from trip_journal.domain import days


@dataclass(frozen=True)
class Stop:
    source_id: str
    start_utc: str
    end_utc: str
    utc_offset_minutes: int


@dataclass(frozen=True)
class Timed:
    source_id: str
    time_utc: str
    utc_offset_minutes: int


def stops_of(data: TripDict) -> list[Stop]:
    return [
        Stop(s["id"], s["start_utc"], s["end_utc"], s["utc_offset_minutes"]) for s in data["stops"]
    ]


def timed_of(records: list[TripDict]) -> list[Timed]:
    return [Timed(r["id"], r["time_utc"], r["utc_offset_minutes"]) for r in records]


@given(trip_files())
def test_p_d1_to_p_d3_grouping(data: TripDict) -> None:
    stops = stops_of(data)
    groups = days.group_stops_by_day(stops)
    flat = [s for group in groups.values() for s in group]
    assert sorted(flat, key=lambda s: s.source_id) == sorted(stops, key=lambda s: s.source_id)
    assert list(groups) == sorted(groups)
    for day, group in groups.items():
        assert all(days.local_date(s.start_utc, s.utc_offset_minutes) == day for s in group)
        assert group == sorted(group, key=days.stop_order)


_BEFORE_2100 = 4_102_358_400 - 2 * 86_400  # keep +24 h and offsets inside year 2099


@given(utc_seconds.filter(lambda s: s < _BEFORE_2100), offsets, offsets)
def test_p_d4_day_arithmetic(seconds: int, a: int, b: int) -> None:
    t = utc_text(seconds)
    later = utc_text(seconds + 86_400)
    today = date.fromisoformat(days.local_date(t, a))
    assert date.fromisoformat(days.local_date(later, a)) == today + timedelta(days=1)
    low, high = min(a, b), max(a, b)
    assert days.local_date(t, low) <= days.local_date(t, high)


@given(trip_files())
def test_p_d5_day_index(data: TripDict) -> None:
    stops = stops_of(data)
    unlinked = timed_of([n for n in data["notes"] if "stop_id" not in n])
    index = days.build_day_index(stops, unlinked, timed_of(data["photos"]))
    assert index == sorted(set(index))
    for i, day in enumerate(index):
        prev_day, next_day = days.neighbours(index, day)
        assert prev_day == (index[i - 1] if i > 0 else None)
        if next_day is not None:
            assert days.neighbours(index, next_day)[0] == day


@given(trip_files())
def test_p_d7_photo_placement(data: TripDict) -> None:
    stops = stops_of(data)
    photos = timed_of(data["photos"])
    placed, other = days.assign_photos(stops, photos)
    by_id = {s.source_id: s for s in stops}
    seen = [p.source_id for group in placed.values() for p in group] + [p.source_id for p in other]
    assert sorted(seen) == sorted(p.source_id for p in photos)  # each photo exactly once
    for sid, group in placed.items():
        stop = by_id[sid]
        for p in group:
            assert stop.start_utc <= p.time_utc <= stop.end_utc
            holders = [s for s in stops if s.start_utc <= p.time_utc <= s.end_utc]
            assert (stop.start_utc, stop.source_id) == max(
                (s.start_utc, s.source_id) for s in holders
            )
    for p in other:
        assert not any(s.start_utc <= p.time_utc <= s.end_utc for s in stops)


@given(trip_files(max_stops=5, max_notes=6, max_photos=6))
def test_p_d6_and_p_d8_through_the_service(data: TripDict) -> None:
    """P-D6: a linked note shows on its stop's day. P-D8: day counts add up to trip totals."""
    conn = connect(":memory:")
    init_schema(conn)
    try:
        services = make_services(conn)
        summary = services.imports.import_trip(encode(data))
        note_days: dict[str, str] = {}
        stop_days: dict[str, str] = {}
        rows = {r.id: r.source_id for r in services.repos.notes.list_for_trip(summary.trip_id)}
        stop_rows = {r.id: r.source_id for r in services.repos.stops.list_for_trip(summary.trip_id)}
        totals = [0, 0, 0]
        for d in summary.days:
            view = services.trips.get_day(summary.trip_id, d.local_date)
            notes = sum(len(s.notes) for s in view.stops) + len(view.unlinked_notes)
            photos = sum(len(s.photos) for s in view.stops) + len(view.other_photos)
            assert (d.stop_count, d.note_count, d.photo_count) == (len(view.stops), notes, photos)
            totals = [totals[0] + len(view.stops), totals[1] + notes, totals[2] + photos]
            for s in view.stops:
                stop_days[stop_rows[s.stop_id]] = d.local_date
                for n in s.notes:
                    note_days[rows[n.note_id]] = d.local_date
            for n in view.unlinked_notes:
                note_days[rows[n.note_id]] = d.local_date
        assert totals == [summary.stop_count, summary.note_count, summary.photo_count]
        assert totals == [len(data["stops"]), len(data["notes"]), len(data["photos"])]
        for n in data["notes"]:
            if "stop_id" in n:
                assert note_days[n["id"]] == stop_days[n["stop_id"]]
    finally:
        conn.close()


@given(st.lists(offsets, min_size=1, max_size=4))
def test_show_offsets_iff_mixed(values: list[int]) -> None:
    stops = [
        Stop(str(i), "2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z", v)
        for i, v in enumerate(values)
    ]
    assert days.show_offsets(stops) == (len(set(values)) > 1)
