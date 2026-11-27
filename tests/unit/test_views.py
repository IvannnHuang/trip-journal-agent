# ADDED [PROMPT #17]: golden day view of the Lisbon sample (TL-1..TL-7, IC-4).
# AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.fixtures import Services, load_minimal_trip
from trip_journal.domain.views import DaySummary, DayView


@pytest.fixture
def day(services: Services) -> DayView:
    trip_id = load_minimal_trip(services).trip_id
    return services.trips.get_day(trip_id, "2026-05-02")


def test_day_header(day: DayView) -> None:
    assert day.trip_title == "A day in Lisbon"
    assert day.heading == "Day 1 - Sat 2 May 2026"
    assert (day.day_number, day.day_count) == (1, 1)
    assert (day.prev_date, day.next_date) == (None, None)
    assert day.show_offsets is False


def test_stops_in_order_with_times(day: DayView) -> None:
    rows = [(s.name, s.start_local, s.end_local, s.end_day_label) for s in day.stops]
    assert rows == [
        ("Café A Brasileira", "09:15", "10:00", ""),
        (None, "10:40", "11:30", ""),
        ("Museu Nacional do Azulejo", "14:00", "16:30", ""),
        ("Late dinner in Bairro Alto", "23:10", "01:30", "+1 day"),
    ]
    assert [s.ends_next_day for s in day.stops] == [False, False, False, True]
    assert {s.offset_label for s in day.stops} == {"UTC+01:00"}


def test_notes_and_photos_per_stop(day: DayView) -> None:
    notes = [[n.local_time for n in s.notes] for s in day.stops]
    assert notes == [["09:30", "09:50"], ["10:50"], ["14:20", "16:10"], ["23:30", "00:50"]]
    assert [s.photo_count for s in day.stops] == [2, 3, 2, 2]
    s4 = day.stops[3]
    assert [n.days_after for n in s4.notes] == [0, 1]
    assert [(p.file_name, p.local_time, p.days_after) for p in s4.photos] == [
        ("IMG_0009.jpg", "23:20", 0),
        ("IMG_0010.jpg", "00:40", 1),
    ]
    no_location = day.stops[2].photos[1]
    assert (no_location.file_name, no_location.lat, no_location.lon) == ("IMG_0008.jpg", None, None)


def test_unlinked_note_and_other_photo(day: DayView) -> None:
    assert [(n.local_time, n.text) for n in day.unlinked_notes] == [
        ("12:45", "Lunch on a bench. Tram 28 passed twice.")
    ]
    assert [(p.file_name, p.local_time) for p in day.other_photos] == [("IMG_0006.jpg", "12:30")]


def test_views_are_frozen() -> None:
    summary = DaySummary(
        local_date="2026-05-02", day_number=1, stop_count=1, note_count=0, photo_count=0
    )
    with pytest.raises(ValidationError):
        summary.day_number = 2
