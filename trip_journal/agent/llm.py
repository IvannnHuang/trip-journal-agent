# ADDED [PROMPT #13]: LLM client protocol, Ollama client, fake client (C10, NP-1, NP-3).
# AI-assisted, Claude Opus 5.5.
"""The only module that talks to the model server."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any, Protocol

import httpx
import openai
from pydantic import BaseModel

from trip_journal.config import MODEL_CALL_TIMEOUT_S, STATUS_TIMEOUT_S
from trip_journal.logs import kv

log = logging.getLogger(__name__)


class ToolCall(BaseModel):
    id: str | None
    name: str
    arguments_json: str


class LLMReply(BaseModel):
    content: str | None
    tool_calls: list[ToolCall] = []


class ModelStatus(BaseModel):
    reachable: bool
    model_installed: bool
    model_name: str
    base_url: str

    @property
    def ok(self) -> bool:
        return self.reachable and self.model_installed


class LLMClient(Protocol):
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMReply: ...

    async def status(self) -> ModelStatus: ...


def server_root(base_url: str) -> str:
    """`http://host:port/v1` → `http://host:port` (ST-2)."""
    root = base_url.rstrip("/")
    return root[: -len("/v1")] if root.endswith("/v1") else root


def model_is_installed(model: str, installed: Sequence[str]) -> bool:
    """Exact match, or untagged name with `name:latest` installed (ST-3)."""
    if model in installed:
        return True
    return ":" not in model and f"{model}:latest" in installed


async def probe_status(base_url: str, model: str, http: httpx.AsyncClient) -> ModelStatus:
    """GET {root}/api/tags with a 2 s timeout; never raises (ST-2)."""
    url = f"{server_root(base_url)}/api/tags"
    try:
        async with asyncio.timeout(STATUS_TIMEOUT_S):
            response = await http.get(url, timeout=STATUS_TIMEOUT_S)
        response.raise_for_status()
        data = response.json()
        names = [str(m.get("name", "")) for m in data.get("models", []) if isinstance(m, dict)]
    except (httpx.HTTPError, TimeoutError, ValueError, AttributeError) as exc:
        log.info(kv("status.check", reachable=False, reason=type(exc).__name__))
        return ModelStatus(
            reachable=False, model_installed=False, model_name=model, base_url=base_url
        )
    installed = model_is_installed(model, names)
    log.info(kv("status.check", reachable=True, installed=installed, model=model))
    return ModelStatus(
        reachable=True, model_installed=installed, model_name=model, base_url=base_url
    )


class OllamaClient:
    """LLMClient over Ollama's OpenAI-compatible API. No retries (AL-8, NP-1)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: float = MODEL_CALL_TIMEOUT_S,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url
        self.model = model
        self._client = openai.AsyncOpenAI(
            base_url=base_url, api_key="ollama", timeout=timeout_s, max_retries=0
        )
        self._http = http

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMReply:
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        if response_format is not None:
            kwargs["response_format"] = response_format
        completion = await self._client.chat.completions.create(**kwargs)
        message = completion.choices[0].message
        calls = [
            ToolCall(id=c.id or None, name=c.function.name, arguments_json=c.function.arguments)
            for c in (message.tool_calls or [])
            if getattr(c, "function", None) is not None
        ]
        return LLMReply(content=message.content, tool_calls=calls)

    async def status(self) -> ModelStatus:
        if self._http is not None:
            return await probe_status(self.base_url, self.model, self._http)
        async with httpx.AsyncClient() as http:
            return await probe_status(self.base_url, self.model, http)


class FakeLLMClient:
    """Scripted LLMClient for tests. Each chat() returns the next reply (or raises it)."""

    def __init__(
        self,
        script: Sequence[LLMReply | BaseException],
        delay_s: float = 0.0,
        status_value: ModelStatus | None = None,
    ) -> None:
        self._script = list(script)
        self.delay_s = delay_s
        self.calls: list[list[dict[str, Any]]] = []
        self.tools_seen: list[list[dict[str, Any]] | None] = []
        self._status = status_value or ModelStatus(
            reachable=True, model_installed=True, model_name="fake", base_url="http://localhost/v1"
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMReply:
        self.calls.append([dict(m) for m in messages])
        self.tools_seen.append(tools)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if not self._script:
            raise AssertionError("FakeLLMClient script is empty")
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    async def status(self) -> ModelStatus:
        return self._status
