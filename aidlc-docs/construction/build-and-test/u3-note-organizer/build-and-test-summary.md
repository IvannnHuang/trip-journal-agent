# Build and Test Summary (U3 Note Organizer)

Date: 2026-11-27. Laptop: Windows 11, uv 0.13.10, Python 3.13.14, Ollama 0.40.18 with `qwen3:8b`.

## Build
- **Status**: Success. No new dependency; ruff, ruff format and mypy --strict clean (94 files).
- **Artifacts**: none (runs from source).

## Tests
| Type | Result |
|---|---|
| Unit + API + page + property | **386 passed**, 4 deselected; coverage 97% (U3 modules 94-100%) |
| Property, `ci` profile | 38 passed (563 s) |
| Integration (real model + real browser) | **9 of 9 pass** |
| Performance P.5 (review actions) | **pass** (max 146 ms vs 300 ms) |
| Batch time (real model) | 111.7 s for 10 notes (pass); 140.9 s for 8 notes (**over the 120 s target**, under the 240 s limit) |
| Accuracy smoke check (manual, non-blocking) | category 89%, stop 89% on 18 notes |
| Contract / security / e2e | N/A: no external API consumers; Security extension opted out; e2e covered by the browser scenarios |

## Findings (none blocking; nothing fixed in this stage)
1. **Tip quality**: one invented tip and 6 of 18 tips that copy the whole note, against OR-F1. Prompt work for U4 / U6 (accuracy is measured formally in U6).
2. **"8/10" rating** still comes back as 8 and the note is dropped (OR-F3), as in the NFR probe; the prompt's conversion example (N-7) did not fix it for this note.
3. **Focus after a review action**: the `#day-stops` swap replaces the focused button, so focus falls back to `<body>` and a keyboard user loses their place. Not in the Functional Design; a11y nit.
4. **Results need a click**: after a run the timeline only shows suggestions after "Show results" reloads the page. This is the designed flow (frontend-components section 1); noted as a possible UX improvement.
5. One batch over the 120 s target (see Tests).

## Overall
- Build: success. Automated tests: pass. Review-action speed: pass.
- Integration: pass (9 of 9). Accuracy smoke check recorded; open items are prompt quality and the focus nit.
