# AI Prompt Log: Trip Journal Agent (INFO5940)

- **Covers:** U1 Foundation Construction (AI-DLC), `scripts/model_spike.py`, `aidlc-docs/`
- **AI assistant:** Claude Code (desktop app), model Claude Opus 5.5
- **Note:** the full raw text of every prompt is also in `aidlc-docs/audit.md` (AI-DLC audit trail).

## 1. Start U1 Foundation Construction (model spike first)
**Date:** 2026-11-25

**Prompt:**
> (Long pasted session instructions; full raw text in `aidlc-docs/audit.md`, entry "Construction Start - Session Request (U1 Foundation)".) Key parts: "ignore the task assignment for the whole project, continue" ... "unit U1 Foundation only ... U1 starts with the model spike (plan Q8 A): ... write a small spike script that tests tool calling with qwen3:8b and one alternative tool-capable Ollama model on a few scripted questions, recording success rate, time per step and memory use." ... "Do not commit or push; I will do that myself."

**Answer:** Started AI-DLC Construction for U1. Wrote the model spike script and the U1 Functional Design plan with 26 open questions for the team (none answered by the AI). Updated `aidlc-state.md` and `audit.md`. The script uses the five planned tools on a synthetic trip, a mini agent loop (max 8 steps, argument validation) and records success rate, valid-call rate, step time, warm-up time and Ollama memory. Applied to files.

**Code (scripts/model_spike.py):** whole file added (tagged in its header).
**Docs:** `aidlc-docs/construction/plans/u1-foundation-functional-design-plan.md` added.

## 2. Language change and status
**Date:** 2026-11-25

**Prompt:**
> use chinese for the chat but only use english to save status or md or files in repo.
> so what is the current status and what is the next step

**Answer:** Explanation only. Chat switched to Chinese; reported status and next steps.

**Code:** none

## 3. Pick two models, move to D:, run the spike
**Date:** 2026-11-25

**Prompt:**
> pick 2 model to pull to d drive, then run the model and save spike results

**Answer:** Picked llama3.1:8b and qwen3:4b as alternatives to qwen3:8b. Set the user environment variable `OLLAMA_MODELS=D:\ollama\models`, copied the existing model store there, restarted Ollama and pulled both models. The qwen3:8b smoke test passed 6/6 (median about 63 s per step, 5.58 GB, 39% on GPU). The full spike (3 models x 3 repeats x 6 questions) is running; results go to `spike_results/`.

**Code:** none (machine setup and script runs only)

## 4. Status
**Date:** 2026-11-25

**Prompt:**
> status

**Answer:** Explanation only: progress table of the spike run.

**Code:** none

## 5. Switch to ai-home rules
**Date:** 2026-11-25

**Prompt:**
> use ai home rule

**Answer:** Asked which scope; the owner chose the full global rules (Chinese human-readable docs, prompt log, explain-then-wait, subagents allowed, skill tracking), with AI-DLC kept as the project workflow and `audit.md` / `aidlc-state.md` kept in English. Created this log and tagged the spike script header (comments only).

**Code (scripts/model_spike.py):** header comment block added (no executable change).

## 6. Fix the spike script and rerun
**Date:** 2026-11-25

**Prompt:**
> Apply 并重跑

**Answer:** The first full run lost all results when the Ollama server stopped, because the script wrote JSON only at the end and the warm-up call had no error handling. Changed the script to save after every run and to record a failed model and move on to the next one. Restarted Ollama as a detached app (so it does not depend on the chat session) and started the rerun in the background (3 models x 3 repeats x 6 questions, output in `spike_results/`).

**Code (scripts/model_spike.py):** `[PROMPT #6] CHANGED` block in `main()`: `save()` helper, per-model `try/except` with an `aborted` list in the report, server check before each model. Test status: `py_compile` passes; the rerun is the runtime test.

## 7. Why three models
**Date:** 2026-11-25

**Prompt:**
> status? dont we only need 2 model? why run 3

**Answer:** Explanation only: the requirement is qwen3:8b plus one alternative; qwen3:4b was extra (from reading "pick 2 model to pull" as two new models) and was no faster here, so stopping it was recommended.

**Code:** none

## 8. Stop qwen3:4b and summarize
**Date:** 2026-11-25

