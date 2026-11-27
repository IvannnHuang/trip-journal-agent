<!-- ADDED [PROMPT #17]: trip file import format (U2 step 17). AI-assisted, Claude Opus 5.5. -->
# Trip file import format

> Summary: one UTF-8 JSON object with `trip`, `stops`, `notes` and optional `photos` /
> `route_summary`. Files up to 20 MB. All times are UTC with a separate local offset.
> A file with any issue is refused as a whole and nothing is stored.
> Full example: [`sample_data/minimal_trip.json`](../sample_data/minimal_trip.json).

Import a file on the **Trips** page (`/trips`) or with `POST /api/trips` (multipart field `file`).
The file is only parsed as JSON and checked against the schema below; nothing in it is executed,
and the file name or extension is never used to decide the type.

## Top level

| Key | Type | Required | Notes |
|---|---|---|---|
| `trip` | object | yes | See [trip](#trip). |
| `stops` | list of objects | yes | At least 1 stop. |
| `notes` | list of objects | yes | May be empty. |
| `photos` | list of objects | no | Default empty. Photo metadata only, no image bytes. |
| `route_summary` | string or null | no | At most 5000 characters. |

Unknown keys are refused at every level (`unknown field 'x'`). Types are strict: a number
written as a string (`"60"`) is refused.

## trip

| Key | Type | Required | Rule |
|---|---|---|---|
| `trip_id` | string | yes | 1 to 100 characters, no leading/trailing spaces. Must not match an already imported trip. |
| `title` | string | yes | 1 to 200 characters after trimming. |
| `home_timezone` | string or null | no | 1 to 64 characters, e.g. `Europe/Lisbon`. Informational only. |

## stops

| Key | Type | Required | Rule |
|---|---|---|---|
| `id` | string | yes | 1 to 100 characters, no leading/trailing spaces, unique among stops. |
| `name` | string or null | no | At most 200 characters. Blank counts as missing; the day page then shows `Unnamed place (lat, lon)`. |
| `start_utc` | string | yes | UTC time, see [times](#times-and-offsets). |
| `end_utc` | string | yes | UTC time, not before `start_utc`. |
| `utc_offset_minutes` | integer | yes | Local offset, see [times](#times-and-offsets). |
| `lat` | number | yes | -90 to 90. |
| `lon` | number | yes | -180 to 180. |

A stop belongs to the local date of its start. A stop that ends on a later local date is shown
with a "+1 day" style label on its end time and is not repeated on the later day.

## notes

| Key | Type | Required | Rule |
|---|---|---|---|
| `id` | string | yes | As for stops, unique among notes. |
| `text` | string | yes | 1 to 10000 characters after trimming; stored exactly as written. |
| `time_utc` | string | yes | UTC time. |
| `utc_offset_minutes` | integer | yes | Local offset. |
| `stop_id` | string or null | no | Must be the `id` of a stop in the same file. A linked note is shown under its stop, on the stop's day. An unlinked note is shown under "Other notes" on its own local date. |

## photos

| Key | Type | Required | Rule |
|---|---|---|---|
| `id` | string | yes | As for stops, unique among photos. |
| `time_utc` | string | yes | UTC time. |
| `utc_offset_minutes` | integer | yes | Local offset. |
| `lat`, `lon` | number or null | no | Same ranges as stops; give both or neither. |
| `file_name` | string or null | no | 1 to 255 characters. Shown as text only. |

A photo is placed under the stop whose time range contains it; otherwise it is listed under
"Other photos" on its own local date.

## Times and offsets

- Times are ISO 8601 **in UTC**: `2026-05-02T08:15:00Z` (or `+00:00`). A time without a zone, or
  with any other offset, is refused. Fractions of a second are dropped on import.
- `utc_offset_minutes` is the local offset at that moment, from -720 to 840, a multiple of 15
  (Lisbon summer time = `60`). Local time = UTC time + offset.

## Limits

| Limit | Value |
|---|---|
| File size | 20 MB (`MAX_IMPORT_BYTES`) |
| Encoding | UTF-8; a leading BOM is allowed |
| Issues listed | First 50 in file order, then "and N more issues" |

## Error messages

File-level problems stop the check at once and report a single issue at location `file`:

| Problem | Message |
|---|---|
| Empty file | The file is empty. |
| Too large | The file is larger than 20 MB. |
| Not UTF-8 | The file is not UTF-8 text. Only the JSON trip format is supported. |
| Starts with `<` | This looks like an XML/GPX file. Only the JSON trip format is supported. |
| Bad JSON | The file is not valid JSON (line L, column C). |
| Not an object | The file must contain one JSON object. |

Otherwise every issue is collected and shown as `location: message`, where the location is a
path like `stops[4].end_utc`:

| Rule | Message |
|---|---|
| Missing key | required field is missing |
| Extra key | unknown field 'x' |
| Wrong type | must be a string / must be a number / must be an integer / must be a list / must be an object |
| NaN or Infinity | must be a finite number |
| Empty `stops` | must have at least 1 item |
| Text length | must be 1 to N characters |
| Id spaces | must not start or end with a space |
| Not UTC | must be a UTC time ending in Z / must be in UTC (Z or +00:00), the local offset goes in utc_offset_minutes |
| Offset | must be between -720 and 840 and a multiple of 15 |
| Coordinates | must be between -90 and 90 / must be between -180 and 180 |
| Duplicate id | duplicate id 's1' (first at stops[0]) |
| End before start | end_utc (...) is before start_utc (...) |
| Unknown stop link | no stop with id 's9' |
| Photo position | lat and lon must both be present or both be missing |

A trip whose `trip_id` is already imported is refused with HTTP 409:
"A trip with the id '...' is already imported. Delete it first, then import again."
Validation issues return HTTP 422 with `{code, message, action, issues: [{location, message}], more}`.

## Example

A shortened version of the sample; the full file has 4 stops, 8 notes and 10 photos on one day.

```json
{
  "trip": {"trip_id": "minimal-lisbon-2026-05", "title": "A day in Lisbon", "home_timezone": "Europe/Lisbon"},
  "stops": [
    {"id": "s1", "name": "Café A Brasileira", "start_utc": "2026-05-02T08:15:00Z",
     "end_utc": "2026-05-02T09:00:00Z", "utc_offset_minutes": 60, "lat": 38.7107, "lon": -9.1424}
  ],
  "notes": [
    {"id": "n1", "stop_id": "s1", "time_utc": "2026-05-02T08:30:00Z", "utc_offset_minutes": 60,
     "text": "Pastel de nata and a bica at the counter. Very crowded."}
  ],
  "photos": [
    {"id": "p1", "time_utc": "2026-05-02T08:20:00Z", "utc_offset_minutes": 60,
     "lat": 38.7107, "lon": -9.1424, "file_name": "IMG_0001.jpg"}
  ],
  "route_summary": "Chiado, Alfama viewpoint, the tile museum, then dinner in Bairro Alto."
}
```
