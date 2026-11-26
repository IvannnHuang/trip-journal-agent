# ADDED [PROMPT #13]: tool result properties P-T1..P-T4 (TR-1..TR-4, TA-7, TA-9).
# AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import asyncio
from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from tests.strategies import json_values
from trip_journal.agent.llm import ToolCall
from trip_journal.agent.tools import (
    RESULT_CLOSE,
    RESULT_OPEN,
    NoteView,
    ToolContext,
    default_registry,
    truncate_text,
    unwrap_tool_result,
    wrap_tool_result,
)
from trip_journal.config import MAX_NOTE_CHARS, MAX_TOOL_RECORDS, TRUNCATION_SUFFIX
from trip_journal.data.db import connect, init_schema
from trip_journal.data.repositories import Repositories

_extra_text = st.text(st.characters(codec="utf-8"), max_size=20)


@given(json_values | st.text(alphabet="<>/&\"'中文é", max_size=30))
def test_p_t1_wrap_round_trip(value: Any) -> None:
    content = wrap_tool_result(value)
    assert unwrap_tool_result(content) == value
    body = content[len(RESULT_OPEN) : content.rindex(RESULT_CLOSE)]
    assert "<" not in body  # no tag can be closed early


@given(st.integers(min_value=0, max_value=120))
def test_p_t2_records_capped(n: int) -> None:
    registry = default_registry()
    views = [
        NoteView(
            note_id=i + 1,
            cite=f"[note:{i + 1}]",
            stop_id=None,
            time_local="t",
            text="x",
            truncated=False,
        )
        for i in range(n)
    ]
    outcome = registry._data_result("search_notes", views)
    data = unwrap_tool_result(outcome.content)
    assert len(data["records"]) == min(n, MAX_TOOL_RECORDS) == len(outcome.returned_ids)
    assert data["total"] == n and data["truncated"] is (n > MAX_TOOL_RECORDS)


@given(st.text(max_size=MAX_NOTE_CHARS * 2))
def test_p_t3_truncation(text: str) -> None:
    out, cut = truncate_text(text)
    assert cut is (len(text) > MAX_NOTE_CHARS)
    if cut:
        assert out == text[:MAX_NOTE_CHARS] + TRUNCATION_SUFFIX
    else:
        assert out == text


@given(st.sampled_from([*default_registry().names, "nope"]), _extra_text)
def test_p_t4_any_call_returns_an_envelope(name: str, args: str) -> None:
    conn = connect(":memory:")
    init_schema(conn)
    repos = Repositories.from_connection(conn)
    trip = repos.trips.add("t", "T")
    ctx = ToolContext(trip_id=trip, repos=repos, places=None)  # type: ignore[arg-type]
    try:
        outcome = asyncio.run(
            default_registry().execute(ToolCall(id="1", name=name, arguments_json=args), ctx)
        )
    finally:
        conn.close()
    data = unwrap_tool_result(outcome.content)
    if outcome.error is not None:
        assert data["error"]["kind"] == outcome.error.kind and outcome.returned_ids == []
