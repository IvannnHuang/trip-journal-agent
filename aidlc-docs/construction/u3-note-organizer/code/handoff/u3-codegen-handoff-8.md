# U3 code generation hand-off 8 (plan steps 19-20 done, 2026-11-27)

- 完成：步骤 19（P-O1..P-O4 property 测试）和 20（P.5 perf 测试），已在 plan 里勾选，未提交。
- 检查：`uv run pytest -q` 386 passed / 4 deselected（基线 381 / 3，+5 个测试，2 min 6 s）；`pytest -m slow` 4 passed；ruff check、ruff format --check、mypy --strict 全部通过。
- 没发现 app 代码 bug，app 代码未改。
- 下一步：步骤 21（全量检查 + coverage）、22（code-summary 等）。

## New files
| File | Tests | Time (default profile) |
|---|---|---|
| `tests/property/test_organizer_props.py` | 4: P-O1, P-O2, P-O3 partition, P-O3 valid-reply round trip (PBT-02 row) | ~17 s |
| `tests/property/test_suggestions_stateful.py` | 1: P-O4 `SuggestionMachine`, 30 steps; edit read-back (PBT-02 row) | ~38 s |
| `tests/perf/test_review_speed.py` | 1 (slow): P.5 | ~1.2 s |

Changed: `tests/fixtures/organizer.py` (+`review_client`, `run_organizer`, `import_two_day_trip`).

## P.5 numbers (busiest reference day 2026-06-13, 166 suggestions, 17 batches; htmx page routes, `#day-stops` re-rendered)
| Action | ms | Target |
|---|---|---|
| Accept | 130 | 300 |
| Reject | 79 | 300 |
| Edit and accept | 84 | 300 |
| Undo | 79 | 300 |
| Accept all | 130 | 300 |

One laptop, one run (Windows 11), in-process TestClient.

## New decisions
- D-42: app-level properties (P-O1, P-O2, P-O4) build a fresh app per Hypothesis example / machine run with `review_client(llm)` (a context manager, no pytest fixtures, so no function-scoped-fixture health check). The HTTP mock answers 404; the organizer only talks to the `LabellingLLM`.
- D-43: no per-test `max_examples`; the U1 profiles stay in charge (NFR-T.3). P-O4 sets only `settings(stateful_step_count=30)` on the TestCase, which inherits the loaded profile.
- D-44: P-O2 and P-O4 re-runs change `LabellingLLM.category`, so "re-run replaces pending values" (OR-RUN1) is exercised; the P-O4 model checks that decided rows keep their values until Undo (OR-ST2) and one row per note (OR-ST1).
- D-45: the perf test copies the reference-trip loader instead of importing `test_import_speed` (D-38). It types the TestClient reply with a small `Protocol`, since TestClient responses are `httpx2.Response` here (see hand-off 7 note on openai / httpx2).

## For step 21
- Coverage: `uv run pytest --cov=trip_journal --cov-report=term-missing -q` (U3 modules ≥ 80%).
- CI profile (PowerShell): `$env:HYPOTHESIS_PROFILE = 'ci'; uv run pytest -q tests/property` — not run here. Estimate from default times ×5: P-O1 / P-O2 ~40 s each, P-O4 ~3 min; run in the background.
- `uv run pytest -m slow -q` once (passed here: 4 tests, ~7 s).
