# ADDED [PROMPT #13]: place cache key properties P-K1..P-K3 (PL-3, PL-5).
# AI-assisted, Claude Opus 5.5.
from __future__ import annotations

from hypothesis import given

from tests.strategies import coordinates
from trip_journal.places.lookup import cache_key


@given(coordinates)
def test_p_k1_key_round_trip(value: float) -> None:
    key = cache_key(value)
    assert cache_key(float(key)) == key


@given(coordinates)
def test_p_k2_key_is_close_and_four_places(value: float) -> None:
    key = cache_key(value)
    assert len(key.split(".")[1]) == 4
    assert abs(float(key) - value) <= 0.00005 + 1e-9


@given(coordinates)
def test_p_k3_no_negative_zero(value: float) -> None:
    assert cache_key(value) != "-0.0000"
