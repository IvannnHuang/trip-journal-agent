# ADDED [PROMPT #13]: settings tests (SE-1..SE-7, ST-1..ST-3). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import logging

import httpx
import pytest

from tests.conftest import FakeOllama
from trip_journal.config import DEFAULT_MODEL, DEFAULT_OLLAMA_BASE_URL
from trip_journal.data.repositories import Repositories
from trip_journal.services.errors import SettingsValidationError
from trip_journal.services.settings import (
    SettingsService,
    SettingsUpdate,
    normalize_base_url,
    parse_bool,
    validate_model,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://localhost:11434/v1", "http://localhost:11434/v1"),
        ("http://localhost:11434", "http://localhost:11434/v1"),
        ("  http://127.0.0.1:8080/v1/ ", "http://127.0.0.1:8080/v1"),
        ("http://[::1]:11434", "http://[::1]:11434/v1"),
        ("http://LOCALHOST/", "http://localhost/v1"),
    ],
)
def test_base_url_accepts_local_http(raw: str, expected: str) -> None:
    assert normalize_base_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "https://localhost:11434/v1",
        "http://example.com:11434/v1",
        "http://192.168.1.5:11434/v1",
        "http://user@localhost:11434/v1",
        "http://localhost:11434/v1?x=1",
        "http://localhost:11434/v1#f",
        "http://localhost:0/v1",
        "http://localhost:99999/v1",
        "http://localhost:/v1",
        "http://localhost:11434/api",
        "http://localhost.evil.com/v1",
        "file:///etc/passwd",
        "http://local host/v1",
    ],
)
def test_base_url_rejects_others(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_base_url(raw)


def test_model_name_rules() -> None:
    assert validate_model(" qwen3:8b ") == "qwen3:8b"
    assert validate_model("library/llama3.2:latest") == "library/llama3.2:latest"
    for bad in ["", "a b", "a:b:c", "x" * 101, "m;rm"]:
        with pytest.raises(ValueError):
            validate_model(bad)


def test_parse_bool() -> None:
    assert parse_bool(" ON ") is True and parse_bool("0") is False and parse_bool(True) is True
    with pytest.raises(ValueError):
        parse_bool("maybe")


def test_precedence_saved_then_env_then_default(
    repos: Repositories, caplog: pytest.LogCaptureFixture
) -> None:
    env = {"TRIP_JOURNAL_MODEL": "llama3.2", "TRIP_JOURNAL_OLLAMA_BASE_URL": "http://evil.com/v1"}
    service = SettingsService(repos.settings, env=env)
    with caplog.at_level(logging.WARNING):
        got = service.get()
    assert got.model_name == "llama3.2"
    assert got.ollama_base_url == DEFAULT_OLLAMA_BASE_URL  # SE-6: bad env value skipped
    assert got.place_lookup_enabled is False
    assert "settings.fallback" in caplog.text and "evil.com" not in caplog.text
    service.update(SettingsUpdate(model_name="mistral"))
    assert service.get().model_name == "mistral"


def test_defaults_without_env(repos: Repositories) -> None:
    assert SettingsService(repos.settings, env={}).get().model_name == DEFAULT_MODEL


def test_update_is_all_or_nothing(repos: Repositories) -> None:
    service = SettingsService(repos.settings, env={})
    with pytest.raises(SettingsValidationError) as info:
        service.update(SettingsUpdate(model_name="ok-model", ollama_base_url="http://example.com"))
    assert set(info.value.issues) == {"ollama_base_url"}
    assert repos.settings.get_all() == {}


def test_update_normalises_and_stores_text(repos: Repositories) -> None:
    service = SettingsService(repos.settings, env={})
    got = service.update(
        SettingsUpdate(ollama_base_url="http://127.0.0.1:11434", place_lookup_enabled="yes")
    )
    assert got.ollama_base_url == "http://127.0.0.1:11434/v1"
    assert repos.settings.get_all()["place_lookup_enabled"] == "true"


async def test_model_status_checks_each_time(repos: Repositories, ollama: FakeOllama) -> None:
    http = httpx.AsyncClient(transport=httpx.MockTransport(ollama.handler))
    service = SettingsService(repos.settings, env={}, http=http)
    assert (await service.model_status()).ok
    ollama.models = ["other:1b"]
    status = await service.model_status()
    assert status.reachable and not status.model_installed
    ollama.up = False
    assert not (await service.model_status()).reachable
    assert len(ollama.requests) == 3  # ST-1: never cached
    assert str(ollama.requests[0].url) == "http://localhost:11434/api/tags"


async def test_untagged_model_matches_latest(repos: Repositories, ollama: FakeOllama) -> None:
    http = httpx.AsyncClient(transport=httpx.MockTransport(ollama.handler))
    service = SettingsService(repos.settings, env={"TRIP_JOURNAL_MODEL": "llama3.2"}, http=http)
    assert (await service.model_status()).model_installed


async def test_bad_tags_reply_is_unreachable(repos: Repositories) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    status = await SettingsService(repos.settings, env={}, http=http).model_status()
    assert not status.reachable
