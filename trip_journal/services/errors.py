# ADDED [PROMPT #13]: errors and user-facing messages (ER-1..ER-3). AI-assisted, Claude Opus 5.5.
"""Typed errors and the fixed wording users see."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel

from trip_journal.domain.import_schema import ImportIssue

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


# ADDED [PROMPT #36]: journal generation and edit preconditions.
class NoRecordsError(AppError):
    http_status = 422


class ParagraphTooLongError(AppError):
    http_status = 422


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
    # CHANGED [PROMPT #25]: carries the limit used, since organize jobs scale it (U3 D-4).
    def __init__(self, detail: str = "job timeout", limit_s: float = 300.0) -> None:
        super().__init__(detail)
        self.limit_s = limit_s


# ADDED [PROMPT #17]: CI-3, a manual cancel is not a timeout.
class JobCancelledError(AppError):
    pass


class SettingsValidationError(AppError):
    http_status = 422

    def __init__(self, issues: dict[str, str]) -> None:
        super().__init__("invalid settings")
        self.issues = issues


# CHANGED [PROMPT #17]: optional code (IC-5) so U2 can raise trip_not_found / day_not_found.
NOT_FOUND_MESSAGES = {
    # ADDED [PROMPT #36]: journal and paragraph lookup failures.
    "journal_not_found": ("No journal has been written for this day.", "Write a journal first."),
    "slot_not_found": ("This paragraph does not exist.", "Open the journal again."),
    "job_not_found": ("This request is no longer available.", "Start it again."),
    "trip_not_found": (
        "This trip does not exist. It may have been deleted.",
        "Open the trip list.",
    ),
    "day_not_found": ("This trip has no records on that date.", "Open the trip overview."),
    # ADDED [PROMPT #25]: U3 OR-E2.
    "suggestion_not_found": (
        "This suggestion does not exist. The trip may have been deleted.",
        "Open the day again.",
    ),
}


class NotFoundError(AppError):
    http_status = 404

    def __init__(self, detail: str = "not found", code: str = "job_not_found") -> None:
        super().__init__(detail)
        self.code = code


# ADDED [PROMPT #17]: U2 import and delete errors (IC-5, R.5).
class ImportValidationError(AppError):
    """422 import_invalid: at most 50 issues, `more` were left out."""

    http_status = 422

    def __init__(self, issues: list[ImportIssue], more: int = 0) -> None:
        super().__init__("import invalid")
        self.issues = issues
        self.more = more


class TripAlreadyExistsError(AppError):
    http_status = 409

    def __init__(self, source_id: str) -> None:
        super().__init__("trip exists")
        self.source_id = source_id


class JobRunningError(AppError):
    http_status = 409


# ADDED [PROMPT #25]: U3 review errors (IC-9, OR-E3, OR-E4).
class SuggestionStateError(AppError):
    """409 suggestion_state: the action is not allowed from the row's status."""

    http_status = 409

    def __init__(self, status: str) -> None:
        super().__init__("suggestion state")
        self.status = status


class SuggestionEditError(AppError):
    """422 invalid_edit with one message per field."""

    http_status = 422

    def __init__(self, fields: dict[str, str]) -> None:
        super().__init__("invalid edit")
        self.fields = fields


def minutes_text(limit_s: float) -> str:
    minutes = max(1, round(limit_s / 60))
    return "1 minute" if minutes == 1 else f"{minutes} minutes"


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


def _is_file_issue(exc: ImportValidationError) -> bool:
    return len(exc.issues) == 1 and exc.issues[0].location == "file"


def to_user_facing(exc: BaseException) -> UserFacingError:
    """Map an exception to fixed wording (ER-1). Unknown errors reveal no details."""
    if isinstance(exc, ModelUnavailableError):
        err = status_message(exc.status)
        if err is not None:
            return _failed(err.code, err.message, err.action, [])
    # ADDED [PROMPT #36]: fixed journal validation messages.
    if isinstance(exc, NoRecordsError):
        return UserFacingError(
            code="no_records", message="No records for this day.", action="Choose another day."
        )
    if isinstance(exc, ParagraphTooLongError):
        return UserFacingError(
            code="invalid_edit",
            message="Paragraph is too long (max 5000 characters).",
            action="Shorten the paragraph and save again.",
        )
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
        # ADDED [PROMPT #36]: surface the empty-run failure without echoing model output.
        if exc.reason == "The agent did not write any paragraph.":
            return _failed("model_error", exc.reason, "Regenerate to try again.", exc.trace)
        if exc.reason == "timeout":
            return _failed(
                "model_timeout", "The model did not respond in time.", "Try again.", exc.trace
            )
        return _failed("model_error", "The model returned an error.", "Try again.", exc.trace)
    if isinstance(exc, JobTimeoutError):
        return _failed(
            "job_timeout",
            f"This took too long (over {minutes_text(exc.limit_s)}) and was stopped.",
            "Try again, or ask a narrower question.",
            [],
        )
    # ADDED [PROMPT #17]: CI-3.
    if isinstance(exc, JobCancelledError):
        return _failed("job_cancelled", "The job was cancelled.", "Try again.", [])
    if isinstance(exc, NotFoundError):
        message, action = NOT_FOUND_MESSAGES.get(exc.code, NOT_FOUND_MESSAGES["job_not_found"])
        return UserFacingError(code=exc.code, message=message, action=action)
    # ADDED [PROMPT #17]: U2 import and delete errors.
    if isinstance(exc, ImportValidationError):
        message = exc.issues[0].message if _is_file_issue(exc) else "The file was not imported."
        return UserFacingError(
            code="import_invalid", message=message, action="Fix the file, then import it again."
        )
    if isinstance(exc, TripAlreadyExistsError):
        return UserFacingError(
            code="trip_exists",
            message=(
                f"A trip with the id '{exc.source_id}' is already imported. "
                "Delete it first, then import again."
            ),
            action="Delete the trip, then import again.",
        )
    if isinstance(exc, JobRunningError):
        return UserFacingError(
            code="job_running",
            message="A job is running. Wait for it to finish or cancel it, then delete the trip.",
            action="Wait for the job, then try again.",
        )
    # ADDED [PROMPT #25]: U3 review errors.
    if isinstance(exc, SuggestionStateError):
        return UserFacingError(
            code="suggestion_state",
            message=f"This suggestion was already {exc.status}. Undo it first.",
            action="Undo the decision, then try again.",
        )
    if isinstance(exc, SuggestionEditError):
        return UserFacingError(
            code="invalid_edit",
            message="Some fields are not valid.",
            action="Fix the marked fields, then save again.",
        )
    return _failed("internal_error", "Something went wrong on the server.", "Try again.", [])
