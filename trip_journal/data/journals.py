# ADDED [PROMPT #36]: atomic journal saves and ownership-preserving edits.
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from pydantic import BaseModel, TypeAdapter

from trip_journal.agent.loop import ToolCallRecord
from trip_journal.domain.journal_merge import MergeResult, Paragraph, Tone, merge_journal
from trip_journal.services.errors import NotFoundError

_TRACE = TypeAdapter(list[ToolCallRecord])


class StoredJournal(BaseModel):
    trip_id: int
    day: str
    tone: Tone
    prompt_version: str
    model_name: str
    trace: list[ToolCallRecord]
    generated_at: str
    updated_at: str
    paragraphs: list[Paragraph]


class JournalRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def exists(self, trip_id: int, day: str) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM journals WHERE trip_id=? AND day=?", (trip_id, day)
            ).fetchone()
            is not None
        )

    def get(self, trip_id: int, day: str) -> StoredJournal | None:
        rows = self.conn.execute(
            "SELECT j.*, p.slot, p.text, p.owner FROM journals j LEFT JOIN journal_paragraphs p"
            " USING (trip_id, day) WHERE j.trip_id=? AND j.day=? ORDER BY p.position",
            (trip_id, day),
        ).fetchall()
        if not rows:
            return None
        return StoredJournal(
            **dict(rows[0]),
            trace=_TRACE.validate_json(rows[0]["trace_json"]),
            paragraphs=[Paragraph.model_validate(dict(row)) for row in rows if row["slot"]],
        )

    def save_generated(
        self,
        trip_id: int,
        day: str,
        order: Sequence[str],
        draft_slots: Mapping[str, str],
        tone: Tone,
        trace: list[ToolCallRecord],
        prompt_version: str,
        model_name: str,
    ) -> MergeResult:
        with self.conn:
            self.conn.execute("BEGIN IMMEDIATE")
            rows = self.conn.execute(
                "SELECT slot,text,owner FROM journal_paragraphs WHERE trip_id=? AND day=?",
                (trip_id, day),
            )
            existing = [Paragraph.model_validate(dict(row)) for row in rows]
            result = merge_journal(existing, draft_slots, order)
            now = datetime.now(UTC).isoformat()
            self.conn.execute(
                "INSERT INTO journals (trip_id,day,tone,trace_json,prompt_version,"
                "model_name,generated_at,updated_at) VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(trip_id,day) DO UPDATE SET tone=excluded.tone,"
                "trace_json=excluded.trace_json,prompt_version=excluded.prompt_version,"
                "model_name=excluded.model_name,generated_at=excluded.generated_at,"
                "updated_at=excluded.updated_at",
                (
                    trip_id,
                    day,
                    tone,
                    _TRACE.dump_json(trace).decode(),
                    prompt_version,
                    model_name,
                    now,
                    now,
                ),
            )
            old_slots = {p.slot for p in existing}
            for position, p in enumerate(result.paragraphs):
                key = (trip_id, day, p.slot)
                if p.slot not in old_slots:
                    self.conn.execute(
                        "INSERT INTO journal_paragraphs (trip_id,day,slot,position,"
                        "text,owner) VALUES (?,?,?,?,?,'generated')",
                        (*key, position, p.text),
                    )
                elif p.slot in result.replaced_slots:
                    self.conn.execute(
                        "UPDATE journal_paragraphs SET text=?,position=? WHERE "
                        "trip_id=? AND day=? AND slot=? AND owner='generated'",
                        (p.text, position, *key),
                    )
                else:
                    self.conn.execute(
                        "UPDATE journal_paragraphs SET position=? WHERE trip_id=? "
                        "AND day=? AND slot=? AND position<>?",
                        (position, *key, position),
                    )
            return result

    def save_user_edit(self, trip_id: int, day: str, slot: str, text: str) -> Paragraph:
        with self.conn:
            self.conn.execute("BEGIN IMMEDIATE")
            key = (trip_id, day, slot)
            row = self.conn.execute(
                "SELECT slot,text,owner FROM journal_paragraphs "
                "WHERE trip_id=? AND day=? AND slot=?",
                key,
            ).fetchone()
            if row is None:
                raise NotFoundError(code="slot_not_found")
            if text == row["text"]:
                return Paragraph.model_validate(dict(row))
            self.conn.execute(
                "UPDATE journal_paragraphs SET text=?,owner='user' "
                "WHERE trip_id=? AND day=? AND slot=?",
                (text, *key),
            )
            self.conn.execute(
                "UPDATE journals SET updated_at=? WHERE trip_id=? AND day=?",
                (datetime.now(UTC).isoformat(), trip_id, day),
            )
            return Paragraph(slot=slot, text=text, owner="user")
