# ADDED [PROMPT #13]: shared Hypothesis strategies (NP-8). AI-assisted, Claude Opus 5.5.
"""Generators for sentences, citations, URLs, model names and tool payloads."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from typing import Any

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


# ADDED [PROMPT #17]: trip file strategies and mutations (U2-NFR-T.4, PBT-07).
# AI-assisted, Claude Opus 5.5.
TripDict = dict[str, Any]

_EPOCH_MIN = int(datetime(2000, 1, 1, tzinfo=UTC).timestamp())
_EPOCH_MAX = int(datetime(2099, 12, 31, 23, 59, 59, tzinfo=UTC).timestamp())
_MAX_STOP_SECONDS = 36 * 3600

utc_seconds = st.integers(min_value=_EPOCH_MIN, max_value=_EPOCH_MAX)
offsets = st.integers(min_value=-48, max_value=56).map(lambda k: k * 15)
record_ids = st.text(_word_chars, min_size=1, max_size=12)
# Printable text, non-Latin included, no leading or trailing space (IM-9).
texts = st.lists(words, min_size=1, max_size=8).map(" ".join)
lats = st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False)
lons = st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False)


def utc_text(seconds: int) -> str:
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def encode(data: TripDict) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


@st.composite
def trip_files(
    draw: st.DrawFn, max_stops: int = 10, max_notes: int = 15, max_photos: int = 15
) -> TripDict:
    """A valid trip file as a JSON-ready dict (Functional Design §6)."""
    n_stops = draw(st.integers(min_value=1, max_value=max_stops))
    n_notes = draw(st.integers(min_value=0, max_value=max_notes))
    n_photos = draw(st.integers(min_value=0, max_value=max_photos))
    stop_ids = draw(st.lists(record_ids, min_size=n_stops, max_size=n_stops, unique=True))
    note_ids = draw(st.lists(record_ids, min_size=n_notes, max_size=n_notes, unique=True))
    photo_ids = draw(st.lists(record_ids, min_size=n_photos, max_size=n_photos, unique=True))
    stops = []
    for sid in stop_ids:
        start = draw(utc_seconds)
        end = min(start + draw(st.integers(0, _MAX_STOP_SECONDS)), _EPOCH_MAX)
        stop: TripDict = {
            "id": sid,
            "start_utc": utc_text(start),
            "end_utc": utc_text(end),
            "utc_offset_minutes": draw(offsets),
            "lat": draw(lats),
            "lon": draw(lons),
        }
        if draw(st.booleans()):
            stop["name"] = draw(texts)
        stops.append(stop)
    notes = []
    for nid in note_ids:
        note: TripDict = {
            "id": nid,
            "text": draw(texts),
            "time_utc": utc_text(draw(utc_seconds)),
            "utc_offset_minutes": draw(offsets),
        }
        if draw(st.booleans()):
            note["stop_id"] = draw(st.sampled_from(stop_ids))
        notes.append(note)
    photos = []
    for pid in photo_ids:
        photo: TripDict = {
            "id": pid,
            "time_utc": utc_text(draw(utc_seconds)),
            "utc_offset_minutes": draw(offsets),
        }
        if draw(st.booleans()):
            photo["lat"], photo["lon"] = draw(lats), draw(lons)
        if draw(st.booleans()):
            photo["file_name"] = draw(texts) + ".jpg"
        photos.append(photo)
    trip: TripDict = {"trip_id": draw(record_ids), "title": draw(texts)}
    if draw(st.booleans()):
        trip["home_timezone"] = draw(st.sampled_from(["Europe/Lisbon", "Asia/Tokyo", "UTC"]))
    data: TripDict = {"trip": trip, "stops": stops, "notes": notes, "photos": photos}
    if draw(st.booleans()):
        data["route_summary"] = draw(texts)
    return data


unknown_keys = st.from_regex(r"\Ax_[a-z]{1,8}\Z")


@st.composite
def with_unknown_key(draw: st.DrawFn, data: TripDict) -> tuple[TripDict, str]:
    """P-I3: one unknown key in one object; returns (file, expected issue location)."""
    out = copy.deepcopy(data)
    key = draw(unknown_keys)
    targets: list[tuple[str, int | None]] = [("", None), ("trip", None)]
    targets += [(name, i) for name in ("stops", "notes", "photos") for i in range(len(out[name]))]
    name, index = draw(st.sampled_from(targets))
    if name == "":
        out[key] = 1
        return out, key
    if index is None:
        out[name][key] = 1
        return out, f"{name}.{key}"
    out[name][index][key] = 1
    return out, f"{name}[{index}].{key}"


@st.composite
def with_end_before_start(draw: st.DrawFn, data: TripDict) -> tuple[TripDict, int]:
    """P-I4: one stop ends 1 s to 1 h before it starts; returns (file, stop index)."""
    out = copy.deepcopy(data)
    i = draw(st.integers(min_value=0, max_value=len(out["stops"]) - 1))
    start = datetime.fromisoformat(out["stops"][i]["start_utc"].replace("Z", "+00:00"))
    end = start - timedelta(seconds=draw(st.integers(min_value=1, max_value=3600)))
    out["stops"][i]["end_utc"] = end.strftime("%Y-%m-%dT%H:%M:%SZ")
    return out, i


@st.composite
def with_many_issues(draw: st.DrawFn, data: TripDict) -> tuple[TripDict, int]:
    """P-I5: append k notes with exactly one issue each (bad offset); returns (file, k)."""
    out = copy.deepcopy(data)
    k = draw(st.integers(min_value=1, max_value=120))
    for j in range(k):
        out["notes"].append(
            {
                "id": f"bad-{j}",
                "text": "x",
                "time_utc": "2026-01-01T00:00:00Z",
                "utc_offset_minutes": 7,
            }
        )
    return out, k
