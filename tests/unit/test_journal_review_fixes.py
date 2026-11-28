# ADDED [PROMPT #36]: C1 review fixes (D-16): huge ids, re-check after await, hidden orphans.
import pytest

from trip_journal.agent.llm import FakeLLMClient, ModelStatus
from trip_journal.domain.grounding import Citation, check_text, extract_citations
from trip_journal.services.errors import NotFoundError
from trip_journal.services.journal import JournalService

DAY = "2026-06-01"


def test_huge_citation_id_is_plain_text() -> None:
    huge = "9" * 5000
    assert extract_citations(f"Went there [note:{huge}].") == []
    assert not check_text(f"Went there [note:{huge}].", set(), False)[0].supported
    max_id = int("9" * 18)
    assert extract_citations(f"Ok [stop:{max_id}].") == [Citation("stop", max_id)]


async def test_trip_deleted_during_status_check(
    journal_service: JournalService, journal_trip: int
) -> None:
    service = journal_service

    class DeletingLLM(FakeLLMClient):
        async def status(self) -> ModelStatus:
            service.repos.trips.delete(journal_trip)
            return await super().status()

    service.llm_factory = lambda _: DeletingLLM([])
    with pytest.raises(NotFoundError):
        await service.start_generation(journal_trip, DAY, "casual")


def test_rows_for_vanished_stops_are_hidden(
    journal_service: JournalService, journal_trip: int
) -> None:
    service = journal_service
    order = ["summary", "stop:999999"]
    service.repos.journals.save_generated(
        journal_trip, DAY, order, dict.fromkeys(order, "Text."), "casual", [], "v", "m"
    )
    view = service.get_journal(journal_trip, DAY)
    assert [p.slot for p in view.paragraphs] == ["summary"]
    stored = service.repos.journals.get(journal_trip, DAY)
    assert stored and [p.slot for p in stored.paragraphs] == order
    with pytest.raises(NotFoundError):
        service.edit_paragraph(journal_trip, DAY, "stop:999999", "mine")
