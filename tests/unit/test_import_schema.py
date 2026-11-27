# ADDED [PROMPT #17]: trip file validation IM-1..IM-14 (C17). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from tests.fixtures import minimal_trip_bytes
from trip_journal.domain.import_schema import (
    MAX_ISSUES,
    ImportIssue,
    TripFileError,
    format_location,
    parse_trip_file,
)

MAX = 20 * 1024 * 1024


def sample() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(minimal_trip_bytes())
    return data


def issues_of(data: dict[str, Any] | bytes) -> list[ImportIssue]:
    raw = data if isinstance(data, bytes) else json.dumps(data).encode()
    with pytest.raises(TripFileError) as info:
        parse_trip_file(raw, MAX)
    return info.value.issues


def test_sample_parses() -> None:
    trip = parse_trip_file(minimal_trip_bytes(), MAX)
    assert trip.trip.trip_id == "minimal-lisbon-2026-05"
    assert (len(trip.stops), len(trip.notes), len(trip.photos)) == (4, 8, 10)
    assert trip.stops[1].name is None
    assert trip.photos[7].lat is None


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (b"", "The file is empty."),
        (b"\xff\xfe{}", "The file is not UTF-8 text. Only the JSON trip format is supported."),
        (
            b'  <?xml version="1.0"?><gpx/>',
            "This looks like an XML/GPX file. Only the JSON trip format is supported.",
        ),
        (b'{"trip": ', "The file is not valid JSON (line 1, column 10)."),
        (b"[1, 2]", "The file must contain one JSON object."),
    ],
)
def test_file_level_refusals(raw: bytes, message: str) -> None:
    assert issues_of(raw) == [ImportIssue("file", message)]


def test_too_large_is_checked_before_decoding() -> None:
    with pytest.raises(TripFileError) as big:
        parse_trip_file(b" " * (MAX + 1), MAX)
    assert big.value.issues == [ImportIssue("file", "The file is larger than 20 MB.")]


def test_utf8_bom_is_accepted() -> None:
    trip = parse_trip_file("﻿".encode() + minimal_trip_bytes(), MAX)
    assert trip.trip.title == "A day in Lisbon"


def test_missing_top_level_and_unknown_key() -> None:
    assert issues_of({"extra": 1}) == [
        ImportIssue("extra", "unknown field 'extra'"),
        ImportIssue("trip", "required field is missing"),
        ImportIssue("stops", "required field is missing"),
        ImportIssue("notes", "required field is missing"),
    ]


def test_stops_must_be_a_non_empty_list() -> None:
    data = sample()
    data["stops"] = []
    data["notes"] = [n for n in data["notes"] if "stop_id" not in n]
    assert issues_of(data) == [ImportIssue("stops", "must have at least 1 item")]
    data["stops"] = {"a": 1}
    assert issues_of(data) == [ImportIssue("stops", "must be a list")]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("start_utc", "2026-05-02T08:15:00", "must be a UTC time ending in Z"),
        ("start_utc", "yesterday", "must be a UTC time ending in Z"),
        (
            "start_utc",
            "2026-05-02T09:15:00+01:00",
            "must be in UTC (Z or +00:00), the local offset goes in utc_offset_minutes",
        ),
        ("utc_offset_minutes", 7, "must be between -720 and 840 and a multiple of 15"),
        ("utc_offset_minutes", 900, "must be between -720 and 840 and a multiple of 15"),
        ("utc_offset_minutes", "60", "must be an integer"),
        ("lat", 91, "must be between -90 and 90"),
        ("lon", -181.5, "must be between -180 and 180"),
        ("lat", "38.7", "must be a number"),
        ("id", " s1", "must not start or end with a space"),
        ("id", "x" * 101, "must be 1 to 100 characters"),
        ("name", "n" * 201, "must be 1 to 200 characters"),
        ("surprise", True, "unknown field 'surprise'"),
    ],
)
def test_stop_field_messages(field: str, value: object, message: str) -> None:
    data = sample()
    data["stops"][0][field] = value
    found = issues_of(data)
    assert found[0] == ImportIssue(f"stops[0].{field}", message)


def test_required_field_and_note_text() -> None:
    data = sample()
    del data["notes"][2]["time_utc"]
    data["notes"][3]["text"] = "   "
    assert issues_of(data) == [
        ImportIssue("notes[2].time_utc", "required field is missing"),
        ImportIssue("notes[3].text", "must be 1 to 10000 characters"),
    ]


def test_nan_is_refused() -> None:
    raw = minimal_trip_bytes().replace(b'"lat": 38.7107', b'"lat": NaN', 1)
    found = issues_of(raw)
    assert found[0].location == "stops[0].lat"
    assert found[0].message == "must be a finite number"


def test_cross_record_rules() -> None:
    data = sample()
    data["stops"][2]["id"] = "s1"
    data["stops"][3]["end_utc"] = "2026-05-02T22:00:00Z"
    data["notes"][0]["stop_id"] = "nope"
    data["photos"][0].pop("lon")
    assert issues_of(data) == [
        ImportIssue("stops[2].id", "duplicate id 's1' (first at stops[0])"),
        ImportIssue(
            "stops[3].end_utc",
            "end_utc (2026-05-02T22:00:00Z) is before start_utc (2026-05-02T22:10:00Z)",
        ),
        ImportIssue("notes[0].stop_id", "no stop with id 'nope'"),
        # s3 was renamed, so its notes lose their stop too.
        ImportIssue("notes[3].stop_id", "no stop with id 's3'"),
        ImportIssue("notes[4].stop_id", "no stop with id 's3'"),
        ImportIssue("photos[0]", "lat and lon must both be present or both be missing"),
    ]


def test_issue_cap_and_more() -> None:
    data = sample()
    for i in range(60):
        bad = copy.deepcopy(data["notes"][0])
        bad.update(id=f"bad{i}", utc_offset_minutes=7)
        data["notes"].append(bad)
    with pytest.raises(TripFileError) as info:
        parse_trip_file(json.dumps(data).encode(), MAX)
    assert len(info.value.issues) == MAX_ISSUES
    assert info.value.more == 10
    assert info.value.issues[0].location == "notes[8].utc_offset_minutes"


def test_normalises_time_and_blank_name() -> None:
    data = sample()
    data["stops"][0]["start_utc"] = "2026-05-02T08:15:00.750+00:00"
    data["stops"][0]["name"] = "   "
    trip = parse_trip_file(json.dumps(data).encode(), MAX)
    assert trip.stops[0].start_utc == "2026-05-02T08:15:00Z"
    assert trip.stops[0].name is None


def test_duplicate_json_key_keeps_last_value() -> None:
    raw = minimal_trip_bytes().replace(
        b'"title": "A day in Lisbon"', b'"title": "first", "title": "A day in Lisbon"', 1
    )
    assert parse_trip_file(raw, MAX).trip.title == "A day in Lisbon"


def test_route_summary_limit() -> None:
    data = sample()
    data["route_summary"] = "r" * 5001
    assert issues_of(data) == [ImportIssue("route_summary", "must be at most 5000 characters")]


def test_format_location() -> None:
    assert format_location(("stops", 4, "end_utc")) == "stops[4].end_utc"
    assert format_location(()) == "file"
