# ADDED [PROMPT #25]: U3 plan step 17, batching (OR-RUN2, N-4). AI-assisted, Claude Opus 5.5.
"""plan_batches limits, the 1,000-char cut in the prompt only, and stops / labels per batch."""

from __future__ import annotations

import re

from tests.fixtures import Services
from trip_journal.agent.llm import FakeLLMClient, LLMReply
from trip_journal.agent.prompts import PromptLibrary
from trip_journal.config import MAX_NOTE_CHARS, TRUNCATION_SUFFIX
from trip_journal.data.repositories import NoteRow, Repositories
from trip_journal.domain.organizer import cut_note_text, plan_batches
from trip_journal.services.organizer import OrganizerService
from trip_journal.services.settings import SettingsService

DAY = "2026-06-01"
EMPTY = LLMReply(content='{"suggestions": []}')


def note(i: int, size: int) -> NoteRow:
    return NoteRow(i, 1, None, f"n{i:02d}", "x" * size, f"{DAY}T08:{i:02d}:00Z", 0, DAY)


def sizes(batches: list[list[NoteRow]]) -> list[int]:
    return [len(b) for b in batches]


def test_ten_notes_fit_eleven_split() -> None:
    assert sizes(plan_batches([note(i, 10) for i in range(10)])) == [10]
    assert sizes(plan_batches([note(i, 10) for i in range(11)])) == [10, 1]
    assert sizes(plan_batches([note(i, 10) for i in range(25)])) == [10, 10, 5]


def test_char_budget_closes_a_batch_before_the_note_that_would_pass_it() -> None:
    assert sizes(plan_batches([note(i, 1000) for i in range(6)])) == [6]  # exactly 6,000
    assert sizes(plan_batches([note(i, 900) for i in range(7)])) == [6, 1]  # 6,300 > 6,000
    five = [note(i, 1000) for i in range(5)]
    assert sizes(plan_batches([*five, note(5, 999), note(6, 2)])) == [6, 1]


def test_long_notes_count_at_their_cut_size() -> None:
    cut = len(cut_note_text("x" * 5000))
    assert cut == MAX_NOTE_CHARS + len(TRUNCATION_SUFFIX)
    per_batch = 6000 // cut
    assert sizes(plan_batches([note(i, 5000) for i in range(10)])) == [per_batch] * (
        10 // per_batch
    ) + ([10 % per_batch] if 10 % per_batch else [])


def test_a_single_huge_note_is_still_sent_alone() -> None:
    assert sizes(plan_batches([note(0, 50_000)])) == [1]
    assert plan_batches([]) == []


def _service(services: Services, llm: FakeLLMClient) -> OrganizerService:
    settings = SettingsService(services.repos.settings, env={})
    return OrganizerService(
        services.repos, services.jobs, settings, services.trips, lambda _s: llm, PromptLibrary()
    )


async def test_every_batch_carries_all_stops_and_restarts_labels(
    services: Services, repos: Repositories
) -> None:
    trip = repos.trips.add("split", "Split")
    repos.stops.add(trip, "a", "Bakery", f"{DAY}T07:00:00Z", f"{DAY}T08:00:00Z", 0, 1.0, 1.0)
    repos.stops.add(trip, "b", None, f"{DAY}T12:00:00Z", f"{DAY}T13:00:00Z", 0, 1.0, 1.0)
    long_text = "y" * (MAX_NOTE_CHARS + 50)
    for i in range(11):
        text = long_text if i == 10 else f"note {i}"
        repos.notes.add(trip, f"x{i:02d}", text, f"{DAY}T09:{i:02d}:00Z", 0)
    llm = FakeLLMClient([EMPTY, EMPTY])
    started = await _service(services, llm).start(trip, DAY)
    assert started.job is not None and started.batches == 2
    await services.jobs.wait(started.job.job_id)

    first, second = (call[-1]["content"] for call in llm.calls)
    for message in (first, second):
        assert "s1 | Bakery | 07:00-08:00" in message
        assert "s2 | Unnamed place | 12:00-13:00" in message
    assert re.findall(r'<note id="(n\d+)">', first) == [f"n{i}" for i in range(1, 11)]
    assert re.findall(r'<note id="(n\d+)">', second) == ["n1"]
    # the 1,000-char cut and mark are in the prompt only; the stored note is unchanged
    assert "y" * MAX_NOTE_CHARS + TRUNCATION_SUFFIX + "</note>" in second
    stored = [n.text for n in repos.notes.list_for_trip(trip)]
    assert long_text in stored
