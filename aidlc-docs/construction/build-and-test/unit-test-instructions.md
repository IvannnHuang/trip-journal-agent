# Unit Test Execution (U1 Foundation)

Unit, API and property-based tests need no network and no Ollama: they use `httpx.MockTransport`, a scripted `FakeLLMClient` and in-memory SQLite.

## Test layout
| Folder | Files | What it covers |
|---|---|---|
| `tests/unit/` | 8 | errors, grounding, jobs, logs, places (rate limit, cache, timeout), repositories, search, settings |
| `tests/agent/` | 3 | agent loop (tool order, step limit, timeouts, unknown tool), prompts, tools |
| `tests/api/` | 3 | jobs API, settings API, Settings page and banners |
| `tests/property/` | 6 | Hypothesis: grounding, search, settings, tool results, cache keys, stateful job machine (P-J1) |

## Run unit tests

### 1. All tests with coverage (default Hypothesis profile, 100 examples)
```powershell
Set-Location D:\documents\web\classes\INFO5940\trip-journal-agent
uv run pytest --cov=trip_journal -q
```

### 2. Property tests with the `ci` profile (500 examples, fixed seed) before a merge
```powershell
$env:HYPOTHESIS_PROFILE = 'ci'; uv run pytest tests/property --hypothesis-seed=12345 -q; Remove-Item Env:HYPOTHESIS_PROFILE
```
A failing example is printed with a `@reproduce_failure` blob (`print_blob=True`); rerun with the same seed to reproduce.

### 3. Review results (measured 2026-11-26, Build and Test)
| Run | Expected | Measured |
|---|---|---|
| `pytest --cov=trip_journal` | 154 pass, 0 fail, coverage ≥ 90% | **154 passed**, 1 warning, 56.9 s (wall 62.7 s); coverage **95%** (1299 statements, 44 missed) |
| `HYPOTHESIS_PROFILE=ci`, seed 12345 | 22 pass | **22 passed** in 248.59 s (wall 4 m 12.8 s) |
| ruff check / format, mypy --strict | clean | ruff "All checks passed!", "55 files already formatted"; mypy "Success: no issues found in 54 source files" |

- **Known warning**: `tests/api/test_pages.py::test_post_saves` raises a `ResourceWarning: unclosed database` (an SQLite connection from a test app that is not closed through the lifespan). Harmless for results; worth a cleanup later.
- **Report location**: console only (coverage `show_missing`, `skip_covered`); no HTML report is written.

### 4. Fix failing tests
1. Read the failing test name and assertion in the pytest output.
2. For a property test, copy the printed falsifying example / `@reproduce_failure` line into a regression test first.
3. Fix the code, then rerun steps 1 and 2 until everything passes.
