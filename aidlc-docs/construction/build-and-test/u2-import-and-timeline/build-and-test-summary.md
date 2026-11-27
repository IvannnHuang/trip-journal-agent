# Build and Test Summary (U2 Import and Timeline)

Date: 2026-11-27. Laptop: Windows 11, uv 0.13.10, Python 3.13.14.

## Build
- **Status**: Success. `uv sync --frozen` OK (no new dependency); ruff, ruff format and mypy --strict clean (77 files).
- **Artifacts**: none (runs from source). Generated test data is in the git-ignored `sample_data/generated/`.

## Tests
| Type | Result |
|---|---|
| Unit + API + page + property | **276 passed** after the F-1 fix, coverage 97% (U2 modules 98-100%) |
| Property, `ci` profile | 33 passed (347.9 s) |
| Integration (real browser) | **8 of 8 pass** (S2 and S4 failed on F-1, passed after the fix) |
| Performance P.1-P.4 | **all pass** (slowest: 19.71 MB in 2.55 s over HTTP vs a 15 s target) |
| Contract / security / e2e | N/A: no external API consumers; Security extension opted out; e2e is covered by the browser scenarios |

## Findings
1. **F-1 (bug, fixed 2026-11-27): 422 and 409 import messages never appeared.** `_partials/import_form.html` puts `hx-on::before-swap` on the `<form>`. htmx 2.0.4 fires `htmx:beforeSwap` on the request's **target** (`#import-panel`, the form's parent), so the handler never runs and htmx drops the 4xx response. After a bad file or a duplicate the user sees nothing happen. Fix: the attribute moved to `<section id="import-panel">` (the swapped-in panel carries it again). Regression test `test_import_swap_handler_sits_on_target` checks that the handler sits on the hx-target in the full page and in the 422 / 409 fragments (a `TestClient` test cannot run htmx). S2 and S4 re-run in the browser: pass.
2. **TL-5 (spec question, open)**: day-page photos show time and file name only, not coordinates or "no location". Owner decision pending.
3. **Nit**: the trip list says "1 days" (`trips/list.html` line 16).
4. `scripts/model_spike.py` has 4 × E501 (U1, unchanged).

## Overall
- Build: success. Automated tests: pass. Performance: pass.
- Integration: pass (8 of 8) after the F-1 fix. Open: TL-5 (owner decision) and the "1 days" nit.
