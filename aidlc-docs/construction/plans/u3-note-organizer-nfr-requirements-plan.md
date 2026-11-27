# U3 Note Organizer - NFR Requirements Plan

**Stage**: Construction - NFR Requirements (unit U3 Note Organizer)
**Inputs**: `aidlc-docs/construction/u3-note-organizer/functional-design/` (4 files; open items NFR-O1..O3 in `business-rules.md` §13), `aidlc-docs/construction/u1-foundation/nfr-requirements/` and `u2-import-and-timeline/nfr-requirements/` (precedent), `aidlc-docs/construction/u1-foundation/model-spike-results.md`, `unit-of-work.md` U3 section, `requirements.md` NFR-1 to NFR-7
**Outputs**: `aidlc-docs/construction/u3-note-organizer/nfr-requirements/nfr-requirements.md`, `aidlc-docs/construction/u3-note-organizer/nfr-requirements/tech-stack-decisions.md`
**Extensions**: Security Baseline and Resiliency Baseline opted out (skipped). PBT Partial: PBT-02, 03, 07, 08, 09 blocking. PBT-09 (Hypothesis) was decided in U1 and is reused.

## Plan steps

- [x] 1. Analyze the U3 Functional Design artifacts and the U1 / U2 NFR decisions (Step 1)
- [x] 2. Probe local Ollama for evidence on NFR-O1 and NFR-O2 (section "Probe evidence")
- [x] 3. Write this plan with questions (Steps 2-4)
- [x] 4. Collect the owner's answers and check them for ambiguity (Step 5)
- [x] 5. Write `nfr-requirements.md`: performance, scalability, reliability, security, usability, logging, testability incl. PBT settings (Step 6)
- [x] 6. Write `tech-stack-decisions.md`: output format, thinking mode, reused stack, dependencies (Step 6)
- [x] 7. Record the NFR Design execute / skip decision (Question 12)
- [x] 8. Present the completion message and wait for approval (Steps 7-8)

## Already decided (no question)

| Topic | Decision | Source |
|---|---|---|
| Stack | Python 3.12+, FastAPI, Jinja2 + htmx, Pydantic v2, `sqlite3` direct in the event loop, `openai` SDK against Ollama's `/v1` endpoint | U1 tech-stack, U1 NFR Design |
| Model | `qwen3:8b` default; one call per batch; per-call limit 120 s; no retries (`max_retries=0`); `<think>` blocks removed (AL-9) | U1-NFR-P.2, M.1, AL-8, AL-9 |
| Batches and job limit | ≤ 10 notes per batch; job limit `min(300 s × batches, 1800 s)`; each batch saved in its own transaction | OR-RUN2, OR-RUN3, OR-SAVE1 |
| Concurrency | One job at a time (409 `model_busy`); review actions allowed during a job (FA-4); a batch save writes only notes still undecided at save time (FA-3). All DB work runs on the event-loop thread, so the check and the write cannot interleave with a review action | U1 JB rules, FA-3, FA-4 |
| Security | Security Baseline opted out. Localhost only; note text inside `<trip_data>`; labels limit what the model can touch (OR-V1); Jinja autoescape; Pydantic for edits | NFR-3, OR-D5, prompt §5 |
| Raw data | U3 never writes `notes.text` / `notes.stop_id` (OR-R1); checked by P-O2 | FR-3.4 |
| Coverage | ≥ 80% line coverage of U3 modules; ruff and mypy strict | unit-of-work DoD, NFR-6.5, NFR-7.1 |
| Tests offline | No test needs Ollama or network; all tests use `FakeLLMClient` | NFR-7.2 |

## Probe evidence (2026-11-27, this laptop)

Same laptop as the U1 spike (Windows 11, 15.7 GB RAM, Ollama 0.40.18, `qwen3:8b` Q4_K_M, about 2.3 of 6.0 GB on GPU, context 4096). One 10-note day with 4 stops (food with ratings, scene, logistics, feedback, an instruction-like note, a mixed Chinese / Portuguese note, a note with no stop), temperature 0, one call per run, through the `openai` SDK at `/v1`. Raw data: `spike_results/organizer-probe-1_20261127.json`, `organizer-probe-2_20261127.json` (not committed; scripts next to them).

