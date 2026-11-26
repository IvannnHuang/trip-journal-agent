# ADDED [PROMPT #13]: settings resolution, validation, model status (C08, SE-1..7, ST-1..7).
# AI-assisted, Claude Opus 5.5.
"""Settings: saved value -> environment variable -> default, each validated."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel

from trip_journal.agent.llm import ModelStatus, probe_status
from trip_journal.config import (
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_PLACE_LOOKUP,
    ENV_MODEL,
    ENV_OLLAMA_BASE_URL,
    ENV_PLACE_LOOKUP,
)
from trip_journal.data.repositories import SettingsRepository
from trip_journal.logs import kv
from trip_journal.services.errors import SettingsValidationError

log = logging.getLogger(__name__)

KEY_MODEL = "model_name"
KEY_BASE_URL = "ollama_base_url"
KEY_PLACE_LOOKUP = "place_lookup_enabled"

MODEL_RE = re.compile(r"^[A-Za-z0-9._\-/]+(:[A-Za-z0-9._\-]+)?$")
ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}
TRUE_WORDS = {"1", "true", "yes", "on"}
FALSE_WORDS = {"0", "false", "no", "off"}


class Settings(BaseModel):
    model_name: str
    ollama_base_url: str
    place_lookup_enabled: bool


class SettingsUpdate(BaseModel):
    """`None` = leave unchanged. Values are raw user input; the service validates them."""

    model_name: str | None = None
    ollama_base_url: str | None = None
    place_lookup_enabled: bool | str | None = None


# ---------- validators: return the normalised value or raise ValueError ----------


def validate_model(value: str) -> str:
    """SE-2."""
    name = value.strip()
    if not 1 <= len(name) <= 100:
        raise ValueError("Enter a model name of 1 to 100 characters.")
    if not MODEL_RE.match(name):
        raise ValueError("Use a model name like qwen3:8b (letters, digits, . _ - / and one :tag).")
    return name


def normalize_base_url(value: str) -> str:
    """SE-3: http on localhost / 127.0.0.1 / [::1] only; path becomes /v1 (SE-7: idempotent)."""
    text = value.strip()
    message = "Use a local address such as http://localhost:11434/v1."
    if not text or any(c.isspace() for c in text):
        raise ValueError(message)
    parts = urlsplit(text)
    if parts.scheme != "http" or parts.query or parts.fragment or "@" in parts.netloc:
        raise ValueError(message)
    if text.endswith(("?", "#")) or ";" in parts.path:
        raise ValueError(message)
    host = parts.hostname
    if host not in ALLOWED_HOSTS:
        raise ValueError(message)
    if host == "::1" and not parts.netloc.lower().startswith("[::1]"):
        raise ValueError(message)
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError(message) from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError(message)
    netloc_tail = parts.netloc.split("]")[-1] if host == "::1" else parts.netloc
    if netloc_tail.endswith(":"):  # "http://localhost:/v1" — empty port
        raise ValueError(message)
    path = parts.path.rstrip("/")
    if path not in ("", "/v1"):
        raise ValueError(message)
    shown_host = "[::1]" if host == "::1" else host
    return f"http://{shown_host}{f':{port}' if port is not None else ''}/v1"


def parse_bool(value: bool | str) -> bool:
    """SE-4."""
    if isinstance(value, bool):
        return value
    word = value.strip().lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    raise ValueError("Use on or off.")


def _to_text(key: str, value: Any) -> str:
    if key == KEY_PLACE_LOOKUP:
        return "true" if value else "false"
    return str(value)


_FIELDS: dict[str, tuple[Callable[[Any], Any], str, Any]] = {
    KEY_MODEL: (validate_model, ENV_MODEL, DEFAULT_MODEL),
    KEY_BASE_URL: (normalize_base_url, ENV_OLLAMA_BASE_URL, DEFAULT_OLLAMA_BASE_URL),
    KEY_PLACE_LOOKUP: (parse_bool, ENV_PLACE_LOOKUP, DEFAULT_PLACE_LOOKUP),
}


class SettingsService:
    def __init__(
        self,
        repo: SettingsRepository,
        env: Mapping[str, str] | None = None,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.repo = repo
        self.env = os.environ if env is None else env
        self.http = http

    def get(self) -> Settings:
        """SE-1 and SE-6: the first valid value of saved -> env -> default, per field."""
        saved = self.repo.get_all()
        values: dict[str, Any] = {}
        for key, (validate, env_name, default) in _FIELDS.items():
            values[key] = default
            for source, raw in (("saved", saved.get(key)), ("env", self.env.get(env_name))):
                if raw is None:
                    continue
                try:
                    values[key] = validate(raw)
                    break
                except ValueError:
                    log.warning(kv("settings.fallback", key=key, source=source))
        return Settings(**values)

    def update(self, change: SettingsUpdate) -> Settings:
        """SE-5: validate every given field first; save all in one transaction or nothing."""
        issues: dict[str, str] = {}
        normalised: dict[str, str] = {}
        for key, (validate, _env, _default) in _FIELDS.items():
            raw = getattr(change, key)
            if raw is None:
                continue
            try:
                normalised[key] = _to_text(key, validate(raw))
            except ValueError as exc:
                issues[key] = str(exc)
        if issues:
            raise SettingsValidationError(issues)
        if normalised:
            self.repo.set_many(normalised)
            log.info(kv("settings.saved", keys=",".join(sorted(normalised))))
        return self.get()

    async def model_status(self, settings: Settings | None = None) -> ModelStatus:
        """ST-1, ST-2: checked fresh every time, never cached."""
        current = settings or self.get()
        if self.http is not None:
            return await probe_status(current.ollama_base_url, current.model_name, self.http)
        async with httpx.AsyncClient() as http:
            return await probe_status(current.ollama_base_url, current.model_name, http)
