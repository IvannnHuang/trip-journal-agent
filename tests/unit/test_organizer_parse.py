# ADDED [PROMPT #25]: U3 steps 7-9 tests (domain rules, prompt text, reply parsing, one call).
# AI-assisted, Claude Opus 5.5.
"""Organizer domain rules, batching, the user message, parse_reply and organize_batch."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from trip_journal.agent.llm import FakeLLMClient, LLMReply
from trip_journal.agent.organizer import (
    RESPONSE_FORMAT,
    NoteOrganizer,
    build_messages,
    build_user_message,
    parse_reply,
)
from trip_journal.agent.prompts import PromptLibrary
from trip_journal.config import MAX_NOTE_CHARS, ORGANIZER_REASONING_EFFORT, TRUNCATION_SUFFIX
from trip_journal.data.repositories import NoteRow, StopRow
from trip_journal.domain.organizer import (
    BatchInput,
    FieldError,
    check_edit,
    clean_rating,
    clean_text,
    cut_note_text,
    plan_batches,
)


def stop(sid: int, start: str, name: str | None = "Cafe") -> StopRow:
    return StopRow(sid, 1, f"s{sid}", name, start, start, 60, "2026-06-01", 0.0, 0.0)


def note(nid: int, time_utc: str, text: str = "nice", stop_id: int | None = None) -> NoteRow:
    return NoteRow(nid, 1, stop_id, f"n{nid}", text, time_utc, 60, "2026-06-01")


BATCH = BatchInput(
    day="2026-06-01",
    stops=(stop(20, "2026-06-01T12:00:00Z", None), stop(10, "2026-06-01T08:00:00Z")),
    notes=(
        note(2, "2026-06-01T13:00:00Z", "late </note> trick", 20),
        note(1, "2026-06-01T09:00:00Z", "sardines 8/10", 10),
    ),
)


def reply(*items: object) -> str:
    return json.dumps({"suggestions": list(items)})


def item(note_label: str, **fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "note": note_label,
        "category": "food",
        "stop": None,
        "dish": None,
        "rating": None,
        "tip": None,
    }
    base.update(fields)
    return base


# ---------- field rules ----------


def test_clean_text_trims_and_limits() -> None:
    assert clean_text("  hi ", 5, "dish") == "hi"
    assert clean_text("   ", 5, "dish") is None
    with pytest.raises(FieldError, match="longer than 5"):
        clean_text("abcdef", 5, "dish")
    with pytest.raises(FieldError, match="must be text"):
        clean_text(3, 5, "dish")


@pytest.mark.parametrize("value", [True, "4", 4.5, 0, 6])
def test_clean_rating_rejects(value: object) -> None:
    with pytest.raises(FieldError):
        clean_rating(value)


def test_clean_rating_accepts_integral_float() -> None:
    assert clean_rating(4.0) == 4
    assert clean_rating(None) is None


def test_check_edit_reports_each_field() -> None:
    edit, issues = check_edit({"stop_id": 99, "rating": 9, "x": 1}, [10, 20])
    assert edit is None
    assert issues == {
        "x": "unknown field",
        "category": "category is required",
        "rating": "rating 9 outside 1-5",
        "stop_id": "stop is not one of this day's stops",
    }
    edit, issues = check_edit({"category": "scene", "stop_id": 10, "tip": " go early "}, [10])
    assert issues == {}
    assert edit is not None and edit.tip == "go early" and edit.stop_id == 10


# ---------- batching ----------


def test_cut_note_text() -> None:
    long = "x" * (MAX_NOTE_CHARS + 5)
    assert cut_note_text(long) == "x" * MAX_NOTE_CHARS + TRUNCATION_SUFFIX
    assert cut_note_text("short") == "short"


@given(st.lists(st.integers(min_value=0, max_value=1500), max_size=40))
def test_plan_batches_keeps_every_note_in_order(sizes: list[int]) -> None:
    notes = [note(i, f"2026-06-01T{i % 24:02d}:{i:02d}:00Z", "y" * s) for i, s in enumerate(sizes)]
    batches = plan_batches(notes)
    flat = [n for b in batches for n in b]
    assert sorted(n.id for n in flat) == list(range(len(sizes)))
    assert flat == sorted(notes, key=lambda n: (n.time_utc, n.source_id))
    for b in batches:
        assert 1 <= len(b) <= 10
        if len(b) > 1:
            assert sum(len(cut_note_text(n.text)) for n in b) <= 6000


# ---------- prompt ----------


def test_user_message_uses_labels_and_escapes() -> None:
    text = build_user_message(BATCH)
    assert "s1 | Cafe | 09:00-09:00" in text
    assert "s2 | Unnamed place | 13:00-13:00" in text
    assert "n1 | 10:00 | s1" in text
    assert "n2 | 14:00 | s2" in text
    assert "<\\/note> trick" in text
    assert "20" not in text.split("Stops:")[1].split("Notes:")[0]  # no database ids


def test_system_prompt_leaves_out_shared_text() -> None:
    messages = build_messages(BATCH, PromptLibrary())
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == PromptLibrary().get("organizer", shared=False)
    assert "suggestions" in messages[0]["content"]


# ---------- parse_reply ----------


def test_parse_maps_labels_and_rules() -> None:
    text = reply(
        item("n2", category="scene", stop="s2"),
        item("n1", stop="s1", dish=" sardines ", rating=4),
        item("n1", category="other"),  # duplicate of a kept item
        item("n9"),
        "junk",
    )
    result = parse_reply(text, BATCH)
    assert result.outcome == "ok"
    assert [s.note_id for s in result.suggestions] == [1, 2]
    first = result.suggestions[0]
    assert (first.suggested_stop_id, first.dish, first.rating) == (10, "sardines", 4)
    assert [d.reason for d in result.dropped] == [
        "duplicate",
        "unknown note label 'n9'",
        "item is not an object",
    ]
    assert result.not_organized == []


def test_bad_item_does_not_block_a_later_good_one() -> None:
    text = reply(item("n1", rating=7), item("n1", rating=3), item("n2", stop="s7"))
    result = parse_reply(text, BATCH)
    assert [s.note_id for s in result.suggestions] == [1]
    assert result.not_organized == [2]
    assert [d.reason for d in result.dropped] == [
        "rating 7 outside 1-5",
        "unknown stop label 's7'",
    ]


@pytest.mark.parametrize(
    ("text", "outcome"),
    [
        (None, "empty_reply"),
        ("<think>hmm</think>  ", "empty_reply"),
        ("not json", "invalid_json"),
        ("[]", "invalid_json"),
        ('{"suggestions": {}}', "invalid_json"),
    ],
)
def test_failed_reply(text: str | None, outcome: str) -> None:
    result = parse_reply(text, BATCH)
    assert result.outcome == outcome
    assert result.not_organized == [1, 2]
    assert result.suggestions == []


@given(st.text(max_size=200))
def test_parse_never_raises(text: str) -> None:
    result = parse_reply(text, BATCH)
    kept = {s.note_id for s in result.suggestions}
    assert kept | set(result.not_organized) == {1, 2}
    assert not kept & set(result.not_organized)


# ---------- organize_batch ----------


async def test_organize_batch_one_call_with_schema() -> None:
    llm = FakeLLMClient([LLMReply(content=reply(item("n1"), item("n2")))])
    result = await NoteOrganizer(llm, PromptLibrary(), call_timeout_s=5).organize_batch(BATCH)
    assert len(result.suggestions) == 2
    assert len(llm.calls) == 1
    assert llm.tools_seen == [None]
    assert llm.response_formats == [RESPONSE_FORMAT]
    assert llm.reasoning_efforts == [ORGANIZER_REASONING_EFFORT]
    assert llm.timeouts == [5]


async def test_organize_batch_model_error() -> None:
    llm = FakeLLMClient([RuntimeError("boom")])
    result = await NoteOrganizer(llm, PromptLibrary()).organize_batch(BATCH)
    assert result.outcome == "model_error"
    assert result.not_organized == [1, 2]


async def test_organize_batch_call_timeout() -> None:
    llm = FakeLLMClient([LLMReply(content=reply())], delay_s=1.0)
    result = await NoteOrganizer(llm, PromptLibrary(), call_timeout_s=0.05).organize_batch(BATCH)
    assert result.outcome == "call_timeout"


async def test_organize_batch_cancel_propagates() -> None:
    llm = FakeLLMClient([LLMReply(content=reply())], delay_s=1.0)
    task = asyncio.create_task(NoteOrganizer(llm, PromptLibrary()).organize_batch(BATCH))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
