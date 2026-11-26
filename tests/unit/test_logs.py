# ADDED [PROMPT #13]: logging tests (LC-1..LC-8). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import asyncio
import logging

import pytest

from tests.conftest import Seed
from trip_journal.agent.llm import ToolCall
from trip_journal.agent.tools import ToolContext, default_registry
from trip_journal.data.repositories import Repositories
from trip_journal.logs import JobIdFilter, current_job_id, kv, setup_logging


def test_kv_quotes_values_with_spaces_and_empty() -> None:
    assert kv("e", a=1, b="x y", c="", d="ok") == "e a=1 b='x y' c='' d=ok"


def test_job_id_filter_uses_dash_outside_a_job() -> None:
    record = logging.LogRecord("n", logging.INFO, "f", 1, "m", None, None)
    JobIdFilter().filter(record)
    assert record.__dict__["job_id"] == "-"


async def test_job_id_is_per_task() -> None:
    seen: list[str] = []

    async def inner(value: str) -> None:
        current_job_id.set(value)
        await asyncio.sleep(0)
        seen.append(current_job_id.get() or "")

    await asyncio.gather(inner("a"), inner("b"))
    assert sorted(seen) == ["a", "b"]
    assert current_job_id.get() is None


def test_setup_logging_is_idempotent_and_rejects_bad_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    root = logging.getLogger()
    old_level = root.level
    setup_logging("DEBUG")
    setup_logging("nonsense")
    marked = [h for h in root.handlers if getattr(h, "_trip_journal_handler", False)]
    assert len(marked) == 1
    assert root.level == logging.INFO
    assert "log.level_invalid" in caplog.text
    root.removeHandler(marked[0])
    root.setLevel(old_level)


async def test_note_text_never_logged(
    seed: Seed, repos: Repositories, caplog: pytest.LogCaptureFixture
) -> None:
    """LC-5: tool calls log ids and counts only, never note text or the query."""
    caplog.set_level(logging.DEBUG)
    marker = "ZEBRAMARKER"
    repos.notes.add(seed.trip_id, "m1", f"note with {marker}", "2026-06-01T08:00:00Z", 120)
    ctx = ToolContext(trip_id=seed.trip_id, repos=repos, places=None)  # type: ignore[arg-type]
    call = ToolCall(id="1", name="search_notes", arguments_json=f'{{"query": "{marker}"}}')
    outcome = await default_registry().execute(call, ctx)
    assert marker in outcome.content
    assert marker not in caplog.text
