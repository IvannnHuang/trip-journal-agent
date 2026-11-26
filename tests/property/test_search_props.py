# ADDED [PROMPT #13]: search properties P-Q1, P-Q2 (SN-1..SN-5). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.conftest import Seed
from trip_journal.data.repositories import Repositories, split_terms

_queries = st.text(st.characters(codec="utf-8", exclude_categories=["Cs"]), max_size=40)
_no_reuse = settings(suppress_health_check=[HealthCheck.function_scoped_fixture])


@_no_reuse
@given(_queries)
def test_p_q1_search_never_raises_on_any_text(repos: Repositories, seed: Seed, query: str) -> None:
    if not split_terms(query):
        return  # SN-1: a query with no terms is rejected (unit-tested)
    repos.notes.search(seed.trip_id, query)


@_no_reuse
@given(_queries | st.sampled_from(["lake", "cake", "Lunch", "ke", "a", "%", "_", '"']))
def test_p_q2_results_are_this_trips_notes(repos: Repositories, seed: Seed, query: str) -> None:
    if not split_terms(query):
        return
    hits = repos.notes.search(seed.trip_id, query, limit=20)
    assert {h.id for h in hits} <= set(seed.notes)
    assert all(h.trip_id == seed.trip_id for h in hits)
    for hit in hits:  # every term appears (case-insensitive) in the note
        assert all(t.casefold() in hit.text.casefold() for t in split_terms(query))
