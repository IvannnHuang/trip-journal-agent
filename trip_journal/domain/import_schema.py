# ADDED [PROMPT #17]: trip file schema and validation IM-1..IM-14 (C17).
# AI-assisted, Claude Opus 5.5.
"""Parse and check an uploaded trip file. Nothing in the file is ever executed.

`parse_trip_file` returns a valid `TripFile` or raises `TripFileError` with every issue
found, ordered by position in the file, at most `MAX_ISSUES` of them.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, ValidationError
from pydantic_core import PydanticCustomError

from trip_journal.domain.days import format_utc

MAX_ISSUES = 50
UTF8_BOM = "﻿"
Loc = tuple[str | int, ...]


@dataclass(frozen=True)
class ImportIssue:
    location: str
    message: str


class TripFileError(Exception):
    """The file was refused; `issues` holds at most MAX_ISSUES, `more` the rest."""

    def __init__(self, issues: list[ImportIssue], more: int = 0) -> None:
        super().__init__(f"{len(issues) + more} import issues")
        self.issues = issues
        self.more = more


def _fail(kind: str, message: str) -> PydanticCustomError:
    return PydanticCustomError(kind, message)


def _utc_time(value: str) -> str:
    """IM-7: ISO-8601 in UTC only; stored as canonical text with whole seconds (FA-2)."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise _fail("utc_time", "must be a UTC time ending in Z") from None
    if parsed.tzinfo is None:
        raise _fail("utc_time", "must be a UTC time ending in Z")
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise _fail(
            "utc_time",
            "must be in UTC (Z or +00:00), the local offset goes in utc_offset_minutes",
        )
    return format_utc(parsed)


def _offset(value: int) -> int:
    """IM-8."""
    if not -720 <= value <= 840 or value % 15 != 0:
        raise _fail("utc_offset", "must be between -720 and 840 and a multiple of 15")
    return value


def _text(max_len: int) -> AfterValidator:
    """IM-9: 1..max_len characters after trim; the text is kept exactly as written."""

    def check(value: str) -> str:
        if not 1 <= len(value.strip()) <= max_len:
            raise _fail("text_length", f"must be 1 to {max_len} characters")
        return value

    return AfterValidator(check)


def _record_id(value: str) -> str:
    """IM-9: ids are 1-100 characters with no leading or trailing spaces."""
    if value != value.strip():
        raise _fail("record_id", "must not start or end with a space")
    if not 1 <= len(value) <= 100:
        raise _fail("record_id", "must be 1 to 100 characters")
    return value


def _stop_name(value: str | None) -> str | None:
    """IM-9: a blank name counts as missing."""
    if value is None or not value.strip():
        return None
    if len(value.strip()) > 200:
        raise _fail("text_length", "must be 1 to 200 characters")
    return value


def _optional_text(max_len: int) -> AfterValidator:
    def check(value: str | None) -> str | None:
        if value is not None and not 1 <= len(value.strip()) <= max_len:
            raise _fail("text_length", f"must be 1 to {max_len} characters")
        return value

    return AfterValidator(check)


def _route_summary(value: str | None) -> str | None:
    if value is not None and len(value.strip()) > 5000:
        raise _fail("text_length", "must be at most 5000 characters")
    return value


def _range(low: float, high: float) -> AfterValidator:
    """IM-10: coordinate range; non-finite values are refused by `allow_inf_nan=False`."""

    def check(value: float | None) -> float | None:
        if value is not None and not low <= value <= high:
            raise _fail("coordinate", f"must be between {low:g} and {high:g}")
        return value

    return AfterValidator(check)


RecordId = Annotated[str, AfterValidator(_record_id)]
UtcTime = Annotated[str, AfterValidator(_utc_time)]
Offset = Annotated[int, AfterValidator(_offset)]
Lat = Annotated[float, _range(-90, 90)]
Lon = Annotated[float, _range(-180, 180)]


class _Model(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False, frozen=True)


