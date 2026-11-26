# ADDED [PROMPT #13]: agent loop tests (AL-1..AL-8, US-19, US-20). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import httpx
import openai
import pytest

from tests.conftest import Seed
from trip_journal.agent.llm import FakeLLMClient, LLMReply, ToolCall
from trip_journal.agent.loop import NOT_RUN_MESSAGE, AgentLoop, strip_think, trace_arguments
from trip_journal.agent.tools import ToolContext, default_registry
from trip_journal.data.repositories import Repositories
from trip_journal.domain.grounding import Citation
from trip_journal.services.errors import ModelCallError


@pytest.fixture
def ctx(repos: Repositories, seed: Seed) -> ToolContext:
    return ToolContext(trip_id=seed.trip_id, repos=repos, places=None)  # type: ignore[arg-type]


def call(name: str, args: str, id_: str | None = "c1") -> LLMReply:
    return LLMReply(content=None, tool_calls=[ToolCall(id=id_, name=name, arguments_json=args)])


def test_strip_think_and_trace_arguments() -> None:
    assert strip_think("<think>\nhidden\n</think>Answer") == "Answer"
    assert strip_think(None) is None
    assert trace_arguments('{"day": "2026-06-01"}') == {"day": "2026-06-01"}
    assert trace_arguments("x" * 500) == {"_raw": "x" * 200}


async def test_tool_then_final_answer(ctx: ToolContext, seed: Seed) -> None:
    llm = FakeLLMClient(
        [call("list_day_stops", '{"day": "2026-06-01"}'), LLMReply(content="<think>x</think>Done")]
    )
    steps: list[str] = []
    result = await AgentLoop(llm, default_registry()).run(
        "sys", [{"role": "user", "content": "hi"}], ctx, on_step=steps.append
    )
    assert result.stopped_reason == "final_answer" and result.final_text == "Done"
    assert [r.name for r in result.trace] == ["list_day_stops"]
    assert result.trace[0].returned_ids == [Citation("stop", s) for s in seed.stops]
    second = llm.calls[1]
    assert second[0] == {"role": "system", "content": "sys"}
    assert second[-1]["role"] == "tool" and second[-1]["tool_call_id"] == "c1"
    assert second[-2]["tool_calls"][0]["function"]["name"] == "list_day_stops"
    assert llm.tools_seen[0] is not None and len(llm.tools_seen[0]) == 5
    assert any("calling list_day_stops" in s for s in steps)


async def test_missing_call_id_is_generated(ctx: ToolContext) -> None:
    llm = FakeLLMClient(
        [call("list_day_stops", '{"day": "2026-06-01"}', None), LLMReply(content="ok")]
    )
    await AgentLoop(llm, default_registry()).run("s", [], ctx)
    assert llm.calls[1][-1]["tool_call_id"] == "call_1_0"


async def test_step_limit_records_not_run(ctx: ToolContext) -> None:
    llm = FakeLLMClient([call("list_day_stops", '{"day": "2026-06-01"}')] * 3)
    result = await AgentLoop(llm, default_registry(), max_steps=3).run("s", [], ctx)
    assert result.stopped_reason == "step_limit" and result.final_text is None
    assert len(result.trace) == 3
    last = result.trace[-1]
    assert last.error is not None and last.error.kind == "not_run"
    assert last.error.message == NOT_RUN_MESSAGE
    assert len(llm.calls) == 3


async def test_bad_tool_call_is_fed_back_not_raised(ctx: ToolContext) -> None:
    llm = FakeLLMClient([call("nope", "{}"), LLMReply(content="sorry")])
    result = await AgentLoop(llm, default_registry()).run("s", [], ctx)
    assert result.final_text == "sorry"
    assert result.trace[0].error is not None and result.trace[0].error.kind == "unknown_tool"
    assert "unknown_tool" in llm.calls[1][-1]["content"]


async def test_model_timeout_keeps_trace(ctx: ToolContext) -> None:
    llm = FakeLLMClient(
        [call("list_day_stops", '{"day": "2026-06-01"}'), LLMReply(content="x")], delay_s=0
    )
    loop = AgentLoop(llm, default_registry(), call_timeout_s=0.05)
    llm.delay_s = 0
    # first call returns, second hangs past the timeout
    original = llm.chat

    async def slow_second(*args, **kwargs):  # type: ignore[no-untyped-def]
        if llm.calls:
            llm.delay_s = 1
        return await original(*args, **kwargs)

    llm.chat = slow_second  # type: ignore[method-assign]
    with pytest.raises(ModelCallError) as info:
        await loop.run("s", [], ctx)
    assert info.value.reason == "timeout"
    assert [r.name for r in info.value.trace] == ["list_day_stops"]


async def test_api_error_maps_to_model_error(ctx: ToolContext) -> None:
    request = httpx.Request("POST", "http://localhost:11434/v1/chat/completions")
    response = httpx.Response(500, request=request)
    # openai 3.x annotates httpx2.Response; the httpx object works at runtime.
    error = openai.APIStatusError("boom", response=response, body=None)  # type: ignore[arg-type]
    llm = FakeLLMClient([error])
    with pytest.raises(ModelCallError) as info:
        await AgentLoop(llm, default_registry()).run("s", [], ctx)
    assert info.value.reason == "error"


async def test_failing_callback_does_not_stop_loop(ctx: ToolContext) -> None:
    def bad(_: object) -> None:
        raise RuntimeError("ui gone")

    llm = FakeLLMClient([LLMReply(content="fine")])
    result = await AgentLoop(llm, default_registry()).run("s", [], ctx, on_step=bad)
    assert result.final_text == "fine"
