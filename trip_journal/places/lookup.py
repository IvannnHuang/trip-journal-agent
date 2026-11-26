# ADDED [PROMPT #13]: place lookup with cache and rate limit (C23, PL-1..PL-9, NP-4).
# AI-assisted, Claude Opus 5.5.
"""Reverse geocoding: imported stop name → cache → Nominatim (only when the owner turned it on).

Only rounded coordinates leave the laptop. Failures never reach the agent as exceptions.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel

from trip_journal.config import (
    NOMINATIM_MIN_INTERVAL_S,
    NOMINATIM_TIMEOUT_S,
    NOMINATIM_URL,
    USER_AGENT,
)
from trip_journal.logs import kv

log = logging.getLogger(__name__)

PlaceSource = Literal["import", "cache", "nominatim", "none"]


def cache_key(value: float) -> str:
    """Round to 4 decimals as text; `-0.0000` becomes `0.0000` (PL-2)."""
    text = f"{round(value, 4):.4f}"
    return "0.0000" if text == "-0.0000" else text


class PlaceName(BaseModel):
    name: str | None
    source: PlaceSource
    stop_id: int | None = None


class PlaceCache(Protocol):
    def get(self, lat_key: str, lon_key: str) -> str | None: ...
    def put(self, lat_key: str, lon_key: str, name: str) -> None: ...


class RateLimiter:
    """At most one request start per `min_interval_s`, process-wide (NP-4).

    The lock is held through the request, and `last_start` is set before it, so two
    callers can never send at the same time.
    """

    def __init__(
        self,
        min_interval_s: float = NOMINATIM_MIN_INTERVAL_S,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.min_interval_s = min_interval_s
        self._clock = clock
        self._sleep = sleep
        self._lock = asyncio.Lock()
        self._last_start: float | None = None

    async def run[T](self, fn: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            if self._last_start is not None:
                wait = self._last_start + self.min_interval_s - self._clock()
                if wait > 0:
                    await self._sleep(wait)
            self._last_start = self._clock()
            return await fn()


def name_from_reply(data: object) -> str | None:
    """`name`, or the first two comma-separated parts of `display_name` (PL-9)."""
    if not isinstance(data, dict):
        return None
    name = data.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    display = data.get("display_name")
    if isinstance(display, str) and display.strip():
        parts = [p.strip() for p in display.split(",") if p.strip()]
        return ", ".join(parts[:2]) or None
    return None


class PlaceLookup:
    def __init__(
        self,
        is_enabled: Callable[[], bool],
        cache: PlaceCache,
        http: httpx.AsyncClient,
        min_interval_s: float = NOMINATIM_MIN_INTERVAL_S,
        user_agent: str = USER_AGENT,
        limiter: RateLimiter | None = None,
    ) -> None:
        self._is_enabled = is_enabled
        self._cache = cache
        self._http = http
        self._user_agent = user_agent
        self._limiter = limiter or RateLimiter(min_interval_s)

    async def lookup(
        self, lat: float, lon: float, imported_name: str | None = None, stop_id: int | None = None
    ) -> PlaceName:
        if imported_name:
            log.info(kv("place.lookup", source="import"))
            return PlaceName(name=imported_name, source="import", stop_id=stop_id)
        if not self._is_enabled():
            log.info(kv("place.lookup", source="none", reason="disabled"))
            return PlaceName(name=None, source="none", stop_id=stop_id)
        lat_key, lon_key = cache_key(lat), cache_key(lon)
        cached = self._cache.get(lat_key, lon_key)
        if cached is not None:
            log.info(kv("place.lookup", source="cache"))
            return PlaceName(name=cached, source="cache", stop_id=stop_id)
        name = await self._fetch(lat_key, lon_key)
        if name is None:
            return PlaceName(name=None, source="none", stop_id=stop_id)
        self._cache.put(lat_key, lon_key, name)
        log.info(kv("place.lookup", source="nominatim"))
        return PlaceName(name=name, source="nominatim", stop_id=stop_id)

    async def _fetch(self, lat_key: str, lon_key: str) -> str | None:
        params = {"lat": lat_key, "lon": lon_key, "format": "jsonv2", "accept-language": "en"}
        headers = {"User-Agent": self._user_agent}

        async def request() -> httpx.Response:
            async with asyncio.timeout(NOMINATIM_TIMEOUT_S):
                return await self._http.get(
                    NOMINATIM_URL, params=params, headers=headers, timeout=NOMINATIM_TIMEOUT_S
                )

        try:
            response = await self._limiter.run(request)
            response.raise_for_status()
            return name_from_reply(response.json())
        except (httpx.HTTPError, TimeoutError, ValueError) as exc:
            log.warning(kv("place.lookup", source="none", reason=type(exc).__name__))
            return None
