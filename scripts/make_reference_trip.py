# ADDED [PROMPT #17]: reference trip generator for the U2 speed checks (U2-NFR-P.2, P.3).
# AI-assisted, Claude Opus 5.5.
"""Write generated trip files under sample_data/generated/ (not committed).

    uv run python scripts/make_reference_trip.py

- reference_trip.json: 14 days, 300 stops, 2,000 notes, 3,000 photos (fixed seed).
- large_trip.json: the same records with long notes, close to (but under) 20 MB.
"""

from __future__ import annotations

import json
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SEED = 5940
DAYS = 14
STOPS = 300
NOTES = 2_000
PHOTOS = 3_000
LARGE_TARGET_BYTES = 19 * 1024 * 1024  # the import limit is 20 MB
OUT_DIR = Path(__file__).resolve().parents[1] / "sample_data" / "generated"
_START = datetime(2026, 6, 1, 6, 0, tzinfo=UTC)
_WORDS = [
    "coffee",
    "tram",
    "harbour",
    "museum",
    "tiles",
    "bridge",
    "market",
    "lunch",
    "rain",
    "sunset",
    "castle",
    "river",
    "train",
    "square",
    "garden",
    "bakery",
    "海边",
    "寺",
    "café",
    "pastel",
    "azulejo",
]


def _utc(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sentence(rng: random.Random, words: int) -> str:
    return " ".join(rng.choice(_WORDS) for _ in range(words)).strip()


def build_trip(seed: int = SEED, note_words: int = 12) -> dict[str, Any]:
    """A valid trip file; the second half of the trip is one hour further east."""
    rng = random.Random(seed)
    per_day = STOPS // DAYS + 1
    stops: list[dict[str, Any]] = []
    for i in range(STOPS):
        day, slot = divmod(i, per_day)
        start = _START + timedelta(days=day, minutes=slot * 40 + rng.randint(0, 5))
        end = start + timedelta(minutes=rng.randint(10, 35))
        stops.append(
            {
                "id": f"s{i:04d}",
                "name": _sentence(rng, 3) if rng.random() < 0.9 else None,
                "start_utc": _utc(start),
                "end_utc": _utc(end),
                "utc_offset_minutes": 60 if day < DAYS // 2 else 120,
                "lat": round(rng.uniform(36.0, 44.0), 5),
                "lon": round(rng.uniform(-9.5, 3.0), 5),
            }
        )
    notes = []
    for i in range(NOTES):
        stop = rng.choice(stops)
        start = datetime.fromisoformat(stop["start_utc"].replace("Z", "+00:00"))
        note: dict[str, Any] = {
            "id": f"n{i:05d}",
            "text": _sentence(rng, note_words)[:10_000],
            "time_utc": _utc(start + timedelta(minutes=rng.randint(0, 30))),
            "utc_offset_minutes": stop["utc_offset_minutes"],
        }
        if rng.random() < 0.7:
            note["stop_id"] = stop["id"]
        notes.append(note)
    photos = []
    for i in range(PHOTOS):
        stop = rng.choice(stops)
        start = datetime.fromisoformat(stop["start_utc"].replace("Z", "+00:00"))
        photo: dict[str, Any] = {
            "id": f"p{i:05d}",
            "time_utc": _utc(start + timedelta(minutes=rng.randint(0, 45))),
            "utc_offset_minutes": stop["utc_offset_minutes"],
            "file_name": f"IMG_{i:05d}.jpg",
        }
        if rng.random() < 0.8:
            photo["lat"], photo["lon"] = stop["lat"], stop["lon"]
        photos.append(photo)
    for stop in stops:
        if stop["name"] is None:
            del stop["name"]
    return {
        "trip": {"trip_id": f"reference-{seed}", "title": "Reference trip"},
        "route_summary": _sentence(rng, 40),
        "stops": stops,
        "notes": notes,
        "photos": photos,
    }


def encode(data: dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def build_large(seed: int = SEED) -> bytes:
    """Same counts, long notes, sized just under LARGE_TARGET_BYTES."""
    probe = len(encode(build_trip(seed, note_words=100)))
    base = len(encode(build_trip(seed, note_words=0)))
    per_100 = (probe - base) / NOTES
    words = int(100 * (LARGE_TARGET_BYTES - base) / NOTES / per_100)
    data = build_trip(seed, note_words=words)
    data["trip"]["trip_id"] = f"large-{seed}"
    raw = encode(data)
    while len(raw) > LARGE_TARGET_BYTES:
        words -= 20
        data = build_trip(seed, note_words=words)
        data["trip"]["trip_id"] = f"large-{seed}"
        raw = encode(data)
    return raw


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reference = encode(build_trip())
    (OUT_DIR / "reference_trip.json").write_bytes(reference)
    large = build_large()
    (OUT_DIR / "large_trip.json").write_bytes(large)
    print(f"reference_trip.json {len(reference) / 1e6:.2f} MB")
    print(f"large_trip.json {len(large) / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
