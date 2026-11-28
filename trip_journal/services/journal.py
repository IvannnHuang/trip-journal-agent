# ADDED [PROMPT #36]: day journal jobs, on-read grounding, editing and scoped citations.
import logging
from collections.abc import Callable, Sequence
from html import escape
from time import perf_counter

from trip_journal.agent.journal import ChunkPlan, JournalAgent, chunk_stops
from trip_journal.agent.llm import LLMClient
from trip_journal.agent.prompts import PromptLibrary
from trip_journal.agent.tools import ToolContext, default_registry, truncate_text
from trip_journal.config import (
    JOURNAL_JOB_TIMEOUT_CAP_S,
    JOURNAL_JOB_TIMEOUT_PER_CALL_S,
    JOURNAL_MAX_PARAGRAPH_CHARS,
    MAX_TOOL_RECORDS,
)
from trip_journal.data.repositories import Repositories
from trip_journal.domain.days import local_hm
from trip_journal.domain.grounding import CITATION_RE, CitationKind, check_text
from trip_journal.domain.journal_merge import (
    Paragraph,
    Tone,
    slot_order,
    slot_safe,
    slots_to_write,
    stop_slot,
)
from trip_journal.domain.views import (
    CitationTarget,
    JournalView,
    NothingToRegenerate,
    ParagraphEditView,
    ParagraphView,
    SentenceView,
)
from trip_journal.logs import kv
from trip_journal.places.lookup import PlaceLookup
from trip_journal.services.errors import (
    ModelUnavailableError,
    NoRecordsError,
    NotFoundError,
    ParagraphTooLongError,
)
from trip_journal.services.jobs import JobProgress, JobRef, JobRunner
from trip_journal.services.settings import Settings, SettingsService
from trip_journal.services.trips import TripService

log = logging.getLogger(__name__)


def plan_day(repos: Repositories, trip_id: int, stops: Sequence[int]) -> ChunkPlan:
    sizes = []
    for stop in stops:
        notes = repos.notes.list_for_stop(trip_id, stop)[:MAX_TOOL_RECORDS]
        sizes.append((stop, sum(len(truncate_text(n.text)[0]) for n in notes)))
    return ChunkPlan(chunk_stops(sizes) or [[]])


def sentence_html(trip_id: int, slot: str, sentence: str) -> str:
    panel = escape(f"cite-panel-{slot_safe(slot)}", quote=True)

    def button(kind: str, cid: str) -> str:
        return (
            f'<button type="button" class="cite" data-testid="cite-{kind}-{cid}" '
            f'aria-expanded="false" aria-controls="{panel}" '
            f'hx-get="/trips/{trip_id}/citations/{kind}/{cid}" hx-target="#{panel}">'
            f"{kind} {cid}</button>"
        )

    return CITATION_RE.sub(lambda m: button(m[1], m[2]), escape(sentence))