class TripMeta(_Model):
    trip_id: RecordId
    title: Annotated[str, _text(200)]
    home_timezone: Annotated[str | None, _optional_text(64)] = None


class StopIn(_Model):
    id: RecordId
    name: Annotated[str | None, AfterValidator(_stop_name)] = None
    start_utc: UtcTime
    end_utc: UtcTime
    utc_offset_minutes: Offset
    lat: Lat
    lon: Lon


class NoteIn(_Model):
    id: RecordId
    text: Annotated[str, _text(10_000)]
    time_utc: UtcTime
    utc_offset_minutes: Offset
    stop_id: str | None = None


class PhotoIn(_Model):
    id: RecordId
    time_utc: UtcTime
    utc_offset_minutes: Offset
    lat: Annotated[float | None, _range(-90, 90)] = None
    lon: Annotated[float | None, _range(-180, 180)] = None
    file_name: Annotated[str | None, _optional_text(255)] = None


class TripFile(_Model):
    trip: TripMeta
    stops: list[StopIn]
    notes: list[NoteIn]
    photos: list[PhotoIn] = []
    route_summary: Annotated[str | None, AfterValidator(_route_summary)] = None


class _RouteSummary(_Model):
    route_summary: Annotated[str | None, AfterValidator(_route_summary)] = None


_TOP_KEYS = tuple(TripFile.model_fields)
_REQUIRED_TOP = ("trip", "stops", "notes")
_LISTS: dict[str, type[_Model]] = {"stops": StopIn, "notes": NoteIn, "photos": PhotoIn}

_TYPE_MESSAGES = {
    "missing": "required field is missing",
    "string_type": "must be a string",
    "float_type": "must be a number",
    "int_type": "must be an integer",
    "list_type": "must be a list",
    "model_type": "must be an object",
    "dict_type": "must be an object",
    "model_attributes_type": "must be an object",
    "finite_number": "must be a finite number",
}


def format_location(loc: Loc) -> str:
    """('stops', 4, 'end_utc') -> 'stops[4].end_utc'."""
    out = ""
    for part in loc:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else part
    return out or "file"


def _position(data: Any, loc: Loc) -> tuple[int, ...]:
    """Sort key that follows the file: key order in objects, index order in lists."""
    key: list[int] = []
    node = data
    for part in loc:
        if isinstance(node, dict) and isinstance(part, str):
            keys = list(node)
            key.append(keys.index(part) if part in node else len(keys))
            node = node.get(part)
        elif isinstance(node, list) and isinstance(part, int):
            key.append(part)
            node = node[part] if 0 <= part < len(node) else None
        else:
            key.append(0)
            node = None
    return tuple(key)


def _message(error: Any) -> str:
    kind = error["type"]
    if kind == "extra_forbidden":
        return f"unknown field '{error['loc'][-1]}'"
    return str(_TYPE_MESSAGES.get(kind, error["msg"]))


class _Collector:
    def __init__(self) -> None:
        self.found: list[tuple[Loc, str]] = []

    def add(self, loc: Loc, message: str) -> None:
        self.found.append((loc, message))

    def validate(self, model: type[_Model], value: Any, prefix: Loc) -> Any:
        try:
            return model.model_validate(value)
        except ValidationError as exc:
            for error in exc.errors():
                self.add(prefix + tuple(error["loc"]), _message(error))
            return None


