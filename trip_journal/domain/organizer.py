# ADDED [PROMPT #25]: U3 Note Organizer domain models and pure rules (C15, OR-F, OR-RUN2).
# AI-assisted, Claude Opus 5.5.
"""Organizer values, field rules, batching and the review view.

Nothing here talks to the model or the database. `check_edit` returns its issues instead of
raising a service error, so the domain never imports services (D-21).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict

from trip_journal.config import (
    MAX_NOTE_CHARS,
    ORGANIZER_BATCH_MAX_CHARS,
    ORGANIZER_BATCH_MAX_NOTES,
    TRUNCATION_SUFFIX,
)
from trip_journal.domain.days import timed_order

if TYPE_CHECKING:
    from trip_journal.data.repositories import NoteRow, StopRow
    from trip_journal.data.suggestions import SuggestionRow

Category = Literal["food", "scene", "logistics", "feedback", "other"]
CATEGORIES: tuple[str, ...] = get_args(Category)
SuggestionStatus = Literal["pending", "accepted", "edited", "rejected"]
BatchOutcome = Literal["ok", "empty_reply", "invalid_json", "model_error", "call_timeout"]

DISH_MAX = 80
TIP_MAX = 200
PREVIEW_CHARS = 60
RATING_MIN = 1
RATING_MAX = 5
NO_STOP_LABEL = "No stop"
UNNAMED_STOP = "Unnamed place"
EDIT_FIELDS = ("category", "stop_id", "dish", "rating", "tip")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


# ---------- model output (the JSON schema sent as response_format, Q8 A) ----------


class ReplyItem(BaseModel):
    note: str
    category: Category
    stop: str | None
    dish: str | None
    rating: int | None
    tip: str | None


class OrganizerReply(BaseModel):
    suggestions: list[ReplyItem]


# ---------- parsed results ----------


class NoteSuggestion(_Frozen):
    """One kept item after label mapping and OR-F checks (satisfies `SuggestedValues`)."""

    note_id: int
    category: Category
    suggested_stop_id: int | None
    dish: str | None
    rating: int | None
    tip: str | None


class DroppedItem(_Frozen):
    note_label: str | None
    note_id: int | None
    reason: str


class OrganizerBatchResult(_Frozen):
    suggestions: list[NoteSuggestion]
    dropped: list[DroppedItem]
    not_organized: list[int]
    outcome: BatchOutcome = "ok"


@dataclass(frozen=True)
class BatchInput:
    """One model call: a day's stops (all of them) and at most 10 of its notes."""

    day: str
    stops: tuple[StopRow, ...]
    notes: tuple[NoteRow, ...]


class NotOrganized(_Frozen):
    note_id: int
    local_time: str
    preview: str
    reason: str


class DayRunResult(BaseModel):
    day: str
    notes_sent: int = 0
    suggested: int = 0
    not_organized: list[NotOrganized] = []
    dropped: list[DroppedItem] = []
    failed_batches: int = 0


class OrganizerRunSummary(BaseModel):
    trip_id: int
    scope_day: str | None
    days: list[DayRunResult]
    total_suggested: int
    total_not_organized: int
    batches: int
    batches_failed: int
    skipped_decided: int
    prompt_version: str
    model_name: str
    stopped: str | None = None  # "job_timeout" when the inner deadline ended the run (D-13)
    remaining_notes: int = 0


# ---------- review view ----------


class SuggestionValues(_Frozen):
    category: str
    stop_id: int | None
    dish: str | None
    rating: int | None
    tip: str | None


class OrganizedFields(_Frozen):
    suggestion_id: int
    category: str
    stop_id: int | None
    dish: str | None
    rating: int | None
    tip: str | None
    edited: bool


class SuggestionView(_Frozen):
    suggestion_id: int
    trip_id: int
    local_date: str
    note_id: int
    note_source_id: str
    status: SuggestionStatus
    category: str
    stop_id: int | None
    stop_source_id: str | None
    stop_label: str
    dish: str | None
    rating: int | None
    tip: str | None
    model_values: SuggestionValues


class SuggestionEdit(_Frozen):
    model_config = ConfigDict(frozen=True, extra="forbid")

    category: Category
    stop_id: int | None = None
    dish: str | None = None
    rating: int | None = None
    tip: str | None = None


# ---------- field rules (OR-F1..F4) ----------


class FieldError(ValueError):
    """One field's rule failed; the message is the drop reason or the form message."""


def clean_text(value: object, limit: int, name: str) -> str | None:
    """OR-F2: trim; empty -> None; longer than `limit` is an error."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise FieldError(f"{name} must be text")
    text = value.strip()
    if not text:
        return None
    if len(text) > limit:
        raise FieldError(f"{name} longer than {limit} characters")
    return text


def clean_rating(value: object) -> int | None:
    """OR-F3: a whole number 1-5; `4.0` is accepted, strings, bools and fractions are not."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise FieldError("rating must be a whole number")
    if isinstance(value, float):
        if not value.is_integer():
            raise FieldError("rating must be a whole number")
        value = int(value)
    if not RATING_MIN <= value <= RATING_MAX:
        raise FieldError(f"rating {value} outside {RATING_MIN}-{RATING_MAX}")
    return value


