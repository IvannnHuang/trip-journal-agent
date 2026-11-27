# Unit Test Execution (U2 Import and Timeline)

## Run
```powershell
uv run pytest --cov
$env:HYPOTHESIS_PROFILE = "ci"; uv run pytest tests/property    # about 6 min; run in the background
```
Tests marked `slow` are deselected by default (`pyproject.toml`); see `performance-test-instructions.md`.

## Results (2026-11-27)
| Run | Result |
|---|---|
| `pytest --cov` (unit + API + page + property, default profile) | **276 passed** after the F-1 fix (275 before; +1 regression test), 3 deselected, 1 warning, 76.4 s; coverage 97% |
| Coverage | total 97%; U2 modules 98-100% (target ≥ 80%, U2-NFR T.1) |
| `HYPOTHESIS_PROFILE=ci` property tests | **33 passed**, 347.9 s (Code Generation run; no code changed since) |

## Gap found in this stage
The API and page tests use `TestClient`, which does not run JavaScript. They check status codes and HTML but cannot see htmx swap behaviour. Finding F-1 (see the summary) passed every automated test for this reason; its regression test can only check where the handler attribute sits.
