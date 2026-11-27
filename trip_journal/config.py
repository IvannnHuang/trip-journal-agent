# ADDED [PROMPT #13]: U1 Foundation constants (LC-1). AI-assisted, Claude Opus 5.5.
"""Fixed limits and defaults in one place, so code, tests and docs agree (LC-1)."""

from __future__ import annotations

from pathlib import Path
from typing import Final

# Timeouts in seconds (NP-1, NP-3, NP-4).
JOB_TIMEOUT_S: Final = 300.0
MODEL_CALL_TIMEOUT_S: Final = 120.0
STATUS_TIMEOUT_S: Final = 2.0
NOMINATIM_TIMEOUT_S: Final = 5.0
NOMINATIM_MIN_INTERVAL_S: Final = 1.0

# Agent and tool limits (AL-1, TA-6, TA-7).
MAX_AGENT_STEPS: Final = 8
MAX_TOOL_RECORDS: Final = 50
MAX_NOTE_CHARS: Final = 1000
TRUNCATION_SUFFIX: Final = "…(truncated)"
MAX_TOOL_ERROR_CHARS: Final = 200
MAX_RAW_ARGUMENTS_CHARS: Final = 200

# Jobs (JB-6).
MAX_FINISHED_JOBS: Final = 20

# Grounding (GR-5).
NOT_IN_RECORDS: Final = "That is not in your records."

# Settings defaults and environment names (SE-1).
DEFAULT_MODEL: Final = "qwen3:8b"
DEFAULT_OLLAMA_BASE_URL: Final = "http://localhost:11434/v1"
DEFAULT_PLACE_LOOKUP: Final = False
ENV_MODEL: Final = "TRIP_JOURNAL_MODEL"
ENV_OLLAMA_BASE_URL: Final = "TRIP_JOURNAL_OLLAMA_BASE_URL"
ENV_PLACE_LOOKUP: Final = "TRIP_JOURNAL_PLACE_LOOKUP"
ENV_LOG_LEVEL: Final = "TRIP_JOURNAL_LOG_LEVEL"
ENV_DB_PATH: Final = "TRIP_JOURNAL_DB"

# Places (NP-4).
NOMINATIM_URL: Final = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT: Final = "TripJournalAgent/0.1 (course project)"

# Server: bind to localhost only.
HOST: Final = "127.0.0.1"
PORT: Final = 8000
# ADDED [PROMPT #17]: CI-1 port override (D-7); an invalid value falls back to PORT.
PORT_ENV: Final = "TRIP_JOURNAL_PORT"

# ADDED [PROMPT #17]: U2 import limit (IM-1, U2-NFR-P.6).
MAX_IMPORT_BYTES: Final = 20 * 1024 * 1024

# ADDED [PROMPT #25]: U3 organizer limits (U3-NFR P.2, P.6, OR-RUN3, N-2, N-4).
ORGANIZER_CALL_TIMEOUT_S: Final = 240.0
ORGANIZER_BATCH_MAX_NOTES: Final = 10
ORGANIZER_BATCH_MAX_CHARS: Final = 6000
ORGANIZER_JOB_TIMEOUT_PER_BATCH_S: Final = 300.0
ORGANIZER_JOB_TIMEOUT_CAP_S: Final = 1800.0
ORGANIZER_REASONING_EFFORT: Final = "none"

PACKAGE_DIR: Final = Path(__file__).resolve().parent
DEFAULT_DB_PATH: Final = PACKAGE_DIR.parent / "data" / "trip_journal.db"
