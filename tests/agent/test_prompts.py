# ADDED [PROMPT #13]: prompt library tests (C16). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

from pathlib import Path

import pytest

from trip_journal.agent.prompts import PromptLibrary
from trip_journal.config import NOT_IN_RECORDS


def test_shared_text_is_appended_and_tone_variant_wins(tmp_path: Path) -> None:
    (tmp_path / "_shared_tool_data.md").write_text("SHARED", encoding="utf-8")
    (tmp_path / "journal.md").write_text("plain", encoding="utf-8")
    (tmp_path / "journal_warm.md").write_text("warm", encoding="utf-8")
    lib = PromptLibrary(tmp_path)
    assert lib.get("journal") == "plain\n\nSHARED"
    assert lib.get("journal", tone="warm") == "warm\n\nSHARED"
    assert lib.get("journal", tone="cold") == "plain\n\nSHARED"


def test_bad_or_missing_names(tmp_path: Path) -> None:
    lib = PromptLibrary(tmp_path)
    with pytest.raises(ValueError):
        lib.get("../secrets")
    with pytest.raises(KeyError):
        lib.get("missing")


def test_version_changes_with_content(tmp_path: Path) -> None:
    lib = PromptLibrary(tmp_path)
    (tmp_path / "a.md").write_text("one", encoding="utf-8")
    first = lib.version()
    assert len(first) == 12 and lib.version() == first
    (tmp_path / "a.md").write_text("two", encoding="utf-8")
    assert lib.version() != first


def test_shipped_shared_text_mentions_rules() -> None:
    text = (Path(PromptLibrary().directory) / "_shared_tool_data.md").read_text(encoding="utf-8")
    assert NOT_IN_RECORDS in text and "[note:" in text
