# Performance Test Instructions (U3 Note Organizer)

## Targets
- U3-NFR P.5: each review action (accept, reject, edit and accept, undo, accept all) <= 300 ms on the busiest reference day.
- U3-NFR P.2 / P.3: one organizer batch (<= 10 notes) target <= 120 s; hard per-call limit 240 s.

## Run
```powershell
uv run pytest -m slow -s
```
In-process (`TestClient`, in-memory SQLite) on the busiest reference day (2026-06-13, 166 suggestions, 17 batches). Batch time needs the real model: see the integration scenarios S1 and S7 (times are in the app log line `organizer.batch ... duration_ms=`).

## Results (2026-11-27)
| Check | Measured | Target | Status |
|---|---|---|---|
| P.5 accept / reject / edit / undo / accept all | 144 / 88 / 89 / 86 / 146 ms | 300 ms | PASS |
| Batch, 8 notes (minimal sample day) | 140.9 s | 120 s target, 240 s limit | **over target**, under limit |
| Batch, 10 notes (probe day) | 111.7 s | 120 s target, 240 s limit | PASS |

The NFR probe measured 116 s for the same 10 notes. One run each on one laptop, so a guide, not a benchmark. The 8-note batch was the first organizer call of the session; if `qwen3:8b` was not yet loaded, its load time is inside that call (not checked), which may explain why it was slower than the 10-note batch.
