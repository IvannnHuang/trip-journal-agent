# ADDED [PROMPT #13]: tool-calling agent loop (C11, AL-1..AL-11, NP-1).
# AI-assisted, Claude Opus 5.5.
"""Plain agent loop: ask the model, run the tools it asks for, repeat (at most 8 calls)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any, Literal

import openai
from pydantic import BaseModel

from trip_journal.agent.llm import LLMClient, LLMReply, ToolCall
from trip_journal.agent.tools import ToolContext, ToolError, ToolRegistry
from trip_journal.config import MAX_AGENT_STEPS, MAX_RAW_ARGUMENTS_CHARS, MODEL_CALL_TIMEOUT_S
from trip_journal.domain.grounding import Citation
from trip_journal.logs import kv
from trip_journal.services.errors import ModelCallError

log = logging.getLogger(__name__)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
NOT_RUN_MESSAGE = "not run: step limit reached"


class ToolCallRecord(BaseModel):
    # ADDED [PROMPT #36]: optional journal trace group, including step zero.
    group: str | None = None
    step: int
    name: str
    arguments: dict[str, Any]
    returned_ids: list[Citation] = []
    error: ToolError | None = None


class AgentResult(BaseModel):
    final_text: str | None
    trace: list[ToolCallRecord]
    stopped_reason: Literal["final_answer", "step_limit"]


StepCallback = Callable[[str], None]
ToolCallCallback = Callable[[ToolCallRecord], None]


def strip_think(text: str | None) -> str | None:
    """Remove `<think>…</think>` blocks and trim (AL-9)."""
    if text is None:
        return None
    return _THINK_RE.sub("", text).strip()


def trace_arguments(raw: str) -> dict[str, Any]:
    """Parsed arguments for the trace, or `{"_raw": first 200 chars}` (TA-2)."""
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    return {"_raw": raw[:MAX_RAW_ARGUMENTS_CHARS]}


def _safe(callback: Callable[[Any], None] | None, value: Any) -> None:
    """AL-11: a callback can never change or stop the loop."""
    if callback is None:
        return
    try:
        callback(value)
    except Exception:
        log.warning(kv("agent.callback_failed"), exc_info=True)


class AgentLoop:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        max_steps: int = MAX_AGENT_STEPS,
        call_timeout_s: float = MODEL_CALL_TIMEOUT_S,
        # ADDED [PROMPT #36]: optional per-request journal settings.
        reasoning_effort: str | None = None,
        request_timeout_s: float | None = None,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.max_steps = max_steps
        self.call_timeout_s = call_timeout_s
        # ADDED [PROMPT #36]: leave SDK defaults in effect for other agents.
        self.reasoning_effort = reasoning_effort
        self.request_timeout_s = request_timeout_s

    async def _call(self, messages: list[dict[str, Any]], trace: list[ToolCallRecord]) -> LLMReply:
        try:
            async with asyncio.timeout(self.call_timeout_s):
                # CHANGED [PROMPT #36]: forward request overrides.
                return await self.llm.chat(
                    messages,
                    tools=self.registry.schemas(),
                    reasoning_effort=self.reasoning_effort,
                    timeout_s=self.request_timeout_s,
                )
        except (TimeoutError, openai.APITimeoutError) as exc:
            raise ModelCallError("timeout", list(trace)) from exc
        except openai.APIError as exc:
            raise ModelCallError("error", list(trace)) from exc

    async def run(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        context: ToolContext,
        on_step: StepCallback | None = None,
        on_tool_call: ToolCallCallback | None = None,
    ) -> AgentResult:
        history: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}, *messages]
        trace: list[ToolCallRecord] = []
        for step in range(1, self.max_steps + 1):
            _safe(on_step, f"step {step}: asking the model")
            started = time.monotonic()
            reply = await self._call(history, trace)
            log.info(
                kv(
                    "agent.step",
                    step=step,
                    tool_calls=len(reply.tool_calls),
                    ms=int((time.monotonic() - started) * 1000),
                )
            )
            if not reply.tool_calls:  # AL-4
                return AgentResult(
                    final_text=strip_think(reply.content),
                    trace=trace,
                    stopped_reason="final_answer",
                )
            calls = [
                ToolCall(
                    id=c.id or f"call_{step}_{i}", name=c.name, arguments_json=c.arguments_json
                )
                for i, c in enumerate(reply.tool_calls)
            ]  # AL-7
            if step == self.max_steps:  # AL-2: the last reply still wants tools
                for call in calls:
                    record = ToolCallRecord(
                        step=step,
                        name=call.name,
                        arguments=trace_arguments(call.arguments_json),
                        error=ToolError(kind="not_run", message=NOT_RUN_MESSAGE),
                    )
                    trace.append(record)
                    _safe(on_tool_call, record)
                break
            history.append(
                {
                    "role": "assistant",
                    "content": strip_think(reply.content) or "",
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": c.arguments_json},
                        }
                        for c in calls
                    ],
                }
            )
            for call in calls:  # AL-3: in reply order
                _safe(on_step, f"step {step}: calling {call.name[:50]}")
                outcome = await self.registry.execute(call, context)
                record = ToolCallRecord(
                    step=step,
                    name=call.name,
                    arguments=trace_arguments(call.arguments_json),
                    returned_ids=outcome.returned_ids,
                    error=outcome.error,
                )
                trace.append(record)
                log.info(
                    kv(
                        "tool.call",
                        step=step,
                        tool=call.name[:50],
                        ids=len(outcome.returned_ids),
                        error=outcome.error.kind if outcome.error else "-",
                    )
                )
                _safe(on_tool_call, record)
                history.append(
                    {"role": "tool", "tool_call_id": call.id, "content": outcome.content}
                )
        return AgentResult(final_text=None, trace=trace, stopped_reason="step_limit")
