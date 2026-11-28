# ADDED [PROMPT #13]: grounding check (C15, GR-1..GR-7). AI-assisted, Claude Opus 5.5.
"""Split model text into sentences and check that each one cites known records.

Pure functions, no I/O. Known limitation (GR-7): abbreviations such as "St." end a
sentence, so each part is checked on its own.
"""

from __future__ import annotations

import re
from typing import Literal, NamedTuple

from trip_journal.config import NOT_IN_RECORDS

CitationKind = Literal["stop", "note", "photo"]

# CHANGED [PROMPT #36]: ids capped at 18 digits; longer ones broke int() on every read (D-16).
CITATION_RE = re.compile(r"\[(stop|note|photo):([1-9][0-9]{0,17})\]")
# End of sentence: . ! ? followed by whitespace or end of line, or a CJK full stop / mark.
_END_RE = re.compile(r"[.!?](?=\s|$)|[。！？]")
# Citations right after the end punctuation stay with the sentence before (GR-2).
_TRAILING_CITES_RE = re.compile(r"(?:\s*\[(?:stop|note|photo):[1-9][0-9]{0,17}\])+")


class Citation(NamedTuple):
    kind: str
    record_id: int

    def __str__(self) -> str:
        return f"[{self.kind}:{self.record_id}]"


class SentenceCheck(NamedTuple):
    sentence: str
    citations: list[Citation]
    supported: bool
    exempt: bool


def _split_line(line: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    pos = 0
    while True:
        match = _END_RE.search(line, pos)
        if match is None:
            break
        end = match.end()
        cites = _TRAILING_CITES_RE.match(line, end)
        if cites is not None:
            end = cites.end()
        piece = line[start:end].strip()
        if piece:
            sentences.append(piece)
        start = pos = end
    rest = line[start:].strip()
    if rest:
        sentences.append(rest)
    return sentences


def split_sentences(text: str) -> list[str]:
    """Lines → sentences (GR-1, GR-2). Blank lines are skipped; headings are kept."""
    sentences: list[str] = []
    for line in text.splitlines():
        if line.strip():
            sentences.extend(_split_line(line))
    return sentences


def extract_citations(sentence: str) -> list[Citation]:
    """All `[kind:N]` citations in order, duplicates kept (GR-3, GR-4)."""
    return [Citation(m.group(1), int(m.group(2))) for m in CITATION_RE.finditer(sentence)]


def _check(sentence: str, known_ids: set[Citation], allow_not_in_records: bool) -> SentenceCheck:
    citations = extract_citations(sentence)
    exempt = allow_not_in_records and sentence.strip() == NOT_IN_RECORDS
    supported = exempt or (bool(citations) and all(c in known_ids for c in citations))
    return SentenceCheck(sentence, citations, supported, exempt)


def check_text(
    text: str, known_ids: set[Citation], allow_not_in_records: bool = False
) -> list[SentenceCheck]:
    """One SentenceCheck per sentence (GR-5, GR-6)."""
    return [_check(s, known_ids, allow_not_in_records) for s in split_sentences(text)]


def find_unsupported_sentences(
    text: str, known_ids: set[Citation], allow_not_in_records: bool = False
) -> list[str]:
    return [
        c.sentence for c in check_text(text, known_ids, allow_not_in_records) if not c.supported
    ]
