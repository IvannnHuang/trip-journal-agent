# Performance Test Instructions (U2 Import and Timeline)

## Targets (U2-NFR P.1-P.4)
Sample import ≤ 1 s; reference trip (14 days, 300 stops, 2,000 notes, 3,000 photos) ≤ 5 s; near-20 MB file ≤ 15 s; `/trips` and the busiest day page ≤ 300 ms.

## Run
```powershell
uv run pytest -m slow -s
```
This runs in-process (`TestClient`, in-memory SQLite). To include HTTP and a file database, start the app and post the generated files:
```powershell
curl.exe -s -o NUL -w "%{http_code} %{time_total}s" -F "file=@sample_data/generated/reference_trip.json;type=application/json" http://127.0.0.1:8741/api/trips
```

## Results (2026-11-27)
| Check | In-process | HTTP + file DB | Target | Status |
|---|---|---|---|---|
| P.1 sample import | 0.135 s | - | 1 s | PASS |
| P.2 reference import | 0.386 s | 0.344 s | 5 s | PASS |
| P.3 19.71 MB import | 1.786 s | 2.547 s | 15 s | PASS |
| P.4 `GET /trips` | 0.073 s | - | 0.3 s | PASS |
| P.4 busiest day page | 0.082 s | - | 0.3 s | PASS |

No load or concurrency test: the app serves one local user by design.
