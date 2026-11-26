# ADDED [PROMPT #13]: logging setup (NP-7). AI-assisted, Claude Opus 5.5.
"""Plain-text logging with a job id on every line.

Logs never hold note text, journal text, prompts, replies or unrounded
coordinates: callers pass only ids, counts, tool names and timings.
"""

from __future__ import annotations

import logging
import os
import sys
from contextvars import ContextVar

from trip_journal.config import ENV_LOG_LEVEL

current_job_id: ContextVar[str | None] = ContextVar("current_job_id", default=None)

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s job_id=%(job_id)s %(message)s"
_VALID_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_HANDLER_MARK = "_trip_journal_handler"


class JobIdFilter(logging.Filter):
    """Adds `job_id` to each record; `-` outside a job."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.job_id = current_job_id.get() or "-"
        return True


def kv(event: str, **fields: object) -> str:
    """Format `event key=value ...`; values with spaces, quotes or empty use repr."""
    parts = [event]
    for key, value in fields.items():
        text = str(value)
        if text == "" or any(ch.isspace() or ch in "\"'" for ch in text):
            text = repr(text)
        parts.append(f"{key}={text}")
    return " ".join(parts)


def setup_logging(level_name: str | None = None) -> None:
    """Configure the root logger (safe to call more than once)."""
    raw = level_name if level_name is not None else os.environ.get(ENV_LOG_LEVEL, "INFO")
    wanted = raw.strip().upper()
    invalid = wanted not in _VALID_LEVELS
    root = logging.getLogger()
    for old in list(root.handlers):
        if getattr(old, _HANDLER_MARK, False):
            root.removeHandler(old)
    handler = logging.StreamHandler(sys.stderr)
    setattr(handler, _HANDLER_MARK, True)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(JobIdFilter())
    root.addHandler(handler)
    root.setLevel(logging.INFO if invalid else getattr(logging, wanted))
    if invalid:
        logging.getLogger("trip_journal.logs").warning(kv("log.level_invalid", value=raw[:20]))
