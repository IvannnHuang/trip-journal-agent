# ADDED [PROMPT #36]: journal slots, ownership and deterministic merge rules.
import re
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel

type Slot = str
type Owner = Literal["generated", "user"]
type Tone = Literal["casual", "concise", "detailed"]


class Paragraph(BaseModel):
    slot: Slot
    text: str
    owner: Owner


class MergeResult(BaseModel):
    paragraphs: list[Paragraph]
    replaced_slots: list[Slot]
    missing_slots: list[Slot]
    nothing_to_regenerate: bool


def stop_slot(stop_id: int) -> Slot:
    return f"stop:{stop_id}"


def parse_slot(text: str) -> Slot | None:
    slot = "".join(text.lower().split())
    return slot if slot == "summary" or re.fullmatch(r"stop:[1-9][0-9]*", slot) else None


def slot_safe(slot: Slot) -> str:
    return slot.replace(":", "-")


def slot_order(stop_ids_in_timeline_order: Sequence[int]) -> list[Slot]:
    return ["summary", *map(stop_slot, stop_ids_in_timeline_order)]


def slots_to_write(existing: Sequence[Paragraph], order: Sequence[Slot]) -> list[Slot]:
    owned = {p.slot for p in existing if p.owner == "user"}
    return [slot for slot in order if slot not in owned]


def merge_journal(
    existing: Sequence[Paragraph], draft: Mapping[Slot, str], order: Sequence[Slot]
) -> MergeResult:
    by_slot = {p.slot: p for p in existing}
    todo = slots_to_write(existing, order)
    replaced = [slot for slot in todo if slot in draft]
    for slot in todo:
        if slot in draft or slot not in by_slot:
            by_slot[slot] = Paragraph(slot=slot, text=draft.get(slot, ""), owner="generated")
    return MergeResult(
        paragraphs=[by_slot[s] for s in order],
        replaced_slots=replaced,
        missing_slots=[s for s in todo if s not in draft],
        nothing_to_regenerate=not todo,
    )


def mark_user_edit(paragraphs: Sequence[Paragraph], slot: Slot, new_text: str) -> list[Paragraph]:
    return [
        Paragraph(slot=slot, text=new_text, owner="user")
        if p.slot == slot and p.text != new_text
        else p
        for p in paragraphs
    ]
