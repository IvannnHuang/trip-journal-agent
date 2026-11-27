# Build and Test Summary (U1 Foundation)

Date: 2026-11-26. Laptop: Windows 11, GTX 1650 Ti 4 GB, 15.7 GiB RAM. Ollama 0.40.18 with `qwen3:8b`.

## Build status
- **Build tool**: uv 0.13.10 with Python 3.13.14. `uv sync --frozen`: "Checked 44 packages".
- **Static gate**: ruff check passes and 55 files are already formatted. `mypy --strict` passes on 54 files.
- **Status**: **Success**. There is no build artifact for U1; the app runs from source with `uv run trip-journal`.
- **Finding**: `uv run trip-journal` could not bind port 8000 on this laptop, because Docker Desktop / WSL holds it (`[WinError 10048]`). The port is hardcoded in `config.py`. A workaround with port 8740 was used; see `build-instructions.md`.

## Test results
| Type | Result | Details |
|---|---|---|
| Unit + API + property (default) | **154 passed**, 0 failed | 56.9 s; coverage 95% |
| Property, `ci` profile (500 examples, seed 12345) | **22 passed** | 248.59 s |
| Integration (real Ollama) | **6 of 6 scenarios pass** | S3 is simulated with a wrong port; S5 passed on the second try |
| Performance | hard limits met; speed targets **not met** | Q&A 241.2 s vs. a 30 s target; 64 to 107 s per step vs. the 11 s rule |
| Contract / security / e2e | N/A | single app with no external API consumers; the Security extension is opted out; no UI flow exists yet |

## NFR Design check: cancel stops generation (PASS)
Both a task cancel and the job deadline stopped generation in Ollama. The log shows `srv stop: cancel task` and `all slots are idle`, and the GPU went from 33% to 0% within 3 s. The model stays loaded until its keep-alive runs out, which is expected.

## Findings for later units (not fixed in U1)
1. Port 8000 is hardcoded. Add a port override such as `TRIP_JOURNAL_PORT`.
2. The nav link `/trips` returns 404 until U2.
3. The "model not installed" message shows three times on the Settings page (UX nit).
4. `ResourceWarning: unclosed database` in `tests/api/test_pages.py::test_post_saves`.
5. The model did not cite its first sentence, so grounding flagged it. The U3/U4 prompts should ask for a citation in every sentence.
6. Ollama's runner crashed when free RAM was low (1.3 GiB): "CUDA error: shared object initialization failed", returned as HTTP 500. The app reported `model_error` correctly. A help text could suggest closing other apps.
7. A manual cancel is reported as `job_timeout`. Consider a separate `job_cancelled` code when U2 adds the cancel button.
8. `scripts/model_spike.py` fails ruff E501 (4 lines). It is outside the app; fix it or exclude it.

## Not verified
- A real Ollama stop (a wrong port was used instead, because stopping Ollama needed the owner's OK).
- The "Check again" button click, the place-lookup toggle, and a live Nominatim call.
- Journal timing (P.1, 90 s target) and a question asked through the UI: U1 has no such pages.

## Overall
- Build: success. All tests pass.
- Integration: pass, including the cancel check.
- Performance: the hard limits hold, and the speed targets are a known limitation.
- **Ready for the Operations stage** (a placeholder) **and for U2**, after the team approves.
