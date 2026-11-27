# ADDED [PROMPT #25]: NoteOrganizer, one model call per batch (C15, OR-V1..V8, N-1..N-3).
# AI-assisted, Claude Opus 5.5.
"""Build the organizer messages, call the model once, and parse the reply item by item.

The model sees short labels (`s1`, `n1`), never database ids (Q9 A). No retries (AL-8).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import openai

from trip_journal.agent.llm import LLMClient
from trip_journal.agent.loop import strip_think
from trip_journal.agent.prompts import PromptLibrary
from trip_journal.agent.tools import DATA_LINE
from trip_journal.config import ORGANIZER_CALL_TIMEOUT_S, ORGANIZER_REASONING_EFFORT
from trip_journal.domain.days import local_hm, timed_order
from trip_journal.domain.organizer import (
    DISH_MAX,
    TIP_MAX,
    UNNAMED_STOP,
    BatchInput,
    BatchOutcome,
    DroppedItem,
    FieldError,
    NoteSuggestion,
    OrganizerBatchResult,
    OrganizerReply,
    clean_category,
    clean_rating,
    clean_text,
    cut_note_text,
)

log = logging.getLogger(__name__)

PROMPT_NAME = "organizer"
NO_STOP = "none"

# N-3 / Q8 A: Ollama constrains the reply to this schema.
RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {"name": "organizer_reply", "schema": OrganizerReply.model_json_schema()},
}


@dataclass(frozen=True)
class Labels:
    """Label <-> id maps for one batch."""

    stop_ids: dict[str, int]  # "s1" -> stop id
    note_ids: dict[str, int]  # "n1" -> note id
    stop_labels: dict[int, str]  # stop id -> "s1"


def make_labels(batch: BatchInput) -> Labels:
    """Stops `s1..sM` by (start_utc, id); notes `n1..nK` in time order (timed_order)."""
    stops = sorted(batch.stops, key=lambda s: (s.start_utc, s.id))
    notes = sorted(batch.notes, key=timed_order)
    stop_ids = {f"s{i}": s.id for i, s in enumerate(stops, start=1)}
    return Labels(
        stop_ids=stop_ids,
        note_ids={f"n{i}": n.id for i, n in enumerate(notes, start=1)},
        stop_labels={sid: label for label, sid in stop_ids.items()},
    )


def escape_note(text: str) -> str:
    """A note cannot close its own `<note>` or the `<trip_data>` block."""
    return text.replace("</", "<\\/")


def build_user_message(batch: BatchInput, labels: Labels | None = None) -> str:
    labels = labels or make_labels(batch)
    stops = {s.id: s for s in batch.stops}
    lines = [f"Day: {batch.day}", "<trip_data>", "Stops:"]
    for label, sid in labels.stop_ids.items():
        stop = stops[sid]
        start = local_hm(stop.start_utc, stop.utc_offset_minutes)
        end = local_hm(stop.end_utc, stop.utc_offset_minutes)
        name = escape_note(stop.name) if stop.name else UNNAMED_STOP
        lines.append(f"{label} | {name} | {start}-{end}")
    if not labels.stop_ids:
        lines.append("(no stops on this day)")
    lines.append("Notes:")
    notes = {n.id: n for n in batch.notes}
    for label, nid in labels.note_ids.items():
        note = notes[nid]
        stop_label = NO_STOP
        if note.stop_id is not None:
            stop_label = labels.stop_labels.get(note.stop_id, NO_STOP)
        lines.append(f"{label} | {local_hm(note.time_utc, note.utc_offset_minutes)} | {stop_label}")
        lines.append(f'<note id="{label}">{escape_note(cut_note_text(note.text))}</note>')
    lines.append("</trip_data>")
    lines.append(DATA_LINE)
    return "\n".join(lines)


def build_messages(batch: BatchInput, prompts: PromptLibrary) -> list[dict[str, Any]]:
    """System prompt without the shared tool-data text (D-15), then the data block."""
    return [
        {"role": "system", "content": prompts.get(PROMPT_NAME, shared=False)},
        {"role": "user", "content": build_user_message(batch)},
    ]


def failed_batch(batch: BatchInput, outcome: BatchOutcome) -> OrganizerBatchResult:
    """OR-V6: every note of the batch is not organized, with the batch's reason."""
    return OrganizerBatchResult(
        suggestions=[],
        dropped=[],
        not_organized=[n.id for n in sorted(batch.notes, key=timed_order)],
        outcome=outcome,
    )


