# ADDED [PROMPT #13]: errors and user-facing messages (ER-1..ER-3). AI-assisted, Claude Opus 5.5.
"""Typed errors and the fixed wording users see."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel

NOTHING_CHANGED = "Nothing you saved was changed."


class StatusLike(Protocol):
    base_url: str
    model_name: str
    reachable: bool
    model_installed: bool


class UserFacingError(BaseModel):
    code: str
    message: str
    action: str
    trace: list[Any] = []


class AppError(Exception):
    """Base class for errors the app knows how to show."""

    http_status = 500


class ModelUnavailableError(AppError):
    http_status = 503

    def __init__(self, status: StatusLike) -> None:
        super().__init__("model unavailable")
        self.status = status


class ModelBusyError(AppError):
    http_status = 429


class AgentStepLimitError(AppError):
    def __init__(self, trace: list[Any] | None = None) -> None:
        super().__init__("step limit")
        self.trace = trace or []


class ModelCallError(AppError):
    def __init__(self, reason: str, trace: list[Any] | None = None) -> None:
        super().__init__(f"model call {reason}")
        self.reason = reason  # "timeout" or "error"
        self.trace = trace or []


class JobTimeoutError(AppError):
    pass


class SettingsValidationError(AppError):
    http_status = 422

    def __init__(self, issues: dict[str, str]) -> None:
        super().__init__("invalid settings")
        self.issues = issues


class NotFoundError(AppError):
    http_status = 404


def status_message(status: StatusLike) -> UserFacingError | None:
    """Banner text for a model status; None when the model is ready (ER-1)."""
    if not status.reachable:
        return UserFacingError(
            code="ollama_unreachable",
            message=(
                f"The local model is not available. Ollama is not running at {status.base_url}."
            ),
            action="Start Ollama (open the Ollama app or run `ollama serve`), then try again.",
        )
    if not status.model_installed:
        return UserFacingError(
            code="model_missing",
            message=f"The model {status.model_name} is not installed in Ollama.",
            action=f"Run `ollama pull {status.model_name}`, then try again.",
        )
    return None


def _failed(code: str, message: str, action: str, trace: list[Any]) -> UserFacingError:
    # ER-3: every failed job says nothing saved changed; the UI offers Try again.
    return UserFacingError(
        code=code, message=f"{message} {NOTHING_CHANGED}", action=action, trace=trace
    )


def to_user_facing(exc: BaseException) -> UserFacingError:
    """Map an exception to fixed wording (ER-1). Unknown errors reveal no details."""
    if isinstance(exc, ModelUnavailableError):
        err = status_message(exc.status)
        if err is not None:
            return _failed(err.code, err.message, err.action, [])
    if isinstance(exc, ModelBusyError):
        return UserFacingError(
            code="model_busy",
            message="Another request is still running.",
            action="Wait for it to finish, then try again.",
        )
    if isinstance(exc, AgentStepLimitError):
        return _failed(
            "step_limit",
            "The agent could not finish within 8 steps.",
            "Try again, or ask a narrower question.",
            exc.trace,
        )
    if isinstance(exc, ModelCallError):
        if exc.reason == "timeout":
            return _failed(
                "model_timeout", "The model did not respond in time.", "Try again.", exc.trace
            )
        return _failed("model_error", "The model returned an error.", "Try again.", exc.trace)
    if isinstance(exc, JobTimeoutError):
        return _failed(
            "job_timeout",
            "This took too long (over 5 minutes) and was stopped.",
            "Try again, or ask a narrower question.",
            [],
        )
    if isinstance(exc, NotFoundError):
        return UserFacingError(
            code="job_not_found",
            message="This request is no longer available.",
            action="Start it again.",
        )
    return _failed("internal_error", "Something went wrong on the server.", "Try again.", [])
