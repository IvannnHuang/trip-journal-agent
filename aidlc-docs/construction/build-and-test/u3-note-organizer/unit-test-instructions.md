# Unit Test Execution (U3 Note Organizer)

## Run
```powershell
uv run pytest --cov
$env:HYPOTHESIS_PROFILE = "ci"; uv run pytest tests/property    # about 9-10 min; run in the background
```
Tests marked `slow` are deselected by default; see `performance-test-instructions.md`.

## Results (2026-11-27)
| Run | Result |
|---|---|
| `pytest -q` (unit + API + page + property, default profile; re-run in Build and Test) | **386 passed**, 4 deselected, 124.8 s |
| `pytest --cov` (Code Generation step 21) | 386 passed; total coverage 97% |
| U3 module coverage (target >= 80%) | `data/suggestions.py` 100%, `domain/organizer.py` 100%, `agent/organizer.py` 99%, `services/organizer.py` 98%, `api/notes.py` 95%, `pages/notes.py` 94% |
| `HYPOTHESIS_PROFILE=ci` property tests | **38 passed**, 563 s |

All tests use `FakeLLMClient` / a fake `LabellingLLM`; no test calls Ollama. Real-model behaviour is checked by hand in `integration-test-instructions.md`.
