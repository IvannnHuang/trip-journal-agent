# ADDED [PROMPT #17]: import properties P-I1..P-I5 (business-rules §6, PBT-02, PBT-03).
# AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import sqlite3

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.fixtures import make_services
from tests.strategies import (
    TripDict,
    encode,
    trip_files,
    with_end_before_start,
    with_many_issues,
    with_unknown_key,
)
from trip_journal.data.db import connect, init_schema
from trip_journal.domain.import_schema import MAX_ISSUES, TripFile, TripFileError, parse_trip_file
from trip_journal.services.errors import ImportValidationError

MAX = 20 * 1024 * 1024


def refused(data: TripDict) -> TripFileError:
    with pytest.raises(TripFileError) as info:
        parse_trip_file(encode(data), MAX)
    return info.value


@given(trip_files())
def test_p_i1_round_trip(data: TripDict) -> None:
    """PBT-02: a parsed file written back as JSON parses to the same model."""
    trip = parse_trip_file(encode(data), MAX)
    again = parse_trip_file(trip.model_dump_json(exclude_none=True).encode(), MAX)
    assert again == trip


def _fresh() -> sqlite3.Connection:
    conn = connect(":memory:")
    init_schema(conn)
    return conn


@given(trip_files(max_stops=5, max_notes=6, max_photos=6))
def test_p_i2_import_then_read_back(data: TripDict) -> None:
    """Advisory: every record is stored exactly as the file says (fresh DB per example)."""
    trip: TripFile = parse_trip_file(encode(data), MAX)
    conn = _fresh()
    try:
        services = make_services(conn)
        summary = services.imports.import_trip(encode(data))
        stored = services.repos.trips.get(summary.trip_id)
        assert stored is not None
        assert (stored.source_id, stored.title) == (trip.trip.trip_id, trip.trip.title)
        assert stored.route_summary == trip.route_summary
        stops = {s.source_id: s for s in services.repos.stops.list_for_trip(summary.trip_id)}
        assert set(stops) == {s.id for s in trip.stops}
        for s in trip.stops:
            row = stops[s.id]
            assert (row.name, row.start_utc, row.end_utc) == (s.name, s.start_utc, s.end_utc)
            assert (row.utc_offset_minutes, row.lat, row.lon) == (
                s.utc_offset_minutes,
                s.lat,
                s.lon,
            )
        by_row = {row.id: sid for sid, row in stops.items()}
        notes = {n.source_id: n for n in services.repos.notes.list_for_trip(summary.trip_id)}
        assert set(notes) == {n.id for n in trip.notes}
        for n in trip.notes:
            row_n = notes[n.id]
            assert (row_n.text, row_n.time_utc) == (n.text, n.time_utc)
            assert (by_row[row_n.stop_id] if row_n.stop_id else None) == n.stop_id
        photos = {p.source_id: p for p in services.repos.photos.list_for_trip(summary.trip_id)}
        assert set(photos) == {p.id for p in trip.photos}
        for p in trip.photos:
            row_p = photos[p.id]
            assert (row_p.time_utc, row_p.lat, row_p.lon, row_p.file_name) == (
                p.time_utc,
                p.lat,
                p.lon,
                p.file_name,
            )
    finally:
        conn.close()


@given(st.data())
def test_p_i3_unknown_key_is_reported_where_it_is(data: st.DataObject) -> None:
    mutated, location = data.draw(trip_files().flatmap(with_unknown_key))
    issues = refused(mutated).issues
    assert any(i.location == location for i in issues)
    assert all(i.location.endswith(location.rsplit(".", 1)[-1]) for i in issues)


@given(trip_files().flatmap(with_end_before_start))
def test_p_i4_end_before_start_is_refused(case: tuple[TripDict, int]) -> None:
    mutated, i = case
    issues = refused(mutated).issues
    assert [x.location for x in issues] == [f"stops[{i}].end_utc"]
    conn = _fresh()
    try:
        services = make_services(conn)
        with pytest.raises(ImportValidationError):
            services.imports.import_trip(encode(mutated))
        assert conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0] == 0
    finally:
        conn.close()


@given(trip_files().flatmap(with_many_issues))
def test_p_i5_issue_cap(case: tuple[TripDict, int]) -> None:
    mutated, k = case
    error = refused(mutated)
    assert len(error.issues) == min(k, MAX_ISSUES)
    assert len(error.issues) + error.more == k
