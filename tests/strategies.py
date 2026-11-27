# ADDED [PROMPT #13]: shared Hypothesis strategies (NP-8). AI-assisted, Claude Opus 5.5.
"""Generators for sentences, citations, URLs, model names and tool payloads."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from hypothesis import strategies as st

from trip_journal.data.repositories import NoteRow, StopRow  # ADDED [PROMPT #25]
from trip_journal.domain.grounding import Citation
from trip_journal.domain.organizer import (  # ADDED [PROMPT #25]
    CATEGORIES,
    DISH_MAX,
    TIP_MAX,
    BatchInput,
)

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


# ADDED [PROMPT #25]: U3 organizer strategies (plan step 16, PBT-07). AI-assisted, Claude Opus 5.5.
ORGANIZER_DAY = "2026-06-01"

# Note texts: short words, unicode (CJK, accents, emoji), and long ones past the 1,000 cut.
_unicode_chars = st.characters(categories=("L", "N", "P", "S", "Zs"), max_codepoint=0x1F6FF)
note_texts = st.one_of(
    texts,
    st.text(_unicode_chars, min_size=1, max_size=200).filter(lambda t: t.strip() != ""),
    st.integers(min_value=900, max_value=2500).map(lambda n: ("café 8/10 " * 300)[:n]),
)


@st.composite
def batches(draw: st.DrawFn, max_stops: int = 4, max_notes: int = 10) -> BatchInput:
    """One batch on ORGANIZER_DAY: 0..max_stops stops, 1..max_notes notes (ids unique)."""
    n_stops = draw(st.integers(min_value=0, max_value=max_stops))
    n_notes = draw(st.integers(min_value=1, max_value=max_notes))
    stops = []
    for i in range(n_stops):
        hour = draw(st.integers(min_value=0, max_value=22))
        start = f"{ORGANIZER_DAY}T{hour:02d}:00:00Z"
        name = draw(st.one_of(st.none(), texts))
        stops.append(StopRow(100 + i, 1, f"s{i}", name, start, start, 0, ORGANIZER_DAY, 38.7, -9.1))
    notes = []
    for i in range(n_notes):
        minute = draw(st.integers(min_value=0, max_value=23 * 60 + 59))
        time_utc = f"{ORGANIZER_DAY}T{minute // 60:02d}:{minute % 60:02d}:00Z"
        stop_id = draw(
            st.one_of(st.none(), st.sampled_from([s.id for s in stops])) if stops else st.none()
        )
        notes.append(
            NoteRow(i + 1, 1, stop_id, f"n{i}", draw(note_texts), time_utc, 0, ORGANIZER_DAY)
        )
    return BatchInput(day=ORGANIZER_DAY, stops=tuple(stops), notes=tuple(notes))


def batch_labels(batch: BatchInput) -> tuple[list[str], list[str]]:
    """The note labels `n1..nK` and stop labels `s1..sM` the model sees for this batch."""
    return (
        [f"n{i}" for i in range(1, len(batch.notes) + 1)],
        [f"s{i}" for i in range(1, len(batch.stops) + 1)],
    )


_good_text = st.one_of(st.none(), texts.filter(lambda t: len(t) <= 60))


@st.composite
def valid_reply_items(draw: st.DrawFn, note_label: str, stop_labels: list[str]) -> dict[str, Any]:
    """An item that passes OR-V1..V4 for this batch."""
    return {
        "note": note_label,
        "category": draw(st.sampled_from(CATEGORIES)),
        "stop": draw(
            st.one_of(st.none(), st.sampled_from(stop_labels)) if stop_labels else st.none()
        ),
        "dish": draw(_good_text),
        "rating": draw(st.one_of(st.none(), st.integers(min_value=1, max_value=5))),
        "tip": draw(_good_text),
    }


@st.composite
def bad_reply_items(draw: st.DrawFn, note_labels: list[str], stop_labels: list[str]) -> Any:
    """An item the parser must drop: unknown labels, bad category, bad fields, or not an object."""
    base = draw(valid_reply_items(draw(st.sampled_from(note_labels)), stop_labels))
    kind = draw(
        st.sampled_from(
            ["note", "stop", "category", "rating", "dish", "tip", "not_object", "note_type"]
        )
    )
    if kind == "note":
        base["note"] = f"n{len(note_labels) + draw(st.integers(min_value=1, max_value=50))}"
    elif kind == "stop":
        base["stop"] = draw(st.sampled_from(["s0", f"s{len(stop_labels) + 1}", "", "S1"]))
    elif kind == "category":
        base["category"] = draw(st.sampled_from(["drink", "Food", "", None, 3]))
    elif kind == "rating":
        base["rating"] = draw(st.sampled_from([0, 6, -1, 4.5, "4", True]))
    elif kind == "dish":
        base["dish"] = "d" * (DISH_MAX + draw(st.integers(min_value=1, max_value=20)))
    elif kind == "tip":
        base["tip"] = draw(st.sampled_from(["t" * (TIP_MAX + 1), 7, ["x"]]))
    elif kind == "not_object":
        return draw(json_scalars)
    else:
        base["note"] = draw(st.sampled_from([1, None, ["n1"]]))
    return base


@st.composite
def reply_texts(draw: st.DrawFn, batch: BatchInput) -> str:
    """Model reply text for `batch`: mixed valid, bad and duplicate items, extra keys,
    `<think>` blocks, wrong top levels and junk."""
    note_labels, stop_labels = batch_labels(batch)
    kind = draw(st.sampled_from(["items", "items", "items", "top_level", "junk"]))
    if kind == "junk":
        return draw(st.one_of(st.text(max_size=80), st.just(""), st.just('{"suggestions": [')))
    if kind == "top_level":
        return json.dumps(draw(json_values))
    items: list[Any] = []
    for _ in range(draw(st.integers(min_value=0, max_value=len(note_labels) + 3))):
        if draw(st.booleans()):
            item = draw(valid_reply_items(draw(st.sampled_from(note_labels)), stop_labels))
            if draw(st.booleans()):
                item["x_extra"] = 1  # OR-V8
            items.append(item)
        else:
            items.append(draw(bad_reply_items(note_labels, stop_labels)))
    body: dict[str, Any] = {"suggestions": items}
    if draw(st.booleans()):
        body["comment"] = "extra top-level key"  # OR-V8
    text = json.dumps(body, ensure_ascii=False)
    if draw(st.booleans()):
        text = f"<think>{draw(st.text(max_size=20))}</think>{text}"
    return text
