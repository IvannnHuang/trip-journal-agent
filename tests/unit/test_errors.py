# ADDED [PROMPT #13]: error mapping tests (ER-1..ER-3). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import pytest

from trip_journal.agent.llm import ModelStatus
from trip_journal.services.errors import (
    NOTHING_CHANGED,
    AgentStepLimitError,
    JobTimeoutError,
    ModelBusyError,
    ModelCallError,
    ModelUnavailableError,
    NotFoundError,
    status_message,
    to_user_facing,
)

DOWN = ModelStatus(
    reachable=False, model_installed=False, model_name="m", base_url="http://localhost:11434/v1"
)
MISSING = ModelStatus(reachable=True, model_installed=False, model_name="qwen3:8b", base_url="u")
READY = ModelStatus(reachable=True, model_installed=True, model_name="m", base_url="u")


def test_status_message() -> None:
    down = status_message(DOWN)
    assert down is not None and down.code == "ollama_unreachable"
    assert "http://localhost:11434/v1" in down.message
    assert "ollama serve" in down.action
    missing = status_message(MISSING)
    assert missing is not None and missing.code == "model_missing"
    assert "ollama pull qwen3:8b" in missing.action
    assert status_message(READY) is None


@pytest.mark.parametrize(
    ("exc", "code", "failed"),
    [
        (ModelUnavailableError(DOWN), "ollama_unreachable", True),
        (ModelUnavailableError(MISSING), "model_missing", True),
        (ModelBusyError("x"), "model_busy", False),
        (AgentStepLimitError(["t"]), "step_limit", True),
        (ModelCallError("timeout"), "model_timeout", True),
        (ModelCallError("error"), "model_error", True),
        (JobTimeoutError("x"), "job_timeout", True),
        (NotFoundError("x"), "job_not_found", False),
        (RuntimeError("secret detail"), "internal_error", True),
    ],
)
def test_to_user_facing(exc: BaseException, code: str, failed: bool) -> None:
    err = to_user_facing(exc)
    assert err.code == code
    assert err.message.endswith(NOTHING_CHANGED) is failed
    assert "secret detail" not in err.message


def test_trace_is_kept() -> None:
    assert to_user_facing(AgentStepLimitError(["a", "b"])).trace == ["a", "b"]
    assert to_user_facing(ModelCallError("timeout", ["c"])).trace == ["c"]
