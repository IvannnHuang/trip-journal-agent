# ADDED [PROMPT #36]: journal invariants P-1 through P-8 and SQLite round trip.
from contextlib import closing

from hypothesis import given
from hypothesis import strategies as st

from tests.strategies import journal_cases, journal_outputs, journal_stop_sizes, journal_texts
from trip_journal.agent.journal import chunk_stops, parse_journal_output
from trip_journal.agent.loop import ToolCallRecord
from trip_journal.data.db import connect, init_schema
from trip_journal.data.repositories import Repositories
from trip_journal.domain.grounding import Citation
from trip_journal.domain.journal_merge import Paragraph, Tone, mark_user_edit, merge_journal


@given(journal_cases(), journal_texts)
def test_merge_and_edit(case: tuple[list[str], list[Paragraph], dict[str, str]], edit: str) -> None:
    order, existing, draft = case
    old = {p.slot: p for p in existing}
    merged = merge_journal(existing, draft, order)
    assert [p.slot for p in merged.paragraphs] == order
    assert merged.nothing_to_regenerate == all(s in old and old[s].owner == "user" for s in order)
    for p in merged.paragraphs:
        previous = old.get(p.slot)
        if previous and previous.owner == "user":
            assert p == previous
        else:
            assert p.owner == "generated"
            assert p.text == draft.get(p.slot, previous.text if previous else "")
    assert merge_journal(merged.paragraphs, draft, order) == merged
    for target in merged.paragraphs:
        edited = mark_user_edit(merged.paragraphs, target.slot, edit)
        for before, after in zip(merged.paragraphs, edited, strict=True):
            if before.slot == target.slot and edit != target.text:
                assert after == Paragraph(slot=target.slot, text=edit, owner="user")
            else:
                assert before == after


@given(journal_outputs())
def test_parser_keeps_only_requested(output: str) -> None:
    draft = parse_journal_output(output, ["summary", "stop:1"], ["stop:1"], allow_empty=True)
    assert set(draft.slots) <= {"summary"}
    assert len(draft.slots) == len(set(draft.slots))


@given(journal_stop_sizes)
def test_chunks(sizes: list[int]) -> None:
    chunks = chunk_stops(list(enumerate(sizes)))
    assert [s for chunk in chunks for s in chunk] == list(range(len(sizes)))
    assert all(
        1 <= len(c) <= 6 and (len(c) == 1 or sum(sizes[s] for s in c) <= 4000) for c in chunks
    )


@given(
    journal_cases(),
    st.sampled_from(["casual", "concise", "detailed"]),
    st.lists(st.integers(1, 999), max_size=6),
)
def test_round_trip(
    case: tuple[list[str], list[Paragraph], dict[str, str]], tone: Tone, ids: list[int]
) -> None:
    order, existing, draft = case
    with closing(connect(":memory:")) as conn:
        init_schema(conn)
        repos = Repositories.from_connection(conn)
        trip = repos.trips.add("source", "Title")
        repo = repos.journals
        day = "2026-06-01"
        repo.save_generated(
            trip, day, order, {p.slot: p.text for p in existing}, "casual", [], "v", "fake"
        )
        for p in existing:
            if p.owner == "user":
                repo.save_user_edit(trip, day, p.slot, p.text + "x")
                repo.save_user_edit(trip, day, p.slot, p.text)
        trace = [
            ToolCallRecord(
                step=0,
                group="prefetch",
                name="get_stop_notes",
                arguments={"stop_id": 1},
                returned_ids=[Citation("note", i) for i in ids],
            )
        ]
        repo.save_generated(trip, day, order, draft, tone, trace, "v2", "fake")
        journal = repo.get(trip, day)
        assert journal and journal.paragraphs == merge_journal(existing, draft, order).paragraphs
        assert (journal.tone, journal.trace, journal.prompt_version, journal.model_name) == (
            tone,
            trace,
            "v2",
            "fake",
        )
