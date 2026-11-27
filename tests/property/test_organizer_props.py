# ADDED [PROMPT #25]: U3 organizer properties P-O1, P-O2, P-O3 (plan step 19, PBT-02 / PBT-03).
# AI-assisted, Claude Opus 5.5.
"""P-O1 accept all, P-O2 raw notes never change, P-O3 reply parser, plus the parser round trip.

FakeLLMClient only (LabellingLLM): no test reaches a real Ollama.
"""

from __future__ import annotations

import json
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from tests.fixtures.organizer import (
    NEXT_DAY,
    SAMPLE_DAY,
    LabellingLLM,
    import_two_day_trip,
    review_client,
    run_organizer,
)
from tests.strategies import batch_labels, batches, reply_texts, valid_reply_items
from trip_journal.agent.organizer import make_labels, parse_reply
from trip_journal.domain.organizer import CATEGORIES, DISH_MAX, TIP_MAX, BatchInput

DAYS = (SAMPLE_DAY, NEXT_DAY)
ROWS = 8  # a whole-trip run on the two-day trip suggests 6 + 2 notes (hand-off 7)
EDIT = {"category": "scene", "tip": "Go early."}


def all_rows(client: TestClient, trip_id: int) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for day in DAYS:
        reply = client.get(f"/api/trips/{trip_id}/days/{day}/suggestions")
        assert reply.status_code == 200
        rows.update({r["suggestion_id"]: r for r in reply.json()})
    return rows


def review(client: TestClient, sid: int, action: str) -> int:
    """One review action through the JSON API; returns the HTTP status."""
    if action == "edit":
        return client.put(f"/api/suggestions/{sid}", json=EDIT).status_code
    return client.post(f"/api/suggestions/{sid}/{action}").status_code


def raw_notes(client: TestClient, trip_id: int) -> list[tuple[int, str, int | None]]:
    app = cast(FastAPI, client.app)
    return [(n.id, n.text, n.stop_id) for n in app.state.trip.repos.notes.list_for_trip(trip_id)]


# ---------- P-O1 ----------

_mix = st.lists(st.sampled_from(["keep", "accept", "reject", "edit"]), min_size=ROWS, max_size=ROWS)


@given(mix=_mix, day=st.sampled_from(DAYS))
def test_p_o1_accept_all_changes_exactly_the_days_pending_rows(mix: list[str], day: str) -> None:
    with review_client(LabellingLLM()) as client:
        trip_id = import_two_day_trip(client)
        run_organizer(client, trip_id)
        rows = all_rows(client, trip_id)
        assert len(rows) == ROWS
        for sid, action in zip(sorted(rows), mix, strict=True):
            if action != "keep":
                assert review(client, sid, action) == 200
        before = all_rows(client, trip_id)
        pending = {
            s for s, r in before.items() if r["local_date"] == day and r["status"] == "pending"
        }

        reply = client.post(f"/api/trips/{trip_id}/days/{day}/suggestions/accept-all")

        assert reply.status_code == 200 and reply.json() == {"accepted": len(pending)}
        after = all_rows(client, trip_id)
        assert after.keys() == before.keys()
        for sid, row in before.items():
            expected = {**row, "status": "accepted"} if sid in pending else row
            assert after[sid] == expected


# ---------- P-O2 ----------

_steps = st.lists(
    st.tuples(
        st.sampled_from(
            ["accept", "reject", "edit", "undo", "accept_all", "rerun_day", "rerun_trip"]
        ),
        st.integers(min_value=0, max_value=ROWS - 1),
        st.sampled_from(DAYS),
        st.sampled_from(CATEGORIES),
    ),
    min_size=1,
    max_size=12,
)


@given(steps=_steps)
def test_p_o2_runs_and_reviews_never_change_raw_notes(
    steps: list[tuple[str, int, str, str]],
) -> None:
    llm = LabellingLLM()
    with review_client(llm) as client:
        trip_id = import_two_day_trip(client)
        notes = raw_notes(client, trip_id)
        for action, index, day, category in steps:
            if action.startswith("rerun"):
                llm.category = category  # a re-run replaces pending values (OR-RUN1)
                run_organizer(client, trip_id, day if action == "rerun_day" else None)
            elif action == "accept_all":
                url = f"/api/trips/{trip_id}/days/{day}/suggestions/accept-all"
                assert client.post(url).status_code == 200
            else:
                rows = sorted(all_rows(client, trip_id))
                if rows:
                    assert review(client, rows[index % len(rows)], action) in (200, 409)
            assert raw_notes(client, trip_id) == notes  # OR-R1, byte for byte


# ---------- P-O3 ----------


@st.composite
def batch_and_reply(draw: st.DrawFn) -> tuple[BatchInput, str]:
    batch = draw(batches())
    return batch, draw(reply_texts(batch))


@given(case=batch_and_reply())
def test_p_o3_parser_partitions_the_batch_and_keeps_only_valid_items(
    case: tuple[BatchInput, str],
) -> None:
    batch, text = case
    result = parse_reply(text, batch)  # never raises

    note_ids = {n.id for n in batch.notes}
    kept = [s.note_id for s in result.suggestions]
    assert len(kept) == len(set(kept))  # at most one suggestion per note
    assert set(kept) <= note_ids
    assert set(kept).isdisjoint(result.not_organized)
    assert set(kept) | set(result.not_organized) == note_ids
    assert len(result.not_organized) == len(set(result.not_organized))
    stop_ids = {s.id for s in batch.stops}
    for s in result.suggestions:
        assert s.category in CATEGORIES  # OR-F4
        assert s.suggested_stop_id is None or s.suggested_stop_id in stop_ids  # OR-S1
        assert s.rating is None or (type(s.rating) is int and 1 <= s.rating <= 5)  # OR-F3
        for value, limit in ((s.dish, DISH_MAX), (s.tip, TIP_MAX)):  # OR-F2
            assert value is None or (value == value.strip() and 0 < len(value) <= limit)


@st.composite
def valid_replies(draw: st.DrawFn) -> tuple[BatchInput, list[dict[str, Any]]]:
    batch = draw(batches())
    note_labels, stop_labels = batch_labels(batch)
    chosen = draw(st.lists(st.sampled_from(note_labels), unique=True))
    return batch, [draw(valid_reply_items(label, stop_labels)) for label in chosen]


def _clean(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


@given(case=valid_replies())
def test_p_o3_valid_reply_round_trip_keeps_every_item(
    case: tuple[BatchInput, list[dict[str, Any]]],
) -> None:
    batch, items = case
    result = parse_reply(json.dumps({"suggestions": items}, ensure_ascii=False), batch)

    labels = make_labels(batch)
    assert result.outcome == "ok" and result.dropped == []
    got = {s.note_id: s for s in result.suggestions}
    assert len(got) == len(items)
    for item in items:
        s = got[labels.note_ids[item["note"]]]
        stop = labels.stop_ids[item["stop"]] if item["stop"] is not None else None
        assert (s.category, s.suggested_stop_id, s.rating) == (
            item["category"],
            stop,
            item["rating"],
        )
        assert (s.dish, s.tip) == (_clean(item["dish"]), _clean(item["tip"]))
