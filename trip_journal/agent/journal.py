# ADDED [PROMPT #36]: journal planning, step-zero tool history, and multi-part generation.
import json
import logging
import re
from collections import Counter
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel

from trip_journal.agent.llm import LLMClient, ToolCall
from trip_journal.agent.loop import AgentLoop, ToolCallRecord
from trip_journal.agent.prompts import PromptLibrary
from trip_journal.agent.tools import ToolContext, ToolRegistry
from trip_journal.config import (
    JOURNAL_CALL_TIMEOUT_S,
    JOURNAL_CHUNK_MAX_CHARS,
    JOURNAL_CHUNK_MAX_STOPS,
    JOURNAL_REASONING_EFFORT,
)
from trip_journal.domain.journal_merge import Tone, parse_slot, stop_slot
from trip_journal.logs import kv
from trip_journal.services.errors import AgentStepLimitError, ModelCallError

log = logging.getLogger(__name__)
type DropReason = Literal["duplicate", "unknown_slot", "user_owned", "not_requested"]
type Message = dict[str, Any]
EMPTY_DRAFT = "The agent did not write any paragraph."


class DroppedHeading(BaseModel):
    heading: str
    reason: DropReason


class JournalDraft(BaseModel):
    slots: dict[str, str] = {}
    dropped: list[DroppedHeading] = []
    trace: list[ToolCallRecord] = []
    stopped_reason: Literal["final_answer", "step_limit"] = "final_answer"


def chunk_stops(
    stops_with_chars: Sequence[tuple[int, int]],
    max_stops: int = JOURNAL_CHUNK_MAX_STOPS,
    max_chars: int = JOURNAL_CHUNK_MAX_CHARS,
) -> list[list[int]]:
    chunks: list[list[int]] = []
    chars = 0
    for stop, size in stops_with_chars:
        if not chunks or len(chunks[-1]) >= max_stops or chars + size > max_chars:
            chunks.append([])
            chars = 0
        chunks[-1].append(stop)
        chars += size
    return chunks


@dataclass
class ChunkPlan:
    chunks: list[list[int]]

    @property
    def planned_calls(self) -> int:
        return len(self.chunks) + int(len(self.chunks) >= 2)


def parse_journal_output(
    text: str, requested: Collection[str], user_owned: Collection[str], *, allow_empty: bool = False
) -> JournalDraft:
    clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    sections = re.split(r"^[^\S\n]*##[^\S\n]*([^\n]+?)[^\S\n]*$", clean, flags=re.MULTILINE)
    draft = JournalDraft()
    seen: set[str] = set()
    for heading, body in zip(sections[1::2], sections[2::2], strict=True):
        slot = parse_slot(heading)
        reason: DropReason | None = None
        if slot is None:
            reason = "unknown_slot"
        elif slot in seen:
            reason = "duplicate"
        elif slot in user_owned:
            reason = "user_owned"
        elif slot not in requested:
            reason = "not_requested"
        elif body.strip():
            draft.slots[slot] = re.sub(r"\A(?:[^\S\n]*\n)+|(?:\n[^\S\n]*)+\Z", "", body)
        if slot is not None:
            seen.add(slot)
        if reason:
            draft.dropped.append(DroppedHeading(heading=heading, reason=reason))
    for why, count in Counter(d.reason for d in draft.dropped).items():
        log.info(kv("journal.drop", reason=why, count=count))
    if not draft.slots and not allow_empty:
        raise ModelCallError(EMPTY_DRAFT)
    return draft


@dataclass
class Prefetched:
    call: Message
    result: Message


async def build_prefetch(
    context: ToolContext,
    day: str,
    stops: Sequence[int],
    registry: ToolRegistry,
    record: Callable[[ToolCallRecord], None],
) -> dict[int | None, Prefetched]:
    loaded: dict[int | None, Prefetched] = {}
    keys: list[int | None] = [None, *stops]
    for i, stop in enumerate(keys):
        name = "list_day_stops" if stop is None else "get_stop_notes"
        arguments = {"day": day} if stop is None else {"stop_id": stop}
        call_id = f"prefetch-{i}"
        raw = json.dumps(arguments)
        outcome = await registry.execute(
            ToolCall(id=call_id, name=name, arguments_json=raw), context
        )
        record(
            ToolCallRecord(
                step=0,
                group="prefetch",
                name=name,
                arguments=arguments,
                returned_ids=outcome.returned_ids,
                error=outcome.error,
            )
        )
        loaded[stop] = Prefetched(
            {"id": call_id, "type": "function", "function": {"name": name, "arguments": raw}},
            {"role": "tool", "tool_call_id": call_id, "content": outcome.content},
        )
    return loaded


