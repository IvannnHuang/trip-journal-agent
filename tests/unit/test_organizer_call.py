# ADDED [PROMPT #25]: U3 plan step 17, the model call (N-1..N-3, D-2, D-3).
# AI-assisted, Claude Opus 5.5. No network: the SDK call is replaced by a recorder.
"""OllamaClient sends `reasoning_effort` / `timeout` only when set; SDK timeouts end a batch."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import httpx2
import openai
import pytest

from trip_journal.agent.llm import FakeLLMClient, OllamaClient
from trip_journal.agent.organizer import RESPONSE_FORMAT, NoteOrganizer
from trip_journal.agent.prompts import PromptLibrary
from trip_journal.config import ORGANIZER_CALL_TIMEOUT_S
from trip_journal.data.repositories import NoteRow
from trip_journal.domain.organizer import BatchInput

DAY = "2026-06-01"
BATCH = BatchInput(
    day=DAY, stops=(), notes=(NoteRow(1, 1, None, "n1", "tea", f"{DAY}T08:00:00Z", 0, DAY),)
)


class Recorder:
    def __init__(self) -> None:
        self.kwargs: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs.append(kwargs)
        message = SimpleNamespace(content='{"suggestions": []}', tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> tuple[OllamaClient, Recorder]:
    client = OllamaClient("http://localhost:11434/v1", "qwen3:8b")
    recorder = Recorder()
    monkeypatch.setattr(client._client.chat.completions, "create", recorder.create)
    return client, recorder


async def test_agent_call_sends_no_new_keys(recorded: tuple[OllamaClient, Recorder]) -> None:
    client, recorder = recorded
    await client.chat([{"role": "user", "content": "hi"}])
    assert set(recorder.kwargs[0]) == {"model", "messages"}  # U1 calls unchanged


async def test_organizer_call_sends_schema_effort_and_timeout(
    recorded: tuple[OllamaClient, Recorder],
) -> None:
    client, recorder = recorded
    result = await NoteOrganizer(client, PromptLibrary()).organize_batch(BATCH)
    assert result.outcome == "ok"
    sent = recorder.kwargs[0]
    assert sent["response_format"] == RESPONSE_FORMAT
    assert sent["response_format"]["type"] == "json_schema"
    assert sent["reasoning_effort"] == "none"
    assert sent["timeout"] == ORGANIZER_CALL_TIMEOUT_S  # D-3: past the SDK's 120 s default
    assert "tools" not in sent


async def test_sdk_timeout_is_call_timeout() -> None:
    error = openai.APITimeoutError(
        request=httpx2.Request("POST", "http://localhost/v1")
    )  # the SDK uses httpx2
    result = await NoteOrganizer(FakeLLMClient([error]), PromptLibrary()).organize_batch(BATCH)
    assert result.outcome == "call_timeout"
    assert result.not_organized == [1]


async def test_http_error_is_model_error() -> None:
    error = httpx.ConnectError("refused")
    result = await NoteOrganizer(FakeLLMClient([error]), PromptLibrary()).organize_batch(BATCH)
    assert result.outcome == "model_error"
