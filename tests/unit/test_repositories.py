# ADDED [PROMPT #13]: repository tests (domain-entities, TA-4, TA-8). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import sqlite3
from datetime import datetime

import pytest

from tests.conftest import Seed
from trip_journal.data.db import transaction
from trip_journal.data.repositories import Repositories, to_local
from trip_journal.domain.grounding import Citation
from trip_journal.places.lookup import cache_key


def test_to_local_applies_offset() -> None:
    assert to_local("2026-06-01T23:30:00Z", 120) == datetime(2026, 6, 2, 1, 30)


def test_trip_lookup_and_delete_cascades(repos: Repositories, seed: Seed) -> None:
    found = repos.trips.get_by_source_id("trip-a")
    assert found is not None and found.id == seed.trip_id
    assert len(repos.trips.list()) == 2
    repos.trips.delete(seed.trip_id)
    assert repos.trips.get(seed.trip_id) is None
    assert repos.stops.get(seed.trip_id, seed.stops[0]) is None
    assert repos.notes.list_for_day(seed.trip_id, "2026-06-01") == []


def test_stops_are_scoped_to_trip(repos: Repositories, seed: Seed) -> None:
    assert repos.stops.get(seed.other_trip_id, seed.stops[0]) is None
    day = repos.stops.list_for_day(seed.trip_id, "2026-06-01")
    assert [s.id for s in day] == seed.stops
    assert repos.stops.counts(seed.trip_id, seed.stops[0]) == (1, 1)


def test_local_date_uses_offset(repos: Repositories, seed: Seed) -> None:
    late = repos.notes.add(seed.trip_id, "late", "late", "2026-06-01T23:00:00Z", 120)
    assert late in [n.id for n in repos.notes.list_for_day(seed.trip_id, "2026-06-02")]


def test_find_by_coordinates_uses_cache_key(repos: Repositories, seed: Seed) -> None:
    stop = repos.stops.find_by_coordinates(seed.trip_id, cache_key(46.36251), cache_key(14.09379))
    assert stop is not None and stop.id == seed.stops[0]
    assert repos.stops.find_by_coordinates(seed.trip_id, "0.0000", "0.0000") is None


def test_photos_between_is_inclusive(repos: Repositories, seed: Seed) -> None:
    found = repos.photos.find_between(
        seed.trip_id, datetime(2026, 6, 1, 9, 45), datetime(2026, 6, 1, 13, 30)
    )
    assert [p.id for p in found] == seed.photos


def test_known_citation_ids(repos: Repositories, seed: Seed) -> None:
    known = repos.trips.known_citation_ids(seed.trip_id)
    assert Citation("stop", seed.stops[0]) in known
    assert Citation("note", seed.notes[2]) in known
    assert Citation("photo", seed.photos[1]) in known
    other_note = repos.notes.search(seed.other_trip_id, "coast")[0].id
    assert Citation("note", other_note) not in known


def test_settings_set_many_and_place_cache(repos: Repositories) -> None:
    repos.settings.set_many({"a": "1", "b": "2"})
    repos.settings.set("a", "3")
    assert repos.settings.get_all() == {"a": "3", "b": "2"}
    assert repos.place_cache.get("1.0000", "2.0000") is None
    repos.place_cache.put("1.0000", "2.0000", "Somewhere")
    repos.place_cache.put("1.0000", "2.0000", "Elsewhere")
    assert repos.place_cache.get("1.0000", "2.0000") == "Elsewhere"


def test_transaction_rolls_back(conn: sqlite3.Connection, repos: Repositories) -> None:
    with pytest.raises(RuntimeError), transaction(conn):
        conn.execute(
            "INSERT INTO settings (key, value, updated_at)"
            " VALUES ('x', 'y', '2026-01-01T00:00:00Z')"
        )
        raise RuntimeError("boom")
    assert repos.settings.get_all() == {}


def test_note_update_and_delete_keep_search_in_sync(repos: Repositories, seed: Seed) -> None:
    n1 = seed.notes[0]
    repos.notes.update_text(n1, "Visited the castle")
    assert [n.id for n in repos.notes.search(seed.trip_id, "castle")] == [n1]
    assert repos.notes.search(seed.trip_id, "swam") == []
    repos.notes.delete(n1)
    assert repos.notes.search(seed.trip_id, "castle") == []
