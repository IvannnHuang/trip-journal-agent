# ADDED [PROMPT #25]: SuggestionRepository for table note_suggestions (U3 IC-6, IC-8).
# AI-assisted, Claude Opus 5.5.
"""One suggestion row per note (FA-1). Nothing here writes the `notes` table (OR-R1)."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

DECIDED = ("accepted", "edited", "rejected")


def utc_now_text() -> str:
    """Same format as `repositories.utc_now_text` (kept here so the import has no cycle)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class SuggestionRow:
    id: int
    trip_id: int
    note_id: int
    status: str
    s_category: str
    s_stop_id: int | None
    s_dish: str | None
    s_rating: int | None
    s_tip: str | None
    f_category: str | None
    f_stop_id: int | None
    f_dish: str | None
    f_rating: int | None
    f_tip: str | None
    prompt_version: str
    model_name: str
    created_at: str
    decided_at: str | None

    @property
    def organized(self) -> bool:
        return self.status in ("accepted", "edited")

    @property
    def effective_stop_id(self) -> int | None:
        """The stop an organized row places its note under (OR-S2)."""
        return self.f_stop_id if self.status == "edited" else self.s_stop_id


class SuggestedValues(Protocol):
    """What `save_batch` needs from each suggestion (domain NoteSuggestion)."""

    @property
    def note_id(self) -> int: ...
    @property
    def category(self) -> str: ...
    @property
    def suggested_stop_id(self) -> int | None: ...
    @property
    def dish(self) -> str | None: ...
    @property
    def rating(self) -> int | None: ...
    @property
    def tip(self) -> str | None: ...


@dataclass(frozen=True)
class FinalValues:
    category: str
    stop_id: int | None
    dish: str | None
    rating: int | None
    tip: str | None


class SuggestionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def save_batch(
        self,
        trip_id: int,
        suggestions: Sequence[SuggestedValues],
        prompt_version: str,
        model_name: str,
        commit: bool = True,
    ) -> int:
        """OR-SAVE1 / FA-3: insert, or replace a pending row; a decided row is skipped.

        The status check is inside the statement, so it holds within the caller's
        transaction. Returns the number of rows written.
        """
        now = utc_now_text()
        written = 0
        for s in suggestions:
            cur = self.conn.execute(
                "INSERT INTO note_suggestions (trip_id, note_id, status, s_category, s_stop_id,"
                " s_dish, s_rating, s_tip, prompt_version, model_name, created_at)"
                " VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(note_id) DO UPDATE SET s_category = excluded.s_category,"
                " s_stop_id = excluded.s_stop_id, s_dish = excluded.s_dish,"
                " s_rating = excluded.s_rating, s_tip = excluded.s_tip,"
                " prompt_version = excluded.prompt_version, model_name = excluded.model_name,"
                " created_at = excluded.created_at"
                " WHERE note_suggestions.status = 'pending'",
                (
                    trip_id,
                    s.note_id,
                    s.category,
                    s.suggested_stop_id,
                    s.dish,
                    s.rating,
                    s.tip,
                    prompt_version,
                    model_name,
                    now,
                ),
            )
            written += cur.rowcount
        if commit:
            self.conn.commit()
        return written

    def get(self, suggestion_id: int) -> SuggestionRow | None:
        row = self.conn.execute(
            "SELECT * FROM note_suggestions WHERE id = ?", (suggestion_id,)
        ).fetchone()
        return SuggestionRow(**dict(row)) if row else None

    def list_for_trip(self, trip_id: int) -> list[SuggestionRow]:
        rows = self.conn.execute(
            "SELECT * FROM note_suggestions WHERE trip_id = ? ORDER BY note_id", (trip_id,)
        )
        return [SuggestionRow(**dict(r)) for r in rows]

    def list_for_day(self, trip_id: int, day: str) -> list[SuggestionRow]:
        rows = self.conn.execute(
            "SELECT s.* FROM note_suggestions s JOIN notes n ON n.id = s.note_id"
            " WHERE s.trip_id = ? AND n.local_date = ? ORDER BY n.time_utc, n.source_id",
            (trip_id, day),
        )
        return [SuggestionRow(**dict(r)) for r in rows]

    def set_status(
        self,
        suggestion_id: int,
        status: str,
        final: FinalValues | None = None,
        commit: bool = True,
    ) -> None:
        """pending -> accepted / edited / rejected. `final` is stored only for edited."""
        f = final if status == "edited" else None
        self.conn.execute(
            "UPDATE note_suggestions SET status = ?, f_category = ?, f_stop_id = ?, f_dish = ?,"
            " f_rating = ?, f_tip = ?, decided_at = ? WHERE id = ?",
            (
                status,
                f.category if f else None,
                f.stop_id if f else None,
                f.dish if f else None,
                f.rating if f else None,
                f.tip if f else None,
                utc_now_text(),
                suggestion_id,
            ),
        )
        if commit:
            self.conn.commit()

    def undo(self, suggestion_id: int, commit: bool = True) -> None:
        """Back to pending with the model values; `f_*` and `decided_at` cleared (Q3 A)."""
        self.conn.execute(
            "UPDATE note_suggestions SET status = 'pending', f_category = NULL,"
            " f_stop_id = NULL, f_dish = NULL, f_rating = NULL, f_tip = NULL,"
            " decided_at = NULL WHERE id = ?",
            (suggestion_id,),
        )
        if commit:
            self.conn.commit()

    def accept_all_pending(self, trip_id: int, note_ids: Sequence[int], commit: bool = True) -> int:
        """OR-AA1: the given notes' pending rows become accepted. Returns the count."""
        if not note_ids:
            return 0
        marks = ",".join("?" for _ in note_ids)
        cur = self.conn.execute(
            "UPDATE note_suggestions SET status = 'accepted', decided_at = ?"
            f" WHERE trip_id = ? AND status = 'pending' AND note_id IN ({marks})",
            (utc_now_text(), trip_id, *note_ids),
        )
        if commit:
            self.conn.commit()
        return int(cur.rowcount)
