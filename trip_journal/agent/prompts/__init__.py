# ADDED [PROMPT #13]: prompt library (C16). AI-assisted, Claude Opus 5.5.
"""Prompts live as Markdown files next to this module; `version` records which set was used."""

from __future__ import annotations

import hashlib
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent
SHARED_FILE = "_shared_tool_data.md"


class PromptLibrary:
    def __init__(self, directory: Path = PROMPTS_DIR) -> None:
        self.directory = directory

    # CHANGED [PROMPT #25]: `shared=False` leaves out the tool-data text (U3 D-15).
    def get(self, name: str, tone: str | None = None, shared: bool = True) -> str:
        """`<name>.md` (or `<name>_<tone>.md` if present) plus the shared tool-data text."""
        if not name.replace("_", "").isalnum():
            raise ValueError(f"bad prompt name {name!r}")
        candidates = [f"{name}_{tone}.md"] if tone else []
        candidates.append(f"{name}.md")
        for file_name in candidates:
            path = self.directory / file_name
            if path.is_file():
                text = path.read_text(encoding="utf-8").strip()
                shared_path = self.directory / SHARED_FILE
                if shared and shared_path.is_file():
                    text = f"{text}\n\n{shared_path.read_text(encoding='utf-8').strip()}"
                return text
        raise KeyError(f"prompt {name!r} not found")

    def version(self) -> str:
        """Short hash over every prompt file's name and content."""
        digest = hashlib.sha256()
        for path in sorted(self.directory.glob("*.md")):
            digest.update(path.name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()[:12]
