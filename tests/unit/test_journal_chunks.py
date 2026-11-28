# ADDED [PROMPT #36]: chunk boundaries and planner/tool character-count agreement.
from unittest.mock import patch

from trip_journal.agent.journal import build_prefetch, chunk_stops
from trip_journal.agent.tools import ToolContext, default_registry, unwrap_tool_result
from trip_journal.services.journal import JournalService, plan_day


def test_boundaries() -> None:
    assert chunk_stops([(i, 0) for i in range(7)]) == [list(range(6)), [6]]
    assert chunk_stops([(1, 3999), (2, 1), (3, 4001), (4, 0)]) == [[1, 2], [3], [4]]
    assert chunk_stops([]) == []


async def test_plan_matches_wrapped_records(
    journal_service: JournalService, journal_trip: int
) -> None:
    repos = journal_service.repos
    day = "2026-06-01"
    ids = [s.id for s in repos.stops.list_for_day(journal_trip, day)]
    for i in range(52):
        repos.notes.add(journal_trip, f"long{i}", "x" * 1200, day + "T01:01:00Z", 0, ids[0])
    ctx = ToolContext(journal_trip, repos, journal_service.places)
    with patch("trip_journal.services.journal.chunk_stops", wraps=chunk_stops) as split:
        plan = plan_day(repos, journal_trip, ids)
    loaded = await build_prefetch(ctx, day, ids, default_registry(), lambda _: None)
    expected = [
        (s, sum(len(r["text"]) for r in unwrap_tool_result(loaded[s].result["content"])["records"]))
        for s in ids
    ]
    assert split.call_args.args == (expected,)
    assert plan.chunks[0] == [ids[0]]