| Run | `response_format` | Thinking switch | Result | Time | Output tokens |
|---|---|---|---|---|---|
| 1 | `json_schema` | none (thinking on) | valid JSON, 10 items, enum kept; thinking returned in a separate `reasoning` field, not in `content` | 342 s | 1,208 |
| 2 | `json_schema` | none (thinking on) | client timeout | > 600 s | - |
| 3 | `json_schema` | `/no_think` in the system prompt | valid, 10 items, but thinking still ran (reasoning 4,307 chars) | 505 s | 1,784 |
| 4 | `json_object` | none (thinking on) | client timeout | > 600 s | - |
| 5 | `json_schema` | `extra_body={"think": false}` | client timeout (switch not honoured, presumed) | > 400 s (×2) | - |
| 6 | `json_schema` | `reasoning_effort="none"` | **valid, 10 items, all labels right, no reasoning** | **116 s** | 466 |

What this shows (one laptop, one run each, so a guide, not a benchmark):
- **NFR-O1**: Ollama honours `json_schema` with thinking on and with thinking off; the `<think>` text does not reach `content`.
- **NFR-O2**: with thinking on, one 10-note batch takes 342 s or more, so **every batch would fail the 120 s per-call limit** (U1-NFR-P.2). `reasoning_effort="none"` is the only switch that turned thinking off; then the batch took 116 s, just under the limit.
- Quality of run 6 (my reading, to be checked in Question 6): category and stop look right for 10 of 10; the instruction-like note was classed `feedback` and gave no rating; one rating came back as `8` for "8/10" (dropped by OR-F3 unless the prompt's conversion rule is followed); `tip` was filled with the whole note for some scene and logistics notes, against OR-F1 "only when the note contains one" (prompt wording to tighten in Code Generation).

---

## Question 1 (NFR-O1)
Which `response_format` does the organizer send to Ollama?

A) `{"type": "json_schema", "json_schema": {"name": "OrganizerReply", "schema": ...}}` as Functional Design Q8 A, with no fallback: the probe shows Ollama honours it (runs 1, 3, 6). The parser still checks everything (OR-V1..V8), so a reply that ignores the schema fails as `invalid_json` like any other bad reply. A fallback to `json_object` would be a second call, which AL-8 (no retries) does not allow

B) `json_schema`, and if Ollama answers with an HTTP 400 for it, fall back once to `json_object` for that batch (an exception to AL-8)

C) `json_object` only (the schema stays in the prompt text)

D) No `response_format`; JSON is asked for in the prompt only

E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 (NFR-O2)
Thinking mode for the organizer call?

A) **Thinking off for the organizer only**, by sending `reasoning_effort="none"` on the organizer call (the only switch that worked in the probe, run 6). The Q&A and journal agent calls keep thinking on (U1-NFR-M.1 unchanged). `LLMClient.chat` gets an optional `reasoning_effort` argument; `FakeLLMClient` records it so a test can check the organizer sends it. If a later Ollama version ignores it, the per-call limit (Question 3) turns that into `call_timeout`, not a hang

B) Thinking on, as U1 (with today's speed every batch on this laptop would hit the per-call limit)

C) Thinking off through `/no_think` in the prompt (the probe shows it does not work with `json_schema`)

D) A setting on the Settings page, default off

E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 (NFR-O2)
What speed target applies to organizing?

With thinking off, one 10-note batch took 116 s on this laptop, against a 120 s per-call limit.

A) **Organizer per-call limit 240 s** (organizer only; the agent loop keeps 120 s, U1-NFR-P.2). Speed **targets**, not hard limits, on the measured laptop: ≤ 120 s per 10-note batch, so a 10-note day ≤ 2 min and a 30-note day (3 batches) ≤ 6 min. The job limit stays `min(300 s × batches, 1800 s)` (OR-RUN3), which leaves room for a 240 s call per batch. Misses are recorded in Build and Test with the laptop, like U1-NFR-P.1

B) Keep the 120 s per-call limit and make batches smaller (≤ 5 notes, about 60 s each); this changes Functional Design OR-RUN2 (Q6 A)

C) Keep 120 s and 10 notes; accept that some batches fail with `call_timeout` on this laptop

D) No organizer speed target; only the limits

E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
The reference large trip (U2-NFR-S.2) has 2,000 notes, so about 200 batches. Under the 1,800 s job cap, at the probe's 116 s per batch, one "whole trip" run organizes about 15 batches (about 150 notes). What should the requirement say?

A) Accept it: a whole-trip run organizes as many batches as fit and stops with `job_timeout`; saved batches stay (OR-SAVE3), and the summary says "Run again to continue with the remaining N notes". The reference for a full run is a normal trip (the minimal sample trip and one day of the reference trip)

B) Raise the cap for whole-trip runs (for example `min(300 s × batches, 4 h)`)

C) Limit "Organize the whole trip" to trips with at most N notes (for example 200) and ask the user to organize larger trips day by day