class JournalService:
    def __init__(
        self,
        repos: Repositories,
        jobs: JobRunner,
        settings: SettingsService,
        trips: TripService,
        llm_factory: Callable[[Settings], LLMClient],
        prompts: PromptLibrary,
        places: PlaceLookup,
    ) -> None:
        self.repos = repos
        self.jobs = jobs
        self.settings = settings
        self.trips = trips
        self.llm_factory = llm_factory
        self.prompts = prompts
        self.places = places

    def _precheck(
        self, trip_id: int, day: str
    ) -> tuple[list[int], list[Paragraph], list[str], list[str]] | None:
        """BL-1 steps 1-4; None means nothing to regenerate."""
        timeline = self.trips.get_day(trip_id, day)
        stops = [s.stop_id for s in timeline.stops]
        if not stops and not self.repos.notes.list_for_day(trip_id, day):
            raise NoRecordsError()
        stored = self.repos.journals.get(trip_id, day)
        existing = stored.paragraphs if stored else []
        order = slot_order(stops)
        todo = slots_to_write(existing, order)
        return (stops, existing, order, todo) if todo else None

    async def start_generation(
        self, trip_id: int, day: str, tone: Tone
    ) -> JobRef | NothingToRegenerate:
        if self._precheck(trip_id, day) is None:
            return NothingToRegenerate()
        current = self.settings.get()
        llm = self.llm_factory(current)
        status = await llm.status()
        if not status.ok:
            raise ModelUnavailableError(status)
        # CHANGED [PROMPT #36]: re-check after the await; the trip or day may have changed (D-16).
        checked = self._precheck(trip_id, day)
        if checked is None:
            return NothingToRegenerate()
        stops, existing, order, todo = checked
        owned = {p.slot: p.text for p in existing if p.owner == "user"}
        previous = {p.slot: p.text for p in existing}
        plan = plan_day(self.repos, trip_id, stops)
        limit = min(JOURNAL_JOB_TIMEOUT_CAP_S, JOURNAL_JOB_TIMEOUT_PER_CALL_S * plan.planned_calls)

        async def work(progress: JobProgress) -> JournalView:
            started = perf_counter()
            log.info(
                kv(
                    "journal.start",
                    trip_id=trip_id,
                    day=day,
                    tone=tone,
                    slots=len(todo),
                    chunks=len(plan.chunks),
                    planned_calls=plan.planned_calls,
                )
            )
            written = missing = 0
            outcome = "failed"
            agent = JournalAgent(llm, default_registry(), self.prompts)
            try:
                draft = await agent.write_day(
                    ToolContext(trip_id, self.repos, self.places),
                    day,
                    tone,
                    plan,
                    todo,
                    owned,
                    previous,
                    progress.step,
                    progress.tool_call,
                )
                progress.step("Saving…")
                merge = self.repos.journals.save_generated(
                    trip_id,
                    day,
                    order,
                    draft.slots,
                    tone,
                    draft.trace,
                    self.prompts.version(),
                    current.model_name,
                )
                written, missing = len(merge.replaced_slots), len(merge.missing_slots)
                view = self.get_journal(trip_id, day)
                if missing:
                    noun = "paragraph" if missing == 1 else "paragraphs"
                    message = f"The agent did not write {missing} {noun}; regenerate to try again."
                    if view.message:
                        message += " " + view.message
                    view = view.model_copy(update={"message": message})
                outcome = "ok"
                return view
            finally:
                log.info(
                    kv(
                        "journal.end",
                        slots_written=written,
                        missing=missing,
                        calls=agent.calls,
                        duration_ms=round((perf_counter() - started) * 1000),
                        outcome=outcome,
                    )
                )

        return self.jobs.start("journal", work, timeout_s=limit)

    def get_journal(self, trip_id: int, day: str) -> JournalView:
        timeline = self.trips.get_day(trip_id, day)
        stored = self.repos.journals.get(trip_id, day)
        if stored is None:
            return JournalView(trip_id=trip_id, day=day)
        trip_ids = self.repos.trips.known_citation_ids(trip_id)
        run_ids = {cid for r in stored.trace for cid in r.returned_ids}
        headings = {
            # CHANGED [PROMPT #36]: reading-view stop heading.
            stop_slot(s.stop_id): f"{s.name or 'Unnamed stop'} · {s.start_local}"
            for s in timeline.stops
        }
        paragraphs = []
        unsupported = 0
        # CHANGED [PROMPT #36]: D-16, rows for stops no longer in the day stay stored but hidden.
        current = set(slot_order([s.stop_id for s in timeline.stops]))
        for p in (p for p in stored.paragraphs if p.slot in current):
            checks = check_text(p.text, trip_ids if p.owner == "user" else run_ids, False)
            sentences = [
                SentenceView(
                    text_html=sentence_html(trip_id, p.slot, c.sentence), supported=c.supported
                )
                for c in checks
            ]
            unsupported += sum(not c.supported for c in checks)
            paragraphs.append(
                ParagraphView(
                    **p.model_dump(),
                    heading=headings.get(p.slot, "Day summary"),
                    state="written"
                    if p.text
                    else ("removed" if p.owner == "user" else "not_written"),
                    sentences=sentences,
                )
            )
        errors = sum(r.error is not None for r in stored.trace)
        message = (
            f"{errors} tool call{'s' if errors != 1 else ''} failed; see How this was made"
            if errors
            else None
        )
        return JournalView(
            trip_id=trip_id,
            day=day,
            tone=stored.tone,
            trace=stored.trace,
            model_name=stored.model_name,
            prompt_version=stored.prompt_version,
            generated_at=stored.generated_at,
            paragraphs=paragraphs,
            unsupported_count=unsupported,
            message=message,
        )

    def edit_paragraph(self, trip_id: int, day: str, slot: str, text: str) -> ParagraphEditView:
        timeline = self.trips.get_day(trip_id, day)
        stored = self.repos.journals.get(trip_id, day)
        if stored is None:
            raise NotFoundError(code="journal_not_found")
        if slot not in slot_order([s.stop_id for s in timeline.stops]):
            raise NotFoundError(code="slot_not_found")
        if len(text) > JOURNAL_MAX_PARAGRAPH_CHARS:
            raise ParagraphTooLongError()
        old = next((p for p in stored.paragraphs if p.slot == slot), None)
        self.repos.journals.save_user_edit(trip_id, day, slot, text)
        log.info(kv("journal.edit", slot=slot, changed=old is None or old.text != text))
        journal = self.get_journal(trip_id, day)
        return ParagraphEditView(
            paragraph=next(p for p in journal.paragraphs if p.slot == slot),
            unsupported_count=journal.unsupported_count,
        )

    def get_citation(self, trip_id: int, kind: CitationKind, id: int) -> CitationTarget:
        if kind == "stop" and (stop := self.repos.stops.get(trip_id, id)):
            count, _ = self.repos.stops.counts(trip_id, id)
            start = local_hm(stop.start_utc, stop.utc_offset_minutes)
            end = local_hm(stop.end_utc, stop.utc_offset_minutes)
            return CitationTarget(
                kind=kind,
                id=id,
                found=True,
                title=stop.name or "Unnamed stop",
                time_label=f"{start}–{end}",
                body=f"{count} note{'s' if count != 1 else ''}",
            )
        if kind == "note" and (note := self.repos.notes.get(trip_id, id)):
            parent = self.repos.stops.get(trip_id, note.stop_id) if note.stop_id else None
            return CitationTarget(
                kind=kind,
                id=id,
                found=True,
                title=(parent.name if parent else None) or "Note",
                time_label=local_hm(note.time_utc, note.utc_offset_minutes),
                body=note.text,
            )
        if kind == "photo":
            for photo in self.repos.photos.list_for_trip(trip_id):
                if photo.id == id:
                    return CitationTarget(
                        kind=kind,
                        id=id,
                        found=True,
                        title=photo.file_name or "Photo",
                        time_label=local_hm(photo.time_utc, photo.utc_offset_minutes),
                    )
        return CitationTarget(
            kind=kind, id=id, found=False, title="Record not found in this trip.", time_label=""
        )
