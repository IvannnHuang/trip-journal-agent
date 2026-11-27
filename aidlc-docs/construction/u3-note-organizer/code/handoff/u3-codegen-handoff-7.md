# U3 code generation hand-off 7 (plan steps 16-18 done, 2026-11-27)

- 完成：步骤 16（strategies、`fake_llm` / `organizer_client` fixture、`make_app_client`）、17（单元测试补缺）、18（API / 页面测试，CI-1 / CI-2，D-9 / D-10 页面位置），已勾选，未提交。
- 检查：pytest 381 passed / 3 deselected（基线 338，+43）；ruff check、ruff format --check、mypy --strict 全部通过。未做浏览器检查。
- 下一步：步骤 19（property）和 20（perf, slow）。

## Test counts (tests collected per file)
| File | Tests |
|---|---|
| `tests/unit/test_organizer_parse.py` | 31 (incl. Hypothesis + parametrize) |
| `tests/unit/test_organizer_batches.py` | 5 |
| `tests/unit/test_organizer_prompt.py` | 5 |
| `tests/unit/test_organizer_call.py` | 4 |
| `tests/unit/test_jobs.py` | 10 (+2 per-job timeout) |
| `tests/unit/test_errors.py` | 19 (+U3 codes, state / timeout text) |
| `tests/api/test_notes_api.py` | 7 |
| `tests/api/test_organizer_pages.py` | 11 |
| `tests/api/test_trip_pages.py` | 20 (+CI-1 photo line, CI-2 day words) |

## Bugs found
- None in app code. One test-side fix: openai 3.60 builds its errors on `httpx2`, so `APITimeoutError` needs an `httpx2.Request` (mypy caught it). `httpx2` is a transitive dependency of openai, not a direct one.

## New decisions
- D-38: shared U3 test helpers live in `tests/fixtures/organizer.py` (`SAMPLE_DAY`, `NEXT_DAY`, `SAMPLE_DAY_LABELS`, `organizer_item`, `organizer_reply`, `LabellingLLM`, `make_app_client`, `import_sample_trip`, `wait_job`, `two_day_trip_bytes`). Test modules import from there, never from each other.
- D-39: `two_day_trip_bytes()` is the reference multi-day trip (sample trip, stop s4 with n7, n8, p9, p10 moved to 2026-05-03; day 1 = s1-s3, n1-n6).
- D-40: model labels follow time order: in the sample day, source note n6 (11:45, no stop) is label `n4`. Tests that target a note by label must say so.
- D-41: D-10 placement is checked by parsing the day page (`placement()` in `test_organizer_pages.py`: note id -> enclosing `stop-<db id>` or `day-other-notes`), plus `notes.stop_id` unchanged before / after.

## Facts for steps 19-20
- Fixtures: `fake_llm` (FakeLLMClient with one `organizer_reply` for the sample day) and `organizer_client` (TestClient over `:memory:`); `http` fixture for custom LLMs via `for client in make_app_client(http, llm):`.
- Strategies in `tests/strategies.py`: `ORGANIZER_DAY`, `note_texts`, `batches`, `batch_labels`, `valid_reply_items`, `bad_reply_items`, `reply_texts`.
- Repos: `app.state.trip.repos` (`notes.list_for_trip`, suggestions repo); JSON: GET `/api/trips/{id}/days/{day}/suggestions` (rows with `suggestion_id`, `note_id`, `note_source_id`, `status`), POST `/api/trips/{id}/days/{day}/suggestions/accept-all` -> `{"accepted": n}`.
- Pending rows are re-sent on a new run; only accepted / edited / rejected count as decided (`?nothing=1` only after every note has a decision).
- Accept-all on the sample day after one run accepts 8; a whole-trip run on the two-day trip = 2 batches, total 8.
- Busy page reply: 429, `organizer-error` fragment, "Another request is still running."
- Perf (step 20): mark `@pytest.mark.slow` (deselected by default; 3 already deselected).
