# ADDED [PROMPT #36]: offline full runs, chunk histories, partial drafts and failures.
import json

import pytest

from trip_journal.agent.llm import FakeLLMClient, LLMReply, ToolCall
from trip_journal.services.jobs import JobRef
from trip_journal.services.journal import JournalService

DAY = "2026-06-01"


async def test_full_draft(journal_service: JournalService, journal_trip: int) -> None:
    service = journal_service
    ids = [s.id for s in service.repos.stops.list_for_day(journal_trip, DAY)]
    replies = [
        LLMReply(content="\n".join(f"## stop:{s}\nStop [stop:{s}]." for s in group))
        for group in (ids[:6], ids[6:])
    ]
    llm = FakeLLMClient([*replies, LLMReply(content=f"## summary\nOverview [stop:{ids[0]}].")])
    service.llm_factory = lambda _: llm
    job = await service.start_generation(journal_trip, DAY, "casual")
    assert isinstance(job, JobRef)
    status = await service.jobs.wait(job.job_id)
    assert status.result and status.result["unsupported_count"] == 0
    assert len(status.result["paragraphs"]) == 9
    assert llm.timeouts == [300] * 3 and llm.reasoning_efforts == ["none"] * 3
    assert [r.step for r in status.trace] == [0] * 9
    assert [r.group for r in status.trace] == ["prefetch"] * 9
    assert [r.arguments["stop_id"] for r in status.trace[1:]] == ids
    for history, group in zip(llm.calls[:2], [ids[:6], ids[6:]], strict=True):
        assistant = history[2]
        assert assistant["role"] == "assistant"
        calls = assistant["tool_calls"]
        assert calls[0]["id"] == "prefetch-0"
        assert [json.loads(c["function"]["arguments"])["stop_id"] for c in calls[1:]] == group
        assert [m["tool_call_id"] for m in history[3:]] == [c["id"] for c in calls]
        assert all("<tool_result>" in m["content"] for m in history[3:])
    summary = json.loads(llm.calls[-1][1]["content"])
    assert list(summary["stop_paragraphs"]) == [f"stop:{i}" for i in ids]
    assert "Private note" not in str(llm.calls[-1])


# ADDED [PROMPT #36]: regeneration skips owned parts and summarizes preserved paragraphs.
async def test_summary_uses_stored_and_partial_parts(
    journal_service: JournalService, journal_trip: int
) -> None:
    service = journal_service
    ids = [s.id for s in service.repos.stops.list_for_day(journal_trip, DAY)]
    order = ["summary", *(f"stop:{s}" for s in ids)]
    service.repos.journals.save_generated(
        journal_trip, DAY, order, dict.fromkeys(order, "previous"), "casual", [], "v", "m"
    )
    for slot in order[1:7]:
        service.edit_paragraph(journal_trip, DAY, slot, "traveller")
    llm = FakeLLMClient(
        [LLMReply(content="## junk\ntext"), LLMReply(content="## summary\nTogether.")]
    )
    service.llm_factory = lambda _: llm
    job = await service.start_generation(journal_trip, DAY, "concise")
    assert isinstance(job, JobRef)
    result = await service.jobs.wait(job.job_id)
    assert result.result and "did not write 2 paragraphs" in result.result["message"]
    assert len(result.trace) == 9 and len(llm.calls) == 2
    summary = json.loads(llm.calls[-1][1]["content"])["stop_paragraphs"]
    assert summary == {s: "traveller" if s in order[1:7] else "previous" for s in order[1:]}
    assert json.loads(llm.calls[0][1]["content"])["slots_to_write"] == order[7:]


@pytest.mark.parametrize("failure", ["timeout", "step_limit", "empty", "summary_timeout"])
async def test_failed_regeneration_keeps_saved_rows(
    journal_service: JournalService, journal_trip: int, failure: str
) -> None:
    service = journal_service
    ids = [s.id for s in service.repos.stops.list_for_day(journal_trip, DAY)]
    order = ["summary", *(f"stop:{s}" for s in ids)]
    service.repos.journals.save_generated(
        journal_trip, DAY, order, {"summary": "saved"}, "detailed", [], "v", "m"
    )
    before = service.repos.journals.get(journal_trip, DAY)
    first = LLMReply(content=f"## stop:{ids[0]}\nwritten")
    tool = LLMReply(
        content=None, tool_calls=[ToolCall(id="err", name="unknown", arguments_json="{}")]
    )
    script: list[LLMReply | BaseException]
    if failure == "empty":
        script = [LLMReply(content="no sections")] * 3
    elif failure == "step_limit":
        script = [first, *([tool] * 8)]
    elif failure == "summary_timeout":
        script = [first, LLMReply(content="omitted"), TimeoutError()]
    else:
        script = [first, TimeoutError()]
    service.llm_factory = lambda _: FakeLLMClient(script)
    job = await service.start_generation(journal_trip, DAY, "casual")
    assert isinstance(job, JobRef)
    status = await service.jobs.wait(job.job_id)
    assert status.state == "failed" and status.error and status.error.trace == status.trace
    if failure == "step_limit":
        assert status.error.code == "step_limit" and status.trace[-1].group == "part 2"
    assert service.repos.journals.get(journal_trip, DAY) == before
