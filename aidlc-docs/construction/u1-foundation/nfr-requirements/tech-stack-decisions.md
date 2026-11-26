# U1 Foundation - Tech Stack Decisions

**Stage**: Construction - NFR Requirements (plan step 5)
**Source**: `docs/technical-environment.md`, `requirements.md` NFR-6, plan answers Q1, Q5-Q9 (all A, owner, 2026-11-26), `model-spike-results.md`
**Scope**: the stack U1 builds on. The stack itself was fixed at Requirements (NFR-6.1, NFR-6.2); this file records the U1-level choices made here.

---

## 1. Runtime and libraries (fixed by NFR-6.1)

| Area | Choice | U1 use |
|---|---|---|
| Language | Python 3.12+ | all code |
| Packaging | uv + `pyproject.toml` | see §4 |
| Web | FastAPI, uvicorn, Jinja2, htmx (no JS build step) | settings page, status banner, job polling |
| Validation | Pydantic v2 | tool argument models (`extra="forbid"`), settings, job status |
| Database | SQLite via `sqlite3`, FTS5 `trigram` tokenizer | `notes_fts`, settings, place cache (FTS5 trigram verified on SQLite 3.50.4 in Functional Design) |
| LLM client | `openai` SDK at Ollama `http://localhost:11434/v1` | agent loop chat calls with `tools` |
| HTTP | httpx | Ollama `/api/tags` check, Nominatim lookup |
| Not used | items under "Do NOT Use" in `technical-environment.md` (LangChain, vector DBs, `requests`, SQLAlchemy, React, Streamlit, hosted LLM APIs by default) | NFR-6.2 |

## 2. Model

| Decision | Value | Rationale |
|---|---|---|
| Default model | `qwen3:8b` | 18/18 spike success; only model with 0 wrong tools and 0 wrong citations (Q1 A) |
| Thinking mode | On (Ollama default; no option sent to disable it) | Q1 A; `<think>` blocks removed by AL-9 |
| Alternative | `llama3.1:8b` may be set in Settings; not recommended as default (12/18, wrong tool on q4, wrong citation on q3) | FD Q1 A, spike |
| Per-call timeout | 120 s, passed to the `openai` client per request | Q5 A |
| Job timeout | 300 s, fixed in `JobRunner(timeout_s=300)` | Q4 A (IC-3) |
| Known limitation | Fails the ≤ 11 s per-step part of the acceptance rule on the measured laptop; about 83% of spike runs fit the timeouts | Q2 A; `nfr-requirements.md` §1.1 |

Trade-off accepted by the owner: correctness of tool choice and citations over speed. Rejected: thinking off (only about 25% faster, still far over the speed targets); `llama3.1:8b` default (fast but 2 of 6 question types fail every time); a Settings hint for slow laptops (option D, not chosen).

## 3. Testing

| Decision | Value | Rationale |
|---|---|---|
| Test runner | pytest, pytest-cov (≥ 80% line coverage) | NFR-7.1 |
| PBT framework | **Hypothesis** (pytest plugin built in) | Q7 A, PBT-09: custom strategies, automatic shrinking, seed replay, pytest integration |
| Profiles | `default`: `max_examples=100`; `ci`: `max_examples=500`; both `print_blob=True`; chosen by `HYPOTHESIS_PROFILE`, registered in `tests/conftest.py` | Q7 A, PBT-08 |
| Example database | `.hypothesis/` directory, git-ignored | Q7 A |
| Fakes | fake LLM client with scripted replies; httpx mock transport for Ollama and Nominatim | NFR-7.2, U1-NFR-T.5 |
| Lint / types | ruff (lint + format), mypy | NFR-6.5 |

Hypothesis, pytest, pytest-cov, ruff and mypy are dev dependencies in `pyproject.toml` (PBT-09 requires the framework in project dependencies).

## 4. Dependency versions

| Decision | Value | Rationale |
|---|---|---|
| `pyproject.toml` | lower bounds only (for example `fastapi>=X.Y`) | Q9 A |
| Lock file | `uv.lock` committed; exact versions come from it (`uv sync --locked`) | Q9 A; same versions on every team laptop |
| Bound values | set at Code Generation from the versions `uv` resolves then, not recalled here | verify versions, do not guess |

## 5. Logging

| Decision | Value | Rationale |
|---|---|---|
| Library | Python standard `logging` | Q8 A |
| Output | console (stderr) only, no log file | Q8 A |
| Level | INFO default; `TRIP_JOURNAL_LOG_LEVEL` env var; invalid → warning + INFO | Q8 A, U1-NFR-L.1 |
| Content rules | no note / journal text, no prompts or replies, coordinates only as the rounded key | U1-NFR-L.2, NFR-2 |

## 6. Network timeouts summary

| Call | Timeout | Source |
|---|---|---|
| Ollama chat (one step) | 120 s | Q5 A |
| Whole job | 300 s | Q4 A |
| Ollama `/api/tags` status | 2 s | FD Q17 A (ST-2) |
| Nominatim reverse lookup | 5 s, max 1 request/s | Q6 A (A-3 confirmed) |