def _check_item(item: object, labels: Labels) -> tuple[NoteSuggestion | None, DroppedItem | None]:
    if not isinstance(item, dict):
        return None, DroppedItem(note_label=None, note_id=None, reason="item is not an object")
    raw_note = item.get("note")
    note_label = raw_note if isinstance(raw_note, str) else None
    note_id = labels.note_ids.get(raw_note) if isinstance(raw_note, str) else None
    if note_id is None:  # OR-V1
        return None, DroppedItem(
            note_label=note_label, note_id=None, reason=f"unknown note label {raw_note!r}"
        )

    def drop(reason: str) -> tuple[None, DroppedItem]:
        return None, DroppedItem(note_label=note_label, note_id=note_id, reason=reason)

    raw_stop = item.get("stop")
    stop_id: int | None = None
    if raw_stop is not None:  # OR-V3
        found = labels.stop_ids.get(raw_stop) if isinstance(raw_stop, str) else None
        if found is None:
            return drop(f"unknown stop label {raw_stop!r}")
        stop_id = found
    try:  # OR-V2, OR-V4
        category = clean_category(item.get("category"))
        dish = clean_text(item.get("dish"), DISH_MAX, "dish")
        rating = clean_rating(item.get("rating"))
        tip = clean_text(item.get("tip"), TIP_MAX, "tip")
    except FieldError as exc:
        return drop(str(exc))
    return (
        NoteSuggestion(
            note_id=note_id,
            category=category,
            suggested_stop_id=stop_id,
            dish=dish,
            rating=rating,
            tip=tip,
        ),
        None,
    )


def parse_reply(text: str | None, batch: BatchInput) -> OrganizerBatchResult:
    """AL-9 clean, then OR-V1..V8. Never raises; every note is kept or not organized."""
    cleaned = strip_think(text)
    if not cleaned:
        return failed_batch(batch, "empty_reply")
    try:
        data = json.loads(cleaned)
    except ValueError:
        return failed_batch(batch, "invalid_json")
    if not isinstance(data, dict) or not isinstance(data.get("suggestions"), list):
        return failed_batch(batch, "invalid_json")
    labels = make_labels(batch)
    kept: dict[int, NoteSuggestion] = {}
    dropped: list[DroppedItem] = []
    for item in data["suggestions"]:
        suggestion, problem = _check_item(item, labels)
        if problem is not None:
            dropped.append(problem)
        elif suggestion is not None:
            if suggestion.note_id in kept:  # OR-V5, D-19: only kept items count
                dropped.append(
                    DroppedItem(
                        note_label=item["note"], note_id=suggestion.note_id, reason="duplicate"
                    )
                )
            else:
                kept[suggestion.note_id] = suggestion
    order = list(labels.note_ids.values())
    return OrganizerBatchResult(
        suggestions=[kept[nid] for nid in order if nid in kept],
        dropped=dropped,
        not_organized=[nid for nid in order if nid not in kept],
    )


class NoteOrganizer:
    def __init__(
        self,
        llm: LLMClient,
        prompts: PromptLibrary,
        call_timeout_s: float = ORGANIZER_CALL_TIMEOUT_S,
    ) -> None:
        self.llm = llm
        self.prompts = prompts
        self.call_timeout_s = call_timeout_s

    async def organize_batch(self, batch: BatchInput) -> OrganizerBatchResult:
        """One call (N-1 no thinking, N-2 own limit, N-3 schema). Cancel propagates."""
        messages = build_messages(batch, self.prompts)
        try:
            async with asyncio.timeout(self.call_timeout_s):  # D-3
                reply = await self.llm.chat(
                    messages,
                    tools=None,
                    response_format=RESPONSE_FORMAT,
                    reasoning_effort=ORGANIZER_REASONING_EFFORT,
                    timeout_s=self.call_timeout_s,
                )
        except (TimeoutError, openai.APITimeoutError):
            return failed_batch(batch, "call_timeout")
        except Exception as exc:  # model or HTTP error; details stay in the log type only
            log.warning("organizer.call_error type=%s", type(exc).__name__)
            return failed_batch(batch, "model_error")
        return parse_reply(reply.content, batch)