def clean_category(value: object) -> Category:
    """OR-F4 / OR-V2: one of the five values, exact and lower case."""
    if isinstance(value, str) and value in CATEGORIES:
        return value  # type: ignore[return-value]  # narrowed by the membership check
    raise FieldError(f"category {value!r} not allowed")


def check_edit(
    raw: Mapping[str, Any], stop_ids: Sequence[int]
) -> tuple[SuggestionEdit | None, dict[str, str]]:
    """OR-F* and OR-S1 for an edit. Returns the edit, or None with one message per field."""
    issues: dict[str, str] = {}
    for key in raw:
        if key not in EDIT_FIELDS:
            issues[str(key)] = "unknown field"
    values: dict[str, Any] = {}
    checks: dict[str, Any] = {
        "category": clean_category,
        "dish": lambda v: clean_text(v, DISH_MAX, "dish"),
        "rating": clean_rating,
        "tip": lambda v: clean_text(v, TIP_MAX, "tip"),
    }
    if "category" not in raw:
        issues["category"] = "category is required"
    for name, check in checks.items():
        if name in raw:
            try:
                values[name] = check(raw[name])
            except FieldError as exc:
                issues[name] = str(exc)
    stop = raw.get("stop_id")
    if stop is not None:
        if isinstance(stop, bool) or not isinstance(stop, int) or stop not in stop_ids:
            issues["stop_id"] = "stop is not one of this day's stops"
        else:
            values["stop_id"] = stop
    if issues:
        return None, issues
    return SuggestionEdit(**values), {}


# ---------- batching (OR-RUN2, N-4) ----------


def cut_note_text(text: str) -> str:
    """The text the prompt carries: at most 1,000 characters plus the marker (TA-7)."""
    if len(text) <= MAX_NOTE_CHARS:
        return text
    return text[:MAX_NOTE_CHARS] + TRUNCATION_SUFFIX


def plan_batches(
    notes: Sequence[NoteRow],
    max_notes: int = ORGANIZER_BATCH_MAX_NOTES,
    max_chars: int = ORGANIZER_BATCH_MAX_CHARS,
) -> list[list[NoteRow]]:
    """Time order; close a batch at `max_notes`, or before a note that would pass `max_chars`.

    A batch always holds at least one note, so a single long note still gets sent.
    """
    batches: list[list[NoteRow]] = []
    current: list[NoteRow] = []
    chars = 0
    for note in sorted(notes, key=timed_order):
        size = len(cut_note_text(note.text))
        if current and (len(current) >= max_notes or chars + size > max_chars):
            batches.append(current)
            current, chars = [], 0
        current.append(note)
        chars += size
    if current:
        batches.append(current)
    return batches


# ---------- views ----------


def model_values(row: SuggestionRow) -> SuggestionValues:
    return SuggestionValues(
        category=row.s_category,
        stop_id=row.s_stop_id,
        dish=row.s_dish,
        rating=row.s_rating,
        tip=row.s_tip,
    )


def effective_values(row: SuggestionRow) -> SuggestionValues:
    """The `f_*` set for an edited row, otherwise the model's `s_*` set."""
    if row.status == "edited":
        return SuggestionValues(
            category=row.f_category or row.s_category,
            stop_id=row.f_stop_id,
            dish=row.f_dish,
            rating=row.f_rating,
            tip=row.f_tip,
        )
    return model_values(row)


def organized_fields(row: SuggestionRow) -> OrganizedFields | None:
    """FR-3.4: only accepted and edited rows become organized note data."""
    if not row.organized:
        return None
    v = effective_values(row)
    return OrganizedFields(
        suggestion_id=row.id,
        category=v.category,
        stop_id=v.stop_id,
        dish=v.dish,
        rating=v.rating,
        tip=v.tip,
        edited=row.status == "edited",
    )


def stop_label(stop: StopRow | None) -> str:
    if stop is None:
        return NO_STOP_LABEL
    return stop.name or UNNAMED_STOP


def suggestion_view(
    row: SuggestionRow, note: NoteRow, stops_by_id: Mapping[int, StopRow]
) -> SuggestionView:
    v = effective_values(row)
    stop = stops_by_id.get(v.stop_id) if v.stop_id is not None else None
    status: SuggestionStatus = row.status  # type: ignore[assignment]  # CHECK in schema.sql
    return SuggestionView(
        suggestion_id=row.id,
        trip_id=row.trip_id,
        local_date=note.local_date,
        note_id=note.id,
        note_source_id=note.source_id,
        status=status,
        category=v.category,
        stop_id=v.stop_id,
        stop_source_id=stop.source_id if stop else None,
        stop_label=stop_label(stop),
        dish=v.dish,
        rating=v.rating,
        tip=v.tip,
        model_values=model_values(row),
    )
