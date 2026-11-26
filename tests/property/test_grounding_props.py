# ADDED [PROMPT #13]: grounding properties P-G1..P-G8 (PBT-02, PBT-03).
# AI-assisted, Claude Opus 5.5.
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from tests.strategies import citations, paragraphs, sentences
from trip_journal.config import NOT_IN_RECORDS
from trip_journal.domain.grounding import (
    Citation,
    check_text,
    extract_citations,
    find_unsupported_sentences,
    split_sentences,
)


@given(st.lists(sentences(), min_size=1, max_size=6))
def test_p_g1_one_piece_per_generated_sentence(parts: list[str]) -> None:
    assert split_sentences(" ".join(parts)) == parts


@given(paragraphs())
def test_p_g2_split_keeps_all_text(text: str) -> None:
    assert "".join(text.split()) == "".join("".join(s.split()) for s in split_sentences(text))


@given(st.lists(citations, max_size=5))
def test_p_g3_citation_round_trip(cites: list[Citation]) -> None:
    text = "Seen " + " ".join(str(c) for c in cites) + "."
    assert extract_citations(text) == cites


@given(sentences(), st.sets(citations, max_size=5))
def test_p_g4_uncited_sentence_is_unsupported(sentence: str, known: set[Citation]) -> None:
    for c in extract_citations(sentence):
        sentence = sentence.replace(f" {c}", "")
    (check,) = check_text(sentence, known)
    assert not check.supported


@given(sentences(), st.sets(citations, min_size=1, max_size=5), st.data())
def test_p_g5_adding_known_citation_never_hurts(
    sentence: str, known: set[Citation], data: st.DataObject
) -> None:
    extra = data.draw(st.sampled_from(sorted(known)))
    before = check_text(sentence, known)[0].supported
    after = check_text(f"{sentence[:-1]} {extra}{sentence[-1]}", known)[0]
    assert after.supported or not before
    if not extract_citations(sentence):
        assert after.supported  # metamorphic: an uncited sentence becomes supported


@given(paragraphs(), st.sets(citations, max_size=8))
def test_p_g6_unsupported_is_subset_of_sentences(text: str, known: set[Citation]) -> None:
    pieces = split_sentences(text)
    assert all(s in pieces for s in find_unsupported_sentences(text, known))


@given(paragraphs())
def test_p_g7_split_is_idempotent(text: str) -> None:
    for sentence in split_sentences(text):
        assert split_sentences(sentence) == [sentence]


@given(st.lists(citations, min_size=1, max_size=6, unique=True), st.data())
def test_p_g8_fully_cited_text_has_no_unsupported(
    known: list[Citation], data: st.DataObject
) -> None:
    parts = data.draw(st.lists(sentences(known=known), min_size=1, max_size=5))
    cited = [p if extract_citations(p) else f"{p[:-1]} {known[0]}{p[-1]}" for p in parts]
    assert find_unsupported_sentences(" ".join(cited), set(known)) == []
    assert find_unsupported_sentences(NOT_IN_RECORDS, set(), allow_not_in_records=True) == []