class JournalAgent:
    def __init__(self, llm: LLMClient, registry: ToolRegistry, prompts: PromptLibrary) -> None:
        self.calls = 0
        self.registry = registry
        self.prompts = prompts
        self.loop = AgentLoop(
            llm,
            registry,
            reasoning_effort=JOURNAL_REASONING_EFFORT,
            call_timeout_s=JOURNAL_CALL_TIMEOUT_S,
            request_timeout_s=JOURNAL_CALL_TIMEOUT_S,
        )

    def prompt(self, tone: Tone, summary: bool = False) -> str:
        prompt = (
            self.prompts.get("journal")
            + "\n\n"
            + self.prompts.get(f"journal_tone_{tone}", shared=False)
        )
        if summary:
            prompt += "\n\n" + self.prompts.get("journal_summary", shared=False)
        return prompt

    async def write_day(
        self,
        context: ToolContext,
        day: str,
        tone: Tone,
        plan: ChunkPlan,
        slots_to_write: Sequence[str],
        user_paragraphs: Mapping[str, str],
        stored_paragraphs: Mapping[str, str],
        on_progress: Callable[[str], None],
        on_tool_call: Callable[[ToolCallRecord], None] | None = None,
    ) -> JournalDraft:
        self.calls = 0
        draft = JournalDraft()

        def record(row: ToolCallRecord) -> None:
            draft.trace.append(row)
            if on_tool_call:
                on_tool_call(row)

        on_progress("Loading the day's records…")
        start = perf_counter()
        stops = [s for chunk in plan.chunks for s in chunk]
        loaded = await build_prefetch(context, day, stops, self.registry, record)
        log.info(
            kv(
                "journal.prefetch",
                stops=len(stops),
                duration_ms=round((perf_counter() - start) * 1000),
            )
        )
        total = len(plan.chunks)
        for i, chunk in enumerate(plan.chunks, 1):
            requested = [stop_slot(s) for s in chunk if stop_slot(s) in slots_to_write]
            if total == 1 and "summary" in slots_to_write:
                requested.insert(0, "summary")
            if not requested:
                continue
            data = {
                "day": day,
                "slots_to_write": requested,
                "traveller_paragraphs": user_paragraphs,
            }
            entries = [loaded[None], *(loaded[s] for s in chunk)]
            history: list[Message] = [
                {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
                {"role": "assistant", "content": "", "tool_calls": [e.call for e in entries]},
                *(e.result for e in entries),
            ]
            await self._part(
                context,
                tone,
                history,
                requested,
                user_paragraphs,
                draft,
                record,
                on_progress,
                i,
                total,
                len(chunk),
            )
        if total >= 2 and "summary" in slots_to_write:
            paragraphs = {**stored_paragraphs, **draft.slots}
            paragraphs.pop("summary", None)
            history = [
                {
                    "role": "user",
                    "content": json.dumps(
                        {"day": day, "slots_to_write": ["summary"], "stop_paragraphs": paragraphs},
                        ensure_ascii=False,
                    ),
                }
            ]
            await self._part(
                context,
                tone,
                history,
                ["summary"],
                user_paragraphs,
                draft,
                record,
                on_progress,
                0,
                total,
                0,
            )
        if not draft.slots:
            raise ModelCallError(EMPTY_DRAFT, list(draft.trace))
        return draft

    async def _part(
        self,
        context: ToolContext,
        tone: Tone,
        history: list[Message],
        requested: list[str],
        owned: Collection[str],
        draft: JournalDraft,
        record: Callable[[ToolCallRecord], None],
        progress: Callable[[str], None],
        index: int,
        total: int,
        stops: int,
    ) -> None:
        group = f"part {index}" if index else "summary"
        steps = 0
        written = 0
        outcome = "failed"
        started = perf_counter()

        def step(message: str) -> None:
            nonlocal steps
            if message.endswith("asking the model"):
                steps += 1
                self.calls += 1
                if not index:
                    progress("Writing the summary…")
                elif total == 1:
                    progress("Writing the journal…")
                else:
                    progress(f"Part {index} of {total}: writing…")

        def tool(row: ToolCallRecord) -> None:
            row.group = group
            record(row)
            prefix = f"Part {index} of {total}, step" if index and total > 1 else "Step"
            progress(f"{prefix} {row.step} of 8: {row.name}")

        try:
            result = await self.loop.run(
                self.prompt(tone, summary=not index), history, context, step, tool
            )
            if result.stopped_reason == "step_limit":
                raise AgentStepLimitError(list(draft.trace))
            part = parse_journal_output(result.final_text or "", requested, owned, allow_empty=True)
            draft.slots.update(part.slots)
            draft.dropped.extend(part.dropped)
            written = len(part.slots)
            outcome = "ok"
        except ModelCallError as exc:
            exc.trace = list(draft.trace)
            raise
        finally:
            log.info(
                kv(
                    "journal.chunk",
                    chunk=f"{index}/{total}" if index else "summary",
                    stops=stops,
                    slots_written=written,
                    steps=steps,
                    duration_ms=round((perf_counter() - started) * 1000),
                    outcome=outcome,
                )
            )
