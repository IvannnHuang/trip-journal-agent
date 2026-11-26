# ADDED [PROMPT #13]: grounding checker examples (GR-1..GR-8). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

from trip_journal.config import NOT_IN_RECORDS
from trip_journal.domain.grounding import (
    Citation,
    check_text,
    extract_citations,
    find_unsupported_sentences,
    split_sentences,
)

KNOWN = {Citation("stop", 1), Citation("note", 2)}


def test_split_keeps_trailing_citations_with_sentence() -> None:
    text = "We swam. [note:2] Then lunch! [stop:1]\nLast line"
    assert split_sentences(text) == ["We swam. [note:2]", "Then lunch! [stop:1]", "Last line"]


def test_split_handles_cjk_and_decimals() -> None:
    assert split_sentences("温度是 3.5 度。很冷！") == ["温度是 3.5 度。", "很冷！"]


def test_extract_citations_in_order_and_rejects_zero() -> None:
    cites = extract_citations("a [stop:1] b [note:22] [photo:0] [place:3]")
    assert cites == [Citation("stop", 1), Citation("note", 22)]
    assert str(cites[1]) == "[note:22]"


def test_supported_requires_all_known() -> None:
    checks = check_text("Swam [note:2]. Ate [note:9]. Walked.", KNOWN)
    assert [c.supported for c in checks] == [True, False, False]


def test_not_in_records_exempt_only_when_allowed() -> None:
    assert check_text(NOT_IN_RECORDS, KNOWN, allow_not_in_records=True)[0].exempt
    assert not check_text(NOT_IN_RECORDS, KNOWN)[0].supported
    longer = f"{NOT_IN_RECORDS} But we swam."
    flagged = find_unsupported_sentences(longer, KNOWN, allow_not_in_records=True)
    assert flagged == ["But we swam."]


def test_empty_text_has_no_sentences() -> None:
    assert check_text("   \n ", KNOWN) == []
