# ADDED [PROMPT #13]: place lookup tests (PL-1..PL-9, NP-4). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx

from trip_journal.config import USER_AGENT
from trip_journal.data.repositories import Repositories
from trip_journal.places.lookup import PlaceLookup, RateLimiter, cache_key, name_from_reply


def _lookup(
    repos: Repositories,
    handler: httpx.MockTransport,
    enabled: bool = True,
    limiter: RateLimiter | None = None,
) -> PlaceLookup:
    return PlaceLookup(
        is_enabled=lambda: enabled,
        cache=repos.place_cache,
        http=httpx.AsyncClient(transport=handler),
        limiter=limiter or RateLimiter(0),
    )


def test_cache_key() -> None:
    assert cache_key(46.362512) == "46.3625"
    assert cache_key(-0.00001) == "0.0000"
    assert cache_key(-12.5) == "-12.5000"


def test_name_from_reply() -> None:
    assert name_from_reply({"name": " Bled "}) == "Bled"
    assert name_from_reply({"name": "", "display_name": "A, B, C"}) == "A, B"
    assert name_from_reply({"error": "x"}) is None
    assert name_from_reply([1]) is None


def _recording(seen: list[httpx.Request]) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(500)

    return handler


async def test_imported_name_wins_without_network(repos: Repositories) -> None:
    seen: list[httpx.Request] = []
    transport = httpx.MockTransport(_recording(seen))
    got = await _lookup(repos, transport).lookup(1.0, 2.0, imported_name="Home", stop_id=3)
    assert (got.name, got.source, got.stop_id) == ("Home", "import", 3)
    assert seen == []


async def test_disabled_means_no_request(repos: Repositories) -> None:
    seen: list[httpx.Request] = []
    transport = httpx.MockTransport(_recording(seen))
    got = await _lookup(repos, transport, enabled=False).lookup(1.0, 2.0)
    assert got.source == "none" and seen == []


async def test_fetch_then_cache(repos: Repositories) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"name": "Bled"})

    lookup = _lookup(repos, httpx.MockTransport(handler))
    first = await lookup.lookup(46.362512, 14.093801)
    second = await lookup.lookup(46.36249, 14.09381)
    assert (first.source, second.source, second.name) == ("nominatim", "cache", "Bled")
    assert len(seen) == 1
    params = seen[0].url.params
    assert params["lat"] == "46.3625" and params["lon"] == "14.0938"  # PL-3: rounded only
    assert seen[0].headers["User-Agent"] == USER_AGENT


async def test_failures_return_none_and_are_not_cached(repos: Repositories) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    got = await _lookup(repos, httpx.MockTransport(handler)).lookup(1.0, 2.0)
    assert got.name is None and got.source == "none"
    assert repos.place_cache.get("1.0000", "2.0000") is None


async def test_rate_limiter_spaces_requests() -> None:
    now = [0.0]
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    limiter = RateLimiter(1.0, clock=lambda: now[0], sleep=fake_sleep)

    async def job() -> int:
        return 1

    await asyncio.gather(limiter.run(job), limiter.run(job), limiter.run(job))
    assert slept == [1.0, 1.0]
