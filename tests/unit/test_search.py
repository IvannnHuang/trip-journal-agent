# ADDED [PROMPT #13]: note search tests (SN-1..SN-5). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import pytest

from tests.conftest import Seed
from trip_journal.data.repositories import Repositories, build_fts_query, split_terms


def test_split_terms_and_fts_query_quote_terms() -> None:
    terms = split_terms("  lake  cold ")
    assert terms == ["lake", "cold"]
    assert build_fts_query(['a"b']).count('""') == 1


def test_search_trigram_and_case_insensitive(repos: Repositories, seed: Seed) -> None:
    assert [n.id for n in repos.notes.search(seed.trip_id, "LAKE cold")] == [seed.notes[0]]
    assert [n.id for n in repos.notes.search(seed.trip_id, "ream")] == [seed.notes[1]]


def test_short_terms_use_like(repos: Repositories, seed: Seed) -> None:
    assert [n.id for n in repos.notes.search(seed.trip_id, "ca")] == [seed.notes[1]]


def test_search_is_scoped_and_limited(repos: Repositories, seed: Seed) -> None:
    assert [n.trip_id for n in repos.notes.search(seed.trip_id, "lake")] == [seed.trip_id]
    for i in range(5):
        repos.notes.add(seed.trip_id, f"x{i}", "lake again", "2026-06-03T08:00:00Z", 0)
    assert len(repos.notes.search(seed.trip_id, "lake", limit=3)) == 3


@pytest.mark.parametrize("query", ['"', "a*", "NEAR(", "x OR y", "%", "_", "\\", "-x", "a:b"])
def test_special_characters_do_not_raise(repos: Repositories, seed: Seed, query: str) -> None:
    repos.notes.search(seed.trip_id, query)


def test_like_wildcards_are_literal(repos: Repositories, seed: Seed) -> None:
    assert repos.notes.search(seed.trip_id, "%") == []
    assert repos.notes.search(seed.trip_id, "_") == []


def test_empty_query_raises(repos: Repositories, seed: Seed) -> None:
    with pytest.raises(ValueError):
        repos.notes.search(seed.trip_id, "   ")


def test_nul_character_is_whitespace(repos: Repositories, seed: Seed) -> None:
    # CHANGED [PROMPT #13]: regression for the NUL bug found by P-Q1/P-Q2.
    assert split_terms("lake\x00swam") == ["lake", "swam"]
    assert [n.id for n in repos.notes.search(seed.trip_id, "lake\x00swam")] == [seed.notes[0]]
    with pytest.raises(ValueError):
        repos.notes.search(seed.trip_id, "\x00")
