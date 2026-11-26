# U1 Foundation - NFR Requirements

**Stage**: Construction - NFR Requirements (plan steps 4)
**Source**: `aidlc-docs/construction/plans/u1-foundation-nfr-requirements-plan.md` (9 answers, all A, chosen by the owner 2026-11-26), `requirements.md` NFR-1 to NFR-7, Functional Design `business-rules.md`, `model-spike-results.md`
**Scope**: the non-functional requirements U1 code must meet. Ids `U1-NFR-<area>.<n>`. Each cites its source. Changes to Functional Design rules are listed in section 9.

---

## 1. Performance

| Id | Requirement | Source |
|---|---|---|
| U1-NFR-P.1 | Speed targets stay as in NFR-1.1: a day-journal draft in ≤ 90 s and a Q&A answer in ≤ 30 s. They are **targets**, measured on the team's slowest demo laptop (NFR-1.2). Missing them is reported in Build and Test with the laptop model, memory and GPU share; it does not block the unit. | Q3 A |
| U1-NFR-P.2 | One model call (one agent step) has a time limit of **120 s**. Over the limit, the call is cancelled and the job fails with `model_timeout` (AL-8, no retry). | Q5 A |
| U1-NFR-P.3 | One job has a time limit of **5 minutes** (300 s) from start (JB-3). Over the limit, the job and its model call are cancelled and it fails with `job_timeout`. The limit is fixed in code, not a setting. | Q4 A |
| U1-NFR-P.4 | The Ollama status check uses a 2 s timeout (ST-2) and runs on every full page load and before every job (ST-1). | Functional Design Q17 A |
| U1-NFR-P.5 | A Nominatim request has a **5 s** timeout (confirms Assumption A-3, PL-7). At most one request per second (process-wide). | Q6 A, Nominatim usage policy |
| U1-NFR-P.6 | Prompt size stays small: tools return at most 50 records and note text at most 1,000 characters (TA-6, TA-7, A-1); the loop has at most 8 steps (AL-1). | NFR-1.3 |

### 1.1 Expected behaviour on the measured laptop (known limitation)

Data from `model-spike-results.md` (Windows 11, 15.7 GB RAM, about 40% of the model on GPU), default model `qwen3:8b` with thinking on:

| Measure | Spike value | Against the limits |
|---|---|---|
| Success rate | 18/18 without limits | 15/18 (83%) would succeed with P.2 and P.3 applied |
| Steps over 120 s | 3 of 39 | these runs fail with `model_timeout` |
| Questions over 300 s | 3 of 18 (max 360.8 s) | these runs fail with `job_timeout` |
| Median per question | 117.7 s | NFR-1.1 Q&A target (30 s) is **not met** on this laptop |

The owner accepted this trade-off (Q1 A, Q4 A, Q5 A). The numbers are re-measured on the demo laptop in Build and Test.

## 2. Model acceptance