D) No whole-trip run at all; day by day only

E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
How large may one batch's prompt be? (The app sends no `num_ctx`, so Ollama's default context applies; 10 notes of up to 1,000 characters each plus the stops is about 3,000-4,000 tokens before the reply and the thinking.)

A) Each note's text is cut to 1,000 characters in the prompt (same as TA-7), and a batch is also closed early when its note text passes 6,000 characters, so a batch has ≤ 10 notes **and** ≤ 6,000 characters of note text. A cut note gets a "(truncated)" mark in the prompt only; the stored text is unchanged

B) Only the 10-note limit; no character limit

C) Same as A, and the app also sends `num_ctx` (for example 8192) through `extra_body`

D) Cut note text to 500 characters

E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 (NFR-O3)
Accuracy (≥ 85% correct category and stop, FR-11) is measured by U6. Should U3 have its own smoke check?

A) Yes, manual and non-blocking: in U3 Build and Test, run the organizer once on a fixed labelled set (the minimal sample trip plus the 10-note probe day in this plan) and record category and stop accuracy and time per batch. The formal ≥ 85% measurement stays in U6

B) Yes, and blocking: U3 is not done until the smoke set reaches ≥ 85%

C) Yes, as an automated test marked `ollama`, skipped by default

D) No; leave all accuracy work to U6

E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7
What speed target applies to the review actions (Accept, Edit and accept, Reject, Undo, Accept all), which do not use the model?

A) A target, not a hard limit: server time ≤ 300 ms for each action, including re-rendering the stop region, on one day of the reference large trip (same as U2-NFR-P.4); measured in Build and Test

B) Same number, blocking

C) No target

D) ≤ 100 ms

E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8
What does U3 log? (Format as U1: Python `logging`, console, key=value, `job_id` attached.)

A) One INFO line per batch (`trip_id`, `day`, `batch=i/I`, `notes`, `kept`, `dropped`, `not_organized`, `outcome` = `ok` / `empty_reply` / `invalid_json` / `model_error` / `call_timeout`, `duration_ms`), one INFO line per run (`batches`, `ok_batches`, totals, `duration_ms`, final job status), and one INFO line per review action (`suggestion_id`, `action`, `from`, `to`; Accept all logs the count). Drop reasons are logged only as codes. Never logged: note text, model reply text, dish, tip

B) Same as A, without the review-action lines

C) Same as A, and at DEBUG level the full model reply (for prompt tuning)

D) Only the run line

E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9
How does a lost connection to Ollama during a run behave? (Today a model error fails the batch and the run moves on, OR-V6.)

A) As designed: each later batch also fails fast with `model_error`; the run ends `failed` if no batch worked, otherwise `succeeded` with warnings. No status check between batches. The summary lists the failed batches, and a re-run continues with the notes left (OR-RUN1)

B) Stop the run at the first `model_error` that is a connection error (no further calls), and keep the saved batches

C) Run the 2 s status check (ST-2) before each batch and stop when Ollama is down

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10
Property-based test settings (PBT-07, PBT-08) for U3?

A) Reuse the U1 profiles (`default` 100 examples, `ci` 500, `print_blob=True`, `deadline=None`, seed in the pre-merge run). P-O4 (`RuleBasedStateMachine`) uses `stateful_step_count=30`. P-O3 reply generator: a strategy for valid items built from the batch labels and the five categories, plus mutations (unknown labels, wrong category, rating as string / fraction / out of range, over-long strings, duplicate notes, extra keys, non-object top level) and arbitrary JSON values. Shared strategies go in `tests/strategies.py`

B) Same as A, with Hypothesis's default `stateful_step_count` (50)

C) Same as A, but P-O4 only in the `ci` profile (skipped in the normal run)

D) A new profile for U3 with more examples

E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11
New dependencies for U3?

A) None. The reply is checked by a Pydantic model and the OR-V rules (no `jsonschema` library); the JSON schema sent in `response_format` is generated from the same Pydantic model (`model_json_schema()`)

B) Add the `jsonschema` library to validate the reply against the schema before the OR-V rules

C) Use a structured-output library (for example `instructor`)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 12
Should NFR Design be skipped for U3?

A) Skip. U3 adds no new NFR pattern beyond what U1 NFR Design set (per-call and job timeouts, `sqlite3` in the event loop, logging format) and U2 used (one transaction per write). Implementation notes go into `nfr-requirements.md` as a short section, as U2 did

B) Execute NFR Design for U3 (for example for the batch save transaction and the output-format fallback)

C) Other (please describe after [Answer]: tag below)

[Answer]: A
