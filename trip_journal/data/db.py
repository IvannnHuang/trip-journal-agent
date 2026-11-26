# ADDED [PROMPT #13]: SQLite connection and schema (C21). AI-assisted, Claude Opus 5.5.
"""SQLite access. Sync calls, used directly in the event loop (NP-6): no await inside a
transaction, and every query is small and indexed."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(path: Path | str) -> sqlite3.Connection:
    """Open a connection with foreign keys on and rows addressable by column name."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables, indexes, the FTS5 index and its triggers (idempotent)."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Commit on success, roll back on any exception."""
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()
