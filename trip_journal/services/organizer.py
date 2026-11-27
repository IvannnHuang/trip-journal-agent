# ADDED [PROMPT #25]: OrganizerService (U3 IC-5): organize run as a job, review actions.
# AI-assisted, Claude Opus 5.5.
"""Run the note organizer for a day or a trip, and review its suggestions.

The run is one `organize` job (OR-RUN4). Each batch is saved in its own transaction as
soon as it returns (OR-SAVE1, N-5). Review actions never call the model (FA-4). Log lines
carry ids, counts and codes only, never note or reply text (L.4).
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel

from trip_journal.agent.llm import LLMClient
from trip_journal.agent.organizer import NoteOrganizer
from trip_journal.agent.prompts import PromptLibrary
from trip_journal.config import (
    ORGANIZER_CALL_TIMEOUT_S,
    ORGANIZER_JOB_TIMEOUT_CAP_S,
    ORGANIZER_JOB_TIMEOUT_PER_BATCH_S,
)
from trip_journal.data.repositories import NoteRow, Repositories, StopRow
from trip_journal.data.suggestions import DECIDED, FinalValues, SuggestionRow
from trip_journal.domain.days import local_hm
from trip_journal.domain.organizer import (
    PREVIEW_CHARS,
    BatchInput,
    DayRunResult,
    NotOrganized,
    OrganizerBatchResult,
    OrganizerRunSummary,
    SuggestionView,
    check_edit,
    plan_batches,
    suggestion_view,
)
from trip_journal.logs import kv
from trip_journal.services.errors import (
    JobTimeoutError,
    ModelBusyError,
    ModelCallError,
    ModelUnavailableError,
    NotFoundError,
    SuggestionEditError,
    SuggestionStateError,
)
from trip_journal.services.jobs import JobProgress, JobRef, JobRunner
from trip_journal.services.settings import Settings, SettingsService
from trip_journal.services.trips import TripService

log = logging.getLogger(__name__)

JOB_KIND = "organize"
NO_ITEM = "no item returned"
INNER_MARGIN_S = 5.0

LLMFactory = Callable[[Settings], LLMClient]


class OrganizeStart(BaseModel):
    """What `start` returns (D-17, D-23). `job` is None when there is nothing to send."""

    job: JobRef | None
    notes_to_send: int
    batches: int


def job_timeout_s(batches: int) -> float:
    """OR-RUN3: `min(300 s × batches, 1800 s)`."""
    return min(ORGANIZER_JOB_TIMEOUT_PER_BATCH_S * batches, ORGANIZER_JOB_TIMEOUT_CAP_S)


def inner_deadline_s(limit_s: float) -> float:
    """D-13: end the batch loop a little before the JobRunner backstop fires."""
    return max(limit_s - INNER_MARGIN_S, limit_s * 0.9)


def _preview(text: str) -> str:
    return text[:PREVIEW_CHARS]


class OrganizerService:
    def __init__(
        self,
        repos: Repositories,
        jobs: JobRunner,
        settings: SettingsService,
        trips: TripService,
        llm_factory: LLMFactory,
        prompts: PromptLibrary,
        call_timeout_s: float = ORGANIZER_CALL_TIMEOUT_S,
    ) -> None:
        self.repos = repos
        self.jobs = jobs
        self.settings = settings
        self.trips = trips
        self.llm_factory = llm_factory
        self.prompts = prompts
        self.call_timeout_s = call_timeout_s

    @property
    def conn(self) -> sqlite3.Connection:
        return self.repos.suggestions.conn

    # ----- run (OR-RUN0..6) -----

    async def start(self, trip_id: int, day: str | None = None) -> OrganizeStart:
        """Plan the run and start the job. Errors: 404 trip/day, 429 busy, 503 not ready."""
        if day is None:
            self.trips.get_summary(trip_id)  # 404 trip_not_found
        else:
            self.trips.get_day(trip_id, day)  # 404 trip_not_found / day_not_found
        if self.jobs.running is not None:
            raise ModelBusyError("a job is running")  # OR-RUN4, before the model probe
        stops = self.repos.stops.list_for_trip(trip_id)
        notes = self.repos.notes.list_for_trip(trip_id)
        decided = {
            r.note_id for r in self.repos.suggestions.list_for_trip(trip_id) if r.status in DECIDED
        }
        days = sorted({n.local_date for n in notes if day is None or n.local_date == day})
        plan: list[BatchInput] = []
        skipped = 0
        for d in days:
            day_notes = [n for n in notes if n.local_date == d]
            to_send = [n for n in day_notes if n.id not in decided]  # OR-RUN1
            skipped += len(day_notes) - len(to_send)
            day_stops = tuple(s for s in stops if s.local_date == d)
            for batch in plan_batches(to_send):
                plan.append(BatchInput(day=d, stops=day_stops, notes=tuple(batch)))
        notes_to_send = sum(len(b.notes) for b in plan)
        if not plan:  # OR-RUN5 (D-24: checked before the model probe)
            log.info(kv("organizer.run", trip_id=trip_id, day=day or "all", result="nothing"))
            return OrganizeStart(job=None, notes_to_send=0, batches=0)
        current = self.settings.get()
        llm = self.llm_factory(current)
        status = await llm.status()
        if not status.ok:  # OR-RUN6 (D-20)
            raise ModelUnavailableError(status)
        limit = job_timeout_s(len(plan))

        async def work(progress: JobProgress) -> BaseModel:
            return await self._run(
                trip_id, day, plan, days, skipped, llm, current.model_name, limit, progress
            )

        job = self.jobs.start(JOB_KIND, work, timeout_s=limit)
        return OrganizeStart(job=job, notes_to_send=notes_to_send, batches=len(plan))

    async def _run(
        self,
        trip_id: int,
        scope_day: str | None,
        plan: list[BatchInput],
        days: list[str],
        skipped: int,
        llm: LLMClient,
        model_name: str,
        limit_s: float,
        progress: JobProgress,
    ) -> OrganizerRunSummary:
        organizer = NoteOrganizer(llm, self.prompts, self.call_timeout_s)
        version = self.prompts.version()
        results = {d: DayRunResult(day=d) for d in days if any(b.day == d for b in plan)}
        day_order = list(results)
        per_day = {d: sum(1 for b in plan if b.day == d) for d in day_order}
        seen = dict.fromkeys(day_order, 0)
        ok_batches = 0
        failed = 0
        done = 0
        started = time.perf_counter()
        stopped: str | None = None
        try:
            async with asyncio.timeout(inner_deadline_s(limit_s)):
                for k, batch in enumerate(plan, start=1):
                    seen[batch.day] += 1
                    i, total = seen[batch.day], per_day[batch.day]
                    if scope_day is None:
                        n = day_order.index(batch.day) + 1
                        progress.step(
                            f"Organizing day {n} of {len(day_order)} ({batch.day}),"
                            f" batch {i} of {total}"
                        )
                    else:
                        progress.step(f"Organizing {batch.day}, batch {i} of {total}")
                    t0 = time.perf_counter()
                    result = await organizer.organize_batch(batch)
                    if result.suggestions:
                        self._save(trip_id, result, version, model_name)
                    done = k
                    if result.outcome == "ok":
                        ok_batches += 1
                    else:
                        failed += 1
                    self._add(results[batch.day], batch, result)
                    log.info(
                        kv(
                            "organizer.batch",
                            trip_id=trip_id,
                            day=batch.day,
                            batch=f"{k}/{len(plan)}",
                            notes=len(batch.notes),
                            kept=len(result.suggestions),
                            dropped=len(result.dropped),
                            not_organized=len(result.not_organized),
                            outcome=result.outcome,
                            duration_ms=round((time.perf_counter() - t0) * 1000),
                        )
                    )
        except TimeoutError:
            if ok_batches == 0:
                self._log_run(trip_id, scope_day, plan, ok_batches, results, started, "job_timeout")
                raise JobTimeoutError("job timeout", limit_s=limit_s) from None
            stopped = "job_timeout"
        if ok_batches == 0:
            self._log_run(trip_id, scope_day, plan, ok_batches, results, started, "failed")
            raise ModelCallError("error")  # OR-V7: every batch failed
        remaining = sum(len(b.notes) for b in plan[done:]) if stopped else 0
        self._log_run(trip_id, scope_day, plan, ok_batches, results, started, "succeeded")
        day_results = list(results.values())
        return OrganizerRunSummary(
            trip_id=trip_id,
            scope_day=scope_day,
            days=day_results,
            total_suggested=sum(r.suggested for r in day_results),
            total_not_organized=sum(len(r.not_organized) for r in day_results),
            batches=done,
            batches_failed=failed,
            skipped_decided=skipped,
            prompt_version=version,
            model_name=model_name,
            stopped=stopped,
            remaining_notes=remaining,
        )

    def _save(
        self, trip_id: int, result: OrganizerBatchResult, version: str, model_name: str
    ) -> int:
        """OR-SAVE1 / N-5: one `BEGIN IMMEDIATE` transaction per batch."""
        with self._transaction():
            return self.repos.suggestions.save_batch(
                trip_id, result.suggestions, version, model_name, commit=False
            )

    @staticmethod
    def _add(day: DayRunResult, batch: BatchInput, result: OrganizerBatchResult) -> None:
        notes = {n.id: n for n in batch.notes}
        reasons = {d.note_id: d.reason for d in result.dropped if d.note_id is not None}
        day.notes_sent += len(batch.notes)
        day.suggested += len(result.suggestions)
        day.dropped.extend(result.dropped)
        if result.outcome != "ok":
            day.failed_batches += 1
        for note_id in result.not_organized:
            note = notes[note_id]
            reason = result.outcome if result.outcome != "ok" else reasons.get(note_id, NO_ITEM)
            day.not_organized.append(
                NotOrganized(
                    note_id=note_id,
                    local_time=local_hm(note.time_utc, note.utc_offset_minutes),
                    preview=_preview(note.text),
                    reason=reason,
                )
            )

    @staticmethod
    def _log_run(
        trip_id: int,
        scope_day: str | None,
        plan: list[BatchInput],
        ok_batches: int,
        results: Mapping[str, DayRunResult],
        started: float,
        status: str,
    ) -> None:
        log.info(
            kv(
                "organizer.run",
                trip_id=trip_id,
                day=scope_day or "all",
                batches=len(plan),
                ok_batches=ok_batches,
                kept=sum(r.suggested for r in results.values()),
                dropped=sum(len(r.dropped) for r in results.values()),
                not_organized=sum(len(r.not_organized) for r in results.values()),
                duration_ms=round((time.perf_counter() - started) * 1000),
                status=status,
            )
        )

    # ----- review actions (OR-ST, OR-S1, OR-F, OR-AA) -----

    def accept(self, suggestion_id: int) -> SuggestionView:
        return self._decide(suggestion_id, "accept", "accepted")

    def reject(self, suggestion_id: int) -> SuggestionView:
        return self._decide(suggestion_id, "reject", "rejected")

    def edit_and_accept(self, suggestion_id: int, raw: Mapping[str, Any]) -> SuggestionView:
        """pending -> edited with the user's values; 422 `invalid_edit` before any write."""
        row = self._row(suggestion_id)
        note = self._note(row)
        stop_ids = [s.id for s in self._day_stops(row.trip_id, note.local_date)]
        edit, issues = check_edit(raw, stop_ids)
        if edit is None:
            raise SuggestionEditError(issues)
        final = FinalValues(
            category=edit.category,
            stop_id=edit.stop_id,
            dish=edit.dish,
            rating=edit.rating,
            tip=edit.tip,
        )
        return self._decide(suggestion_id, "edit", "edited", final)

    def undo(self, suggestion_id: int) -> SuggestionView:
        """accepted / edited / rejected -> pending (Q3 A)."""
        with self._transaction():
            row = self._row(suggestion_id)
            if row.status not in DECIDED:
                raise SuggestionStateError(row.status)
            self.repos.suggestions.undo(suggestion_id, commit=False)
        self._log_review(suggestion_id, "undo", row.status, "pending")
        return self._view(self._row(suggestion_id))

    def accept_all(self, trip_id: int, day: str) -> int:
        """OR-AA1: the day's pending rows become accepted; returns the count."""
        self.trips.get_day(trip_id, day)  # 404 trip_not_found / day_not_found
        note_ids = [n.id for n in self.repos.notes.list_for_trip(trip_id) if n.local_date == day]
        with self._transaction():
            count = self.repos.suggestions.accept_all_pending(trip_id, note_ids, commit=False)
        log.info(kv("organizer.review", action="accept_all", trip_id=trip_id, day=day, count=count))
        return count

    def get_view(self, suggestion_id: int) -> SuggestionView:
        return self._view(self._row(suggestion_id))

    def list_for_day(self, trip_id: int, day: str) -> list[SuggestionView]:
        """Every suggestion row of the day, in note time order (404 trip / day)."""
        self.trips.get_day(trip_id, day)
        notes = {n.id: n for n in self.repos.notes.list_for_trip(trip_id) if n.local_date == day}
        stops = {s.id: s for s in self._day_stops(trip_id, day)}
        return [
            suggestion_view(r, notes[r.note_id], stops)
            for r in self.repos.suggestions.list_for_day(trip_id, day)
        ]

    # ----- helpers -----

    def _decide(
        self, suggestion_id: int, action: str, to: str, final: FinalValues | None = None
    ) -> SuggestionView:
        with self._transaction():
            row = self._row(suggestion_id)  # re-read inside the transaction (FA-3)
            if row.status != "pending":
                raise SuggestionStateError(row.status)
            self.repos.suggestions.set_status(suggestion_id, to, final, commit=False)
        self._log_review(suggestion_id, action, "pending", to)
        return self._view(self._row(suggestion_id))

    def _transaction(self) -> _Transaction:
        return _Transaction(self.conn)

    def _row(self, suggestion_id: int) -> SuggestionRow:
        row = self.repos.suggestions.get(suggestion_id)
        if row is None:
            raise NotFoundError("suggestion not found", code="suggestion_not_found")
        return row

    def _note(self, row: SuggestionRow) -> NoteRow:
        note = self.repos.notes.get(row.trip_id, row.note_id)
        if note is None:  # the FK cascade makes this unreachable
            raise NotFoundError("suggestion not found", code="suggestion_not_found")
        return note

    def _day_stops(self, trip_id: int, day: str) -> list[StopRow]:
        return [s for s in self.repos.stops.list_for_trip(trip_id) if s.local_date == day]

    def _view(self, row: SuggestionRow) -> SuggestionView:
        note = self._note(row)
        stops = {s.id: s for s in self._day_stops(row.trip_id, note.local_date)}
        return suggestion_view(row, note, stops)

    @staticmethod
    def _log_review(suggestion_id: int, action: str, before: str, after: str) -> None:
        fields: dict[str, object] = {"from": before, "to": after}
        log.info(kv("organizer.review", suggestion_id=suggestion_id, action=action, **fields))


class _Transaction:
    """`BEGIN IMMEDIATE` ... `COMMIT`, `ROLLBACK` on any exception (N-5, U2 `_store`)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def __enter__(self) -> None:
        if self.conn.in_transaction:
            self.conn.commit()  # sqlite3 refuses BEGIN inside an open implicit transaction
        self.conn.execute("BEGIN IMMEDIATE")

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
