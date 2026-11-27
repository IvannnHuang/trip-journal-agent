# ADDED [PROMPT #25]: SuggestionRepository tests (U3 IC-6, OR-SAVE1, FA-1, FA-3, OR-AA1, OR-R1).
# AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import sqlite3

import pytest

from tests.conftest import Seed
from trip_journal.data.repositories import Repositories
from trip_journal.data.suggestions import FinalValues
from trip_journal.domain.organizer import NoteSuggestion


def sug(note_id: int, category: str = "food", stop_id: int | None = None) -> NoteSuggestion:
    return NoteSuggestion(
        note_id=note_id,
        category=category,  # type: ignore[arg-type]
        suggested_stop_id=stop_id,
        dish="dish",
        rating=3,
        tip="tip",
    )


def by_note(repos: Repositories, trip_id: int) -> dict[int, str]:
    return {r.note_id: r.status for r in repos.suggestions.list_for_trip(trip_id)}


def test_save_inserts_then_replaces_pending_only(repos: Repositories, seed: Seed) -> None:
    n1, n2, _ = seed.notes
    repo = repos.suggestions
    assert repo.save_batch(seed.trip_id, [sug(n1), sug(n2)], "v1", "m1") == 2
    first = repo.list_for_trip(seed.trip_id)
    assert [r.status for r in first] == ["pending", "pending"]
    repo.set_status(first[0].id, "rejected")
    assert repo.save_batch(seed.trip_id, [sug(n1, "scene"), sug(n2, "scene")], "v2", "m2") == 1
    rows = {r.note_id: r for r in repo.list_for_trip(seed.trip_id)}
    assert rows[n1].status == "rejected" and rows[n1].s_category == "food"  # FA-3
    assert rows[n2].s_category == "scene" and rows[n2].prompt_version == "v2"
    assert rows[n2].model_name == "m2" and rows[n2].id == first[1].id  # FA-1: one row per note


def test_set_status_edited_stores_final_values(repos: Repositories, seed: Seed) -> None:
    repo = repos.suggestions
    repo.save_batch(seed.trip_id, [sug(seed.notes[0], stop_id=seed.stops[0])], "v", "m")
    sid = repo.list_for_trip(seed.trip_id)[0].id
    repo.set_status(sid, "edited", FinalValues("scene", seed.stops[1], None, 5, None))
    row = repo.get(sid)
    assert row is not None and row.status == "edited" and row.organized
    assert row.f_category == "scene" and row.f_rating == 5 and row.decided_at is not None
    assert row.effective_stop_id == seed.stops[1]
    repo.undo(sid)
    row = repo.get(sid)
    assert row is not None and row.status == "pending" and not row.organized
    assert row.f_category is None and row.f_rating is None and row.decided_at is None
    assert row.effective_stop_id == seed.stops[0]


def test_accepted_ignores_final_values(repos: Repositories, seed: Seed) -> None:
    repo = repos.suggestions
    repo.save_batch(seed.trip_id, [sug(seed.notes[0])], "v", "m")
    sid = repo.list_for_trip(seed.trip_id)[0].id
    repo.set_status(sid, "accepted", FinalValues("scene", None, None, 5, None))
    row = repo.get(sid)
    assert row is not None and row.f_category is None and row.organized


def test_accept_all_pending_only_given_notes(repos: Repositories, seed: Seed) -> None:
    n1, n2, n3 = seed.notes
    repo = repos.suggestions
    repo.save_batch(seed.trip_id, [sug(n1), sug(n2), sug(n3)], "v", "m")
    repo.set_status(repo.list_for_trip(seed.trip_id)[1].id, "rejected")
    assert repo.accept_all_pending(seed.trip_id, [n1, n2]) == 1
    assert by_note(repos, seed.trip_id) == {n1: "accepted", n2: "rejected", n3: "pending"}
    assert repo.accept_all_pending(seed.trip_id, []) == 0


def test_list_for_day_and_get_missing(repos: Repositories, seed: Seed) -> None:
    n1, n2, n3 = seed.notes
    repos.suggestions.save_batch(seed.trip_id, [sug(n3), sug(n2), sug(n1)], "v", "m")
    day1 = repos.suggestions.list_for_day(seed.trip_id, "2026-06-01")
    assert [r.note_id for r in day1] == [n1, n2]  # note time order
    assert [r.note_id for r in repos.suggestions.list_for_day(seed.trip_id, "2026-06-02")] == [n3]
    assert repos.suggestions.get(999) is None


def test_uncommitted_save_rolls_back(
    repos: Repositories, seed: Seed, conn: sqlite3.Connection
) -> None:
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    repos.suggestions.save_batch(seed.trip_id, [sug(seed.notes[0])], "v", "m", commit=False)
    conn.rollback()
    assert repos.suggestions.list_for_trip(seed.trip_id) == []


def test_notes_table_is_never_written(repos: Repositories, seed: Seed) -> None:
    before = repos.notes.list_for_trip(seed.trip_id)
    repo = repos.suggestions
    repo.save_batch(seed.trip_id, [sug(n, stop_id=seed.stops[1]) for n in seed.notes], "v", "m")
    for row in repo.list_for_trip(seed.trip_id):
        repo.set_status(row.id, "accepted")
    assert repos.notes.list_for_trip(seed.trip_id) == before  # OR-R1


def test_delete_note_or_trip_cascades(repos: Repositories, seed: Seed) -> None:
    repos.suggestions.save_batch(seed.trip_id, [sug(n) for n in seed.notes], "v", "m")
    repos.trips.delete(seed.trip_id)
    assert repos.suggestions.list_for_trip(seed.trip_id) == []


def test_status_check_constraint(repos: Repositories, seed: Seed) -> None:
    repos.suggestions.save_batch(seed.trip_id, [sug(seed.notes[0])], "v", "m")
    sid = repos.suggestions.list_for_trip(seed.trip_id)[0].id
    with pytest.raises(sqlite3.IntegrityError):
        repos.suggestions.set_status(sid, "maybe")
