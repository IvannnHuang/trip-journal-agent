# ADDED [PROMPT #36]: edits around save, ordering, transaction rollback and trace fidelity.
import sqlite3

import pytest

from trip_journal.agent.loop import ToolCallRecord
from trip_journal.data.repositories import Repositories
from trip_journal.domain.grounding import Citation
from trip_journal.services.errors import NotFoundError


def test_ownership_and_positions(repos: Repositories, conn: sqlite3.Connection) -> None:
    trip = repos.trips.add("trip", "Title")
    repo = repos.journals
    day = "2026-06-01"
    order = ["summary", "stop:2", "stop:1"]
    trace = [
        ToolCallRecord(
            group="prefetch",
            step=0,
            name="get_stop_notes",
            arguments={"stop_id": 2},
            returned_ids=[Citation("note", 1)],
        )
    ]
    repo.save_generated(
        trip, day, order, dict.fromkeys(order, "old"), "casual", trace, "v1", "fake"
    )
    before = repo.get(trip, day)
    assert before and before.trace == trace
    changes = conn.total_changes
    assert repo.save_user_edit(trip, day, "summary", "old").owner == "generated"
    assert repo.get(trip, day) == before and conn.total_changes == changes
    repo.save_user_edit(trip, day, "stop:1", " old")
    order.reverse()
    merge = repo.save_generated(
        trip, day, order, dict.fromkeys(order, "new"), "concise", trace, "v2", "fake"
    )
    assert [p.text for p in merge.paragraphs] == [" old", "new", "new"]
    after = repo.get(trip, day)
    assert after and after.paragraphs == merge.paragraphs and after.tone == "concise"
    assert repo.save_user_edit(trip, day, "summary", "").owner == "user"
    with pytest.raises(NotFoundError):
        repo.save_user_edit(trip, day, "unknown", "x")
    before = repo.get(trip, day)
    conn.execute(
        "CREATE TRIGGER fail_save BEFORE UPDATE ON journal_paragraphs "
        "BEGIN SELECT RAISE(ABORT,'fail'); END"
    )
    with pytest.raises(sqlite3.IntegrityError):
        repo.save_generated(
            trip, day, order, {"stop:2": "lost"}, "detailed", [], "other", "different"
        )
    assert repo.get(trip, day) == before