| Id | Requirement | Source |
|---|---|---|
| U1-NFR-M.1 | The default model is **`qwen3:8b` with thinking on** (Ollama's default for qwen3; the app sends no option to turn thinking off). Thinking blocks are removed from the output (AL-9). | Q1 A |
| U1-NFR-M.2 | The acceptance rule for a default model stays as Functional Design Q3 A: success ≥ 80% on every demo laptop and a median ≤ about 11 s per step. | Q2 A |
| U1-NFR-M.3 | `qwen3:8b` **fails the speed part** of M.2 on the measured laptop (median 65.6 s per step). This is recorded as a known limitation, not hidden; Build and Test re-measures success and step time on the demo laptop and reports both. | Q2 A |
| U1-NFR-M.4 | `llama3.1:8b` (Functional Design Q1 A) was the spike alternative only. It is not the default; a user may still set it in Settings (SE-2). | Q1 A, FD Q1 A |

## 3. Scalability

| Id | Requirement | Source |
|---|---|---|
| U1-NFR-S.1 | Single user on one laptop. No load or growth target. | NFR-3.1 |
| U1-NFR-S.2 | At most one running job (JB-1); at most 20 finished jobs kept in memory (JB-5). | FD Q19 A |

## 4. Availability and reliability

| Id | Requirement | Source |
|---|---|---|
| U1-NFR-R.1 | No uptime target: the user starts the app locally. | NFR-4.1 |
| U1-NFR-R.2 | When Ollama is down or the model is missing, pages still load and show the banner (ST-4); no job is created (ST-7). | NFR-4.1, US-19 |
| U1-NFR-R.3 | Place lookup failures never reach the agent as exceptions (PL-8). | US-17 S4 |
| U1-NFR-R.4 | Tool errors, step limit, model timeout, job timeout and internal errors end with the fixed messages ER-1 to ER-3. The server keeps running; nothing saved is changed. | NFR-4.2 |
| U1-NFR-R.5 | No automatic retry of model calls or jobs; the user presses Try again. | FD Q26 A |

## 5. Security and privacy

Security Baseline extension: opted out (skipped). The project's own rules still apply.

| Id | Requirement | Source |
|---|---|---|
| U1-NFR-SP.1 | Server binds to `127.0.0.1`; the model base URL accepts only localhost hosts over http (SE-3). No hosted LLM. | NFR-2.1 |
| U1-NFR-SP.2 | The only outbound request is the optional place lookup, off by default; it sends only coordinates rounded to 4 decimals (PL-2, PL-7). | NFR-2.2 |
| U1-NFR-SP.3 | Tool arguments are validated before tools run; tool results are delimited data (TR-1, TR-2); model text is HTML-escaped on display. | NFR-3.4, NFR-3.5 |
| U1-NFR-SP.4 | Logs never contain note text, journal text or full coordinates (only the rounded cache key) (see L.2). | Q8 A, NFR-2 |

## 6. Usability

| Id | Requirement | Source |
|---|---|---|
| U1-NFR-U.1 | Semantic HTML, keyboard use, readable contrast, no colour-only signals. | NFR-5.1 |
| U1-NFR-U.2 | Error messages use the fixed wording in ER-1, say what to do next, and timeouts say so plainly (`model_timeout`, `job_timeout`). | NFR-5.2 |

## 7. Maintainability and logging

| Id | Requirement | Source |
|---|---|---|
| U1-NFR-L.1 | Python `logging` to the console only. Default level INFO; `TRIP_JOURNAL_LOG_LEVEL` (DEBUG, INFO, WARNING, ERROR, any case) changes it; an invalid value logs a warning and uses INFO (like SE-6). No log file. | Q8 A |
| U1-NFR-L.2 | Logged: job start / finish / fail with code and duration, step number and step time, tool name and returned ids, status-check results, settings fallbacks (SE-6), full exception for `tool_failed` and `internal_error`. Not logged: note text, journal text, model prompts or replies, unrounded coordinates. | Q8 A, Q25 A |
| U1-NFR-L.3 | ruff (lint and format) and mypy pass before merge. | NFR-6.5 |
| U1-NFR-L.4 | Layers call downward only; tools use repositories, never raw SQL in the loop. | NFR-6.3 |
| U1-NFR-L.5 | Dependencies: lower bounds in `pyproject.toml`, exact versions in a committed `uv.lock` (details in `tech-stack-decisions.md`). | Q9 A |

## 8. Testability

| Id | Requirement | Source |
|---|---|---|
| U1-NFR-T.1 | pytest with ≥ 80% line coverage of U1 domain functions and tools (pytest-cov). | NFR-7.1 |
| U1-NFR-T.2 | Agent loop tests use a fake LLM client with scripted replies, including a call that exceeds the 120 s limit (simulated with a short limit in tests) and a job that exceeds 5 minutes (same). | NFR-7.2, P.2, P.3 |
| U1-NFR-T.3 | Property-based tests use **Hypothesis**. Profiles: `default` 100 examples per property; `ci` 500 examples, selected by `HYPOTHESIS_PROFILE=ci`. Failing examples are kept in the Hypothesis example database (`.hypothesis/`, git-ignored). | Q7 A, PBT-09 |
| U1-NFR-T.4 | The PBT properties are those in `business-rules.md` §10 (P-G1 to P-Q2 blocking where PBT-02 / 03 apply; P-J1 advisory). Domain generators (trips, stops, notes, photos, settings values, coordinates, citation texts) live in one shared test module and respect the business rules (PBT-07). Shrinking stays on; both profiles set `print_blob=True` so a failure prints the shrunk input and a replay blob; the pre-merge run passes an explicit `--hypothesis-seed` so the seed is in the log (PBT-08). | PBT Partial mode |
| U1-NFR-T.5 | No test needs a running Ollama or network; Nominatim is tested with a mock transport. | NFR-7.2 |

## 9. Changes to Functional Design

| Rule | Change | Source |
|---|---|---|
| AL-8 | Adds the per-call limit: 120 s. | Q5 A |
| PL-7 | Assumption A-3 confirmed: 5 s timeout. The "[Assumption A-3]" marker can be removed at NFR Design. | Q6 A |
| SE-1 | Default `qwen3:8b` confirmed; thinking on. | Q1 A |
| JB-3 | 5 minutes confirmed, fixed in code. | Q4 A |
| New | `TRIP_JOURNAL_LOG_LEVEL` environment variable (L.1). It is not a Settings-page field. | Q8 A |

## 10. Extension compliance

| Extension / rule | Status | Note |
|---|---|---|
| Security Baseline | N/A (opted out) | Skipped per `aidlc-state.md` |
| Resiliency Baseline | N/A (opted out) | Skipped per `aidlc-state.md` |
| PBT-09 framework selection (blocking) | Compliant | Hypothesis chosen (T.3, `tech-stack-decisions.md` §3) |
| PBT-02, 03, 07, 08 (blocking) | N/A at this stage | Apply at Code Generation; requirements stated in T.3, T.4 |
| Other PBT rules (advisory) | N/A at this stage | |
