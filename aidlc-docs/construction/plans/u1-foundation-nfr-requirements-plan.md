# U1 Foundation - NFR Requirements Plan

**Stage**: Construction - NFR Requirements (unit U1 Foundation)
**Inputs**: `aidlc-docs/construction/u1-foundation/functional-design/` (4 files), `aidlc-docs/construction/u1-foundation/model-spike-results.md`, `aidlc-docs/inception/requirements/requirements.md` (NFR-1 to NFR-7), `docs/technical-environment.md`
**Outputs**: `aidlc-docs/construction/u1-foundation/nfr-requirements/nfr-requirements.md`, `aidlc-docs/construction/u1-foundation/nfr-requirements/tech-stack-decisions.md`
**Extensions**: Security Baseline and Resiliency Baseline opted out (skipped). PBT Partial: PBT-09 (framework choice) is decided here.

## Plan steps

- [x] 1. Analyze the Functional Design artifacts and the spike results (Step 1)
- [x] 2. Write this plan with questions (Steps 2-4)
- [x] 3. Collect the owner's answers (interview) and check them for ambiguity (Step 5)
- [x] 4. Write `nfr-requirements.md`: performance, scalability, availability, reliability, security and privacy, usability, maintainability, testability (Step 6)
- [x] 5. Write `tech-stack-decisions.md`: model, libraries, PBT framework, logging, dependency pinning (Step 6)
- [x] 6. Present the completion message and wait for approval (Steps 7-8)

## Categories with no open question

| Category | Why no question | Source |
|---|---|---|
| Scalability | Single user, one laptop, one running job at a time (JB-1). No growth target. | NFR-3.1, JB-1 |
| Availability | Local app, started by the user; no uptime target. Graceful degradation when Ollama or the place lookup is down is already required. | NFR-4.1 |
| Security | Security Baseline opted out. Localhost only, no auth, tool-argument validation, delimited tool results and localhost-only base URL are already set. | NFR-2, NFR-3, SE-3, TR-1 |
| Usability | Semantic HTML, keyboard use, fixed error wording already set. | NFR-5, ER-1 |

## The conflict behind Questions 1-4 (read first)

Spike data from the one laptop tested (Windows 11, 15.7 GB RAM, about 40% of the model on GPU):

| Model | Success | Median per step | Median per question (max) |
|---|---|---|---|
| qwen3:8b, thinking on | 18/18 (100%) | 65.6 s | 117.7 s (360.8 s) |
| qwen3:8b, thinking off | 6/6 (100%) | 47.9 s | 104.9 s (252.7 s) |
| llama3.1:8b | 12/18 (67%); q3_photos and q4_place fail 3/3 | 5.8 s | 15.4 s (27.3 s) |

- Functional Design Q1 A chose `llama3.1:8b` as the **spike alternative**. business-rules.md SE-1 sets the **default** to `qwen3:8b` (from Application Design). The default is decided here.
- Functional Design Q3 A says a default needs **≥ 80% success and ≤ about 11 s per step**. No tested model meets both on this laptop.
- NFR-1.1 asks for a journal in ≤ 90 s and a Q&A answer in ≤ 30 s. Only llama3.1:8b is near that speed.
- Functional Design Q20 A stops a job after 5 minutes. qwen3:8b with thinking had a question take 360.8 s, so it would be stopped.

## Question 1
Which model is the default (`TRIP_JOURNAL_MODEL` default, SE-1)?

A) `qwen3:8b` with thinking on: always correct in the spike, but about 1-6 minutes per question on this laptop

B) `qwen3:8b` with thinking off: correct 6/6, about 25% faster, still about 1.5-4 minutes per question

C) `llama3.1:8b`: about 15 s per question, but wrong tool or wrong citation on 2 of 6 question types; the grounding check flags the bad citations

D) `qwen3:8b` as the default, and the Settings page tells slow laptops that `llama3.1:8b` is a faster but less accurate choice

E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
How should the Functional Design Q3 A acceptance rule (≥ 80% success, ≤ 11 s per step) be treated, given no model meets it here?

A) Keep it as the rule; record that the chosen default fails it on this laptop as a known limitation, and re-measure on the demo laptop in Build and Test

B) Change it to success only (≥ 80%); speed becomes a target, not a gate

C) Change it to speed only; accuracy problems are handled by the grounding check and prompts

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
What happens to the NFR-1.1 speed targets (journal ≤ 90 s, Q&A ≤ 30 s)?

A) Keep them as targets measured on the slowest demo laptop (NFR-1.2); missing them is reported, not a blocker

B) Relax them to fit qwen3:8b on this laptop (for example journal ≤ 6 min, Q&A ≤ 3 min)

C) Keep them as hard requirements (then only a fast model or faster hardware can pass)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
Overall job time limit (Functional Design Q20 A, JB-3: 5 minutes)?

A) Keep 5 minutes

B) Raise to 10 minutes, so qwen3:8b multi-step questions finish on this laptop

C) Make it a setting with default 10 minutes

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
Time limit for one model call (AL-8 `model_timeout`; not set yet)?

A) 120 s

B) 240 s (covers the slowest qwen3:8b step seen, 227 s)

C) Same as the job limit (no separate per-call limit)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6
Nominatim request timeout (Assumption A-3, PL-7)?

A) 5 s

B) 10 s

C) 3 s

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7
Property-based testing framework and run size (PBT-09)?

A) Hypothesis; default profile 100 examples per property, a `ci` profile with 500, failing examples kept in the Hypothesis database (git-ignored)

B) Hypothesis with default settings only (100 examples)

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8
Server logging?

A) Python `logging` to the console, INFO by default, level set by `TRIP_JOURNAL_LOG_LEVEL`; never log note text or coordinates beyond the rounded key

B) Console plus a rotating log file under `data/logs/`

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9
Dependency versions?

A) Lower bounds in `pyproject.toml` (for example `fastapi>=0.115`), exact versions locked in a committed `uv.lock`

B) Exact pins in `pyproject.toml`

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Answer analysis (Step 5)

All 9 answers were chosen by the owner (Ivan Huang) in an interview on 2026-11-26; each is a single listed option, so no clarification file is needed.

Combined effect checked against the spike data (this laptop, qwen3:8b thinking on, 18 runs): with a 120 s per-call limit (Q5 A) and a 5-minute job limit (Q4 A), 3 of 39 steps exceed 120 s and 3 of 18 questions exceed 300 s; 15 of 18 runs (83%) would still succeed. This stays above the 80% success part of the Q3 A rule (kept by Q2 A) and is recorded as a known limitation in `nfr-requirements.md`.
