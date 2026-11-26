# ADDED [PROMPT #13]: shared Hypothesis strategies (NP-8). AI-assisted, Claude Opus 5.5.
"""Generators for sentences, citations, URLs, model names and tool payloads."""

from __future__ import annotations

from hypothesis import strategies as st

from trip_journal.domain.grounding import Citation

KINDS = ("stop", "note", "photo")

citations = st.builds(Citation, st.sampled_from(KINDS), st.integers(min_value=1, max_value=10_000))

# Words without sentence-ending punctuation, brackets or newlines.
_word_chars = st.characters(
    categories=("L", "N"), exclude_characters="[]。！？", max_codepoint=0x2FFF
)
words = st.text(_word_chars, min_size=1, max_size=8)


@st.composite
def sentences(draw: st.DrawFn, known: list[Citation] | None = None) -> str:
    """One sentence: words, optional citations, then `.`, `!` or `?`."""
    body = " ".join(draw(st.lists(words, min_size=1, max_size=6)))
    pool = st.sampled_from(known) if known else citations
    cites = draw(st.lists(pool, max_size=3))
    tail = "".join(f" {c}" for c in cites)
    return f"{body}{tail}{draw(st.sampled_from('.!?'))}"


@st.composite
def paragraphs(draw: st.DrawFn) -> str:
    return " ".join(draw(st.lists(sentences(), min_size=1, max_size=5)))


model_names = st.from_regex(r"\A[A-Za-z0-9._\-/]{1,40}(:[A-Za-z0-9._\-]{1,20})?\Z")

hosts = st.sampled_from(["localhost", "127.0.0.1", "[::1]", "LOCALHOST"])
ports = st.one_of(st.none(), st.integers(min_value=1, max_value=65535))
paths = st.sampled_from(["", "/", "/v1", "/v1/"])


@st.composite
def allowed_urls(draw: st.DrawFn) -> str:
    port = draw(ports)
    return f"http://{draw(hosts)}{'' if port is None else f':{port}'}{draw(paths)}"


json_scalars = st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=30))
json_values = st.recursive(
    json_scalars,
    lambda inner: st.one_of(
        st.lists(inner, max_size=4), st.dictionaries(st.text(max_size=8), inner, max_size=4)
    ),
    max_leaves=12,
)

coordinates = st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False)