def _decode(raw: bytes, max_bytes: int) -> Any:
    """IM-1..IM-4; the first failing file rule stops the import."""

    def refuse(message: str) -> TripFileError:
        return TripFileError([ImportIssue("file", message)])

    if not raw:
        raise refuse("The file is empty.")
    if len(raw) > max_bytes:
        raise refuse(f"The file is larger than {max_bytes // (1024 * 1024)} MB.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise refuse(
            "The file is not UTF-8 text. Only the JSON trip format is supported."
        ) from None
    text = text.removeprefix(UTF8_BOM)
    if text.lstrip().startswith("<"):
        raise refuse("This looks like an XML/GPX file. Only the JSON trip format is supported.")
    try:
        # D-10 / FA-3: a repeated key keeps its last value, like json.loads itself.
        data = json.loads(text, parse_constant=lambda _name: math.nan)
    except json.JSONDecodeError as exc:
        raise refuse(
            f"The file is not valid JSON (line {exc.lineno}, column {exc.colno})."
        ) from None
    if not isinstance(data, dict):
        raise refuse("The file must contain one JSON object.")
    return data


def _check_records(data: dict[str, Any], issues: _Collector) -> dict[str, Any]:
    """IM-5..IM-11: schema per record; returns the records that passed, by list."""
    for key in data:
        if key not in _TOP_KEYS:
            issues.add((key,), f"unknown field '{key}'")
    for key in _REQUIRED_TOP:
        if key not in data:
            issues.add((key,), "required field is missing")
    valid: dict[str, Any] = {"trip": None, "stops": [], "notes": [], "photos": []}
    if "trip" in data:
        valid["trip"] = issues.validate(TripMeta, data["trip"], ("trip",))
    for key, model in _LISTS.items():
        if key not in data:
            continue
        items = data[key]
        if not isinstance(items, list):
            issues.add((key,), "must be a list")
            continue
        if key == "stops" and not items:
            issues.add((key,), "must have at least 1 item")
        for i, item in enumerate(items):
            record = issues.validate(model, item, (key, i))
            if record is not None:
                valid[key].append((i, record))
    if "route_summary" in data:
        issues.validate(_RouteSummary, {"route_summary": data["route_summary"]}, ())
    return valid


def _check_cross(data: dict[str, Any], valid: dict[str, Any], issues: _Collector) -> None:
    """IM-10 (photo lat/lon pair), IM-12 (unique ids), IM-13 (stop links, end >= start)."""
    for key in _LISTS:
        first: dict[str, int] = {}
        for i, record in valid[key]:
            if record.id in first:
                issues.add(
                    (key, i, "id"),
                    f"duplicate id '{record.id}' (first at {key}[{first[record.id]}])",
                )
            else:
                first[record.id] = i
    for i, stop in valid["stops"]:
        if stop.end_utc < stop.start_utc:
            issues.add(
                ("stops", i, "end_utc"),
                f"end_utc ({stop.end_utc}) is before start_utc ({stop.start_utc})",
            )
    raw_stops = data.get("stops")
    stop_ids = {
        s["id"]
        for s in (raw_stops if isinstance(raw_stops, list) else [])
        if isinstance(s, dict) and isinstance(s.get("id"), str)
    }
    for i, note in valid["notes"]:
        if note.stop_id is not None and note.stop_id not in stop_ids:
            issues.add(("notes", i, "stop_id"), f"no stop with id '{note.stop_id}'")
    for i, photo in valid["photos"]:
        if (photo.lat is None) != (photo.lon is None):
            issues.add(("photos", i), "lat and lon must both be present or both be missing")


def parse_trip_file(raw: bytes, max_bytes: int) -> TripFile:
    """IM-1..IM-14. Raises TripFileError; returns a fully valid TripFile."""
    data = _decode(raw, max_bytes)
    issues = _Collector()
    valid = _check_records(data, issues)
    _check_cross(data, valid, issues)
    if issues.found:
        ordered = sorted(issues.found, key=lambda item: _position(data, item[0]))
        shown = [ImportIssue(format_location(loc), msg) for loc, msg in ordered[:MAX_ISSUES]]
        raise TripFileError(shown, max(0, len(ordered) - MAX_ISSUES))
    return TripFile(
        trip=valid["trip"],
        stops=[r for _, r in valid["stops"]],
        notes=[r for _, r in valid["notes"]],
        photos=[r for _, r in valid["photos"]],
        route_summary=data.get("route_summary"),
    )