**Prompt:**
> 停掉 qwen3:4b，写汇总

**Answer:** Stopped the run (qwen3:4b after 3 runs). Wrote `aidlc-docs/construction/u1-foundation/model-spike-results.md`: qwen3:8b 18/18 but slow (65.6 s per step median); llama3.1:8b 12/18 and about 10x faster, failing q3_photos (citation) and q4_place (wrong tool) every time.

**Code:** none (results document only)

## 9. Interview for the Functional Design questions
**Date:** 2026-11-25

**Prompt:**
> interview me the question

**Answer:** Asked all 26 plan questions as multiple-choice dialogs; the owner chose A for every question. Answers written into the plan file; no ambiguities. Started the qwen3:8b `--no-think` spike run (Question 2 A).

**Code:** none (plan answers and a spike run only)

## 10. Generate the Functional Design documents

**Date:** 2026-11-26

**Prompt:**
> 生成设计文档

**Answer:** Wrote the four U1 Functional Design artifacts (domain entities, business logic model, business rules with property-based test properties and a story/DoD check, frontend components) from the 26 answers. Listed 13 interface changes against component-methods.md and 3 open assumptions for the owner to review.

**Code:** none (design documents only)

## 11. NFR Requirements for U1 (plan, interview, documents)

**Date:** 2026-11-26

**Prompt:**
> (main chat task) Run the AI-DLC stage "NFR Requirements" for unit U1 Foundation; settle A-3 (Nominatim timeout) and the default model with the owner.

**Answer:** Wrote the NFR Requirements plan with 9 questions and showed the model conflict (no model meets the Functional Design speed rule on this laptop). The owner chose A for all 9: default qwen3:8b with thinking on, speed limits kept as targets with the miss recorded as a known limitation, 5-minute job limit, 120 s per model call, 5 s Nominatim timeout, Hypothesis with a ci profile, console logging, lower bounds plus uv.lock. Wrote nfr-requirements.md and tech-stack-decisions.md.

**Code:** none (plan and NFR documents only)

## 12. NFR Design for U1 (plan, interview, documents)

**Date:** 2026-11-26

**Prompt:**
> (main chat task) Run the AI-DLC stage "NFR Design" for unit U1 Foundation; cover the 5-minute job limit, the 120 s per-call timeout, the Nominatim 5 s timeout and 1 request/s lock, the Hypothesis ci profile and console logging.

**Answer:** Wrote the NFR Design plan with 6 questions. The owner chose A for all 6: asyncio.timeout(120) around each model call (openai client timeout as backstop, max_retries=0), sqlite3 called directly in the event loop, one Nominatim lock held through the request with the 5 s limit on the request only, Hypothesis deadline=None in both profiles, plain-text key=value log lines with job_id, uvicorn logs in the same format with access lines on. Wrote nfr-design-patterns.md (NP-1 to NP-9) and logical-components.md (LC-1 to LC-13).

**Code:** none (plan and NFR design documents only)

## 13. Code Generation for U1 Foundation (plan + code + tests)

**Date:** 2026-11-26

**Prompt:**
> (main chat task) Run the AI-DLC Code Generation stage for unit U1 Foundation: Part 1 plan with checkbox steps, file list, test list and PBT mapping, wait for approval; Part 2 generate code in trip_journal/, summaries in aidlc-docs/construction/u1-foundation/code/, run unit and property tests with uv (Hypothesis ci profile); do not start Build and Test; do not commit or push. Owner reply to the plan: "批准，含下载".

**Answer:** Wrote the 29-step plan (approved with the one-time htmx 2.0.4 download), then generated the trip_journal package (data, domain, agent, places, services, api, pages) and the tests (unit, agent, api, property). Property tests found a NUL-in-query bug in search; fixed in split_terms. Results: 154 tests passed, coverage 95%; ci profile 22 property tests passed (seed 12345); ruff and mypy strict clean on trip_journal and tests. Not verified: real Ollama, real Nominatim, real browser.

**Code:** all files under `trip_journal/` and `tests/` tagged `ADDED [PROMPT #13]`; `trip_journal/data/repositories.py` `split_terms` tagged `CHANGED [PROMPT #13]`. Summary: `aidlc-docs/construction/u1-foundation/code/code-summary.md`.
