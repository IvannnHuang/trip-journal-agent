# U4 Daily Journal - NFR Requirements Plan

**Stage**: Construction - NFR Requirements (unit U4 Daily Journal)
**Inputs**: `aidlc-docs/construction/u4-daily-journal/functional-design/` (4 files; BL-2 leaves speed and thinking mode to this stage), `aidlc-docs/construction/u1-foundation/nfr-requirements/` and `u3-note-organizer/nfr-requirements/` (precedent), `aidlc-docs/construction/u1-foundation/model-spike-results.md`, `requirements.md` NFR-1 to NFR-7
**Outputs**: `aidlc-docs/construction/u4-daily-journal/nfr-requirements/nfr-requirements.md`, `aidlc-docs/construction/u4-daily-journal/nfr-requirements/tech-stack-decisions.md`
**Extensions**: Security Baseline and Resiliency Baseline opted out (skipped). PBT Partial: PBT-02, 03, 07, 08, 09 blocking. PBT-09 (Hypothesis) was decided in U1 and is reused.

## Plan steps

- [x] 1. Analyze the U4 Functional Design artifacts and the U1 / U3 NFR decisions (Step 1)
- [x] 2. Probe local Ollama with a journal-style run (section "Probe evidence")
- [x] 3. Write this plan with questions (Steps 2-4)
- [x] 4. Collect the owner's answers and check them for ambiguity (Step 5)
- [x] 5. Write `nfr-requirements.md`: performance, scalability, reliability, security, usability, logging, testability incl. PBT settings (Step 6)
- [x] 6. Write `tech-stack-decisions.md`: thinking mode, limits, context size, reused stack, dependencies (Step 6)
- [x] 7. Record the NFR Design execute / skip decision (Question 14): skip; implementation notes N-1..N-9 in `nfr-requirements.md` §9
- [x] 8. Present the completion message and wait for approval (Steps 7-8)

## Already decided (no question)

| Topic | Decision | Source |
|---|---|---|
| Stack | Python 3.12+, FastAPI, Jinja2 + htmx, Pydantic v2, `sqlite3` direct in the event loop, `openai` SDK against Ollama's `/v1` endpoint | U1 tech-stack, U1 NFR Design |
| Model | `qwen3:8b` default; `max_retries=0`; no automatic retry (JR-F4); `<think>` blocks removed (AL-9) | U1-NFR-M.1, AL-8, AL-9 |
| Agent loop | `AgentLoop(max_steps=8)` with the five read-only tools; prompt asks for the answer by step 4 | BL-2, BL-6, FD Q7 A |
| Jobs | One job at a time (409 `model_busy`); edits allowed during a job (JR-S3); one `BEGIN IMMEDIATE` save step guarded by `WHERE owner = 'generated'` (JR-S1) | U1 JB rules, BL-4 |
| Failure | A failed run leaves the saved journal untouched and its trace is not saved (JR-F1, JR-F2) | FD Q10 A |
| Security | Security Baseline opted out. Localhost only; tool output delimited as data (`_shared_tool_data.md`); Jinja autoescape; citations rendered from escaped text; logs never hold note or journal text | NFR-2, NFR-3, U1-NFR-SP.* |
| Coverage | ≥ 80% line coverage of U4 modules; ruff and mypy strict | unit-of-work DoD, NFR-6.5, NFR-7.1 |
| Tests offline | No test needs Ollama or network; all tests use `FakeLLMClient` | NFR-7.2 |

## Probe evidence (2026-11-27, this laptop)

Same laptop as the U1 spike and the U3 probe (Windows 11, 15.7 GB RAM, Ollama 0.40.18, `qwen3:8b` Q4_K_M, about 2.3 of 6.0 GB on GPU, `context_length` 4096 per `/api/ps`). One journal run per row on the minimal sample trip (2026-05-02: 4 stops, 7 notes on stops, 1 note without a stop, 10 photos), so 5 slots (`summary`, `stop:1..4`). The run used the **real** `AgentLoop` (8 steps), `default_registry()` and an in-memory database; a draft of the BL-6 prompt (tool plan, slot headings, citation rule, do-not-invent rule, casual tone). Per-call limit raised to 900 s for the probe so times are measured, not cut. Script and raw JSON are in the session scratchpad only (not in the repo, not in `spike_results`).

| Run | Setting | Steps (time each) | Total | Slots written | Tools called | Sentences with a citation | Grounded? |
|---|---|---|---|---|---|---|---|
| 1 | `reasoning_effort="none"` (thinking off) | 2 (29.0 s, 90.4 s) | **119 s** | 5 / 5 | `list_day_stops` only | 4 / 15 | **No**: never read the notes; invented espresso, pastries, street art, a traditional dish |
| 2 | thinking on (U1 default) | 2 (173.7 s, 184.8 s) | **359 s** | 5 / 5 | `list_day_stops` only | 14 / 14 | **No**: never read the notes; invented facts **with real-looking ids** (`[note:2]`, `[note:5]`, `[photo:1]`...) |
| 3 | thinking off, **app pre-fetches** `list_day_stops` + `get_stop_notes` for every stop and puts the results in the history before the first model call | 1 (99.4 s) | **99 s** | 5 / 5 | (pre-fetched) | 4 / 14 | **Mostly yes**: every fact comes from the notes (pastel de nata, 2.80 EUR, tile panel, 12 EUR, bacalhau); small additions ("in Lisbon", "the atmosphere was warm"); citations only at the end of each paragraph; the stop-less note (tram 28) not used |

What this shows (one laptop, one run each, so a guide, not a benchmark):
- **The model ignores the tool plan.** In both agent runs it called `list_day_stops`, saw `note_count`, and wrote the journal without one `get_stop_notes` call. The prompt rule "call `get_stop_notes` for every stop" (BL-6) is not enough with `qwen3:8b`.
- **Thinking on is slower and not safer.** Both steps exceeded the 120 s per-call limit (U1-NFR-P.2), so run 2 would fail with `model_timeout` in the app; and it fabricated citations to ids that exist in the trip, which the FD grounding check (JR-G1: known ids = all trip ids) would count as **supported**.
- **Pre-fetch + thinking off** gave the only grounded draft and the fastest run (99 s for a 4-stop day), still over the NFR-1.1 target of 90 s on this laptop.
- **Citations per sentence** were not followed (4 / 14 cited in run 3), so the per-sentence check (BL-7) would flag about 10 sentences as unsupported. The prompt needs a stronger rule and an example (Code Generation).
- **Context size.** Ollama runs with a 4,096-token context on this laptop. The minimal day fits. The busiest day of the reference large trip (U2-NFR-S.2) has 22 stops and 115 notes (about 8,400 characters of note text, more with the JSON wrapping of tool results), which will not fit in one call; Ollama would cut the prompt without an error.

---

## Questions

Owner answer (2026-11-28T00:08:56Z): "all A". All 14 answers are A; no ambiguity (Q12 chunk-split property applies because Q5 = A).

Answer each question by writing the letter after `[Answer]:`. Option A is the recommendation each time. "Other" is always allowed; describe it after the tag.

### Question 1 - How does the journal gather the day's records?
The probe shows `qwen3:8b` skips `get_stop_notes` even when the prompt orders it (runs 1 and 2).

A) **App pre-fetch.** Before the first model call the app runs `list_day_stops(day)` and `get_stop_notes(stop_id)` for every stop of the day (no model step used), records them in the trace as step 0 (same trace format as tool calls), and starts the loop with those results in the history. `find_photos`, `search_notes`, `lookup_place` stay available. Changes FD BL-2 / BL-6 (the tool plan in the prompt becomes "records are already loaded; use tools only for photos or other days"). Matches run 3.
B) Pure agent as in FD (model decides every call); accept ungrounded drafts.
C) Pre-fetch as in A, plus `find_photos(day)` so photos can be cited.
D) Pure agent, but reject a run (`journal_ungrounded`) when no `get_stop_notes` call happened for a stop that has notes.
E) Other

[Answer]: A

### Question 2 - Thinking mode for journal calls
A) **Off** (`reasoning_effort="none"`) for journal calls only, like the U3 organizer. `AgentLoop` gains an optional `reasoning_effort` parameter passed to `llm.chat`; Q&A (U5) keeps its own choice.
B) On (U1 default): about 3x slower and broke the 120 s limit in the probe.
C) A setting, default off.
E) Other

[Answer]: A

### Question 3 - Per-call and job limits for the journal
Today: 120 s per call (`MODEL_CALL_TIMEOUT_S`), 300 s per job (`JOB_TIMEOUT_S`). Run 3 used 99 s in one call for 4 stops.

A) **Journal-specific**: per call 300 s (`JOURNAL_CALL_TIMEOUT_S`), job `min(300 s x number of calls, 1800 s)` (`JOURNAL_JOB_TIMEOUT_PER_CALL_S`, `JOURNAL_JOB_TIMEOUT_CAP_S`), same pattern as U3. Other jobs unchanged.
B) Per call 240 s, job 300 s (one big call only).
C) Keep 120 s / 300 s (most days would time out on this laptop).
E) Other

[Answer]: A

### Question 4 - Speed target (NFR-1.1 says ≤ 90 s)
A) **Measured target on this laptop**: ≤ 120 s for a day with ≤ 5 stops, ≤ 300 s for a day with about 10 stops. Keep the NFR-1.1 goal of 90 s as the stretch target; a miss is recorded in Build and Test with the measured time, as U1 did for NFR-1.
B) Hold 90 s as a hard target (would need a smaller model or GPU).
C) No speed target; only the limits of Question 3.
E) Other

[Answer]: A

### Question 5 - Busy days and the 4,096-token context
A) **Chunk by stops.** Split the day's stops into chunks of ≤ 6 stops or ≤ 4,000 characters of note text, whichever comes first; one model call per chunk writes those stop slots; a last call writes `summary` from the chunk paragraphs (not the raw notes). Each chunk is one trace step group. A day that fits in one chunk stays one call.
B) Cap: refuse days over the limit with a clear message (`journal_day_too_big`).
C) Raise the Ollama context (`OLLAMA_CONTEXT_LENGTH` documented in the README); one call per day. Unverified whether `/v1` accepts a per-request `num_ctx`; larger context also costs speed and VRAM.
D) Accept silent truncation.
E) Other

[Answer]: A

### Question 6 - Grounding check for generated paragraphs
Run 2 cited real trip ids that were never read. FD JR-G1 counts any trip id as known.

A) **Per-run known ids** for generated paragraphs: a citation is supported only if its id was returned in that run's trace (pre-fetch step 0 included; a stop id counts once `list_day_stops` returned it). User-written paragraphs keep the trip-wide check of JR-G1. Changes JR-G1.
B) Keep JR-G1 as in FD (trip-wide ids).
E) Other

[Answer]: A

### Question 7 - Quality smoke check for real drafts
A) **Manual, non-blocking**, in U4 Build and Test: the minimal trip day and one reference-trip day; record per day the unsupported-sentence count, any invented facts, and the time. The prompt is strengthened in Code Generation (one citation per sentence, a short worked example), since run 3 cited only 4 / 14 sentences.
B) Blocking threshold (for example ≤ 20% unsupported sentences) before U4 is complete.
C) No smoke check.
E) Other

[Answer]: A

### Question 8 - Output length
A) **No `max_tokens`**; paragraph length comes from the tone fragment (casual 2-4 sentences, concise 1-2, detailed 4-6). The per-call limit bounds runaway output.
B) `max_tokens=2048` per call.
E) Other

[Answer]: A

### Question 9 - Speed of non-model work
A) **Targets** (not hard tests): journal page render, paragraph edit `PUT` and citation panel each ≤ 300 ms on the reference large trip; checked once in Build and Test.
B) Hard performance tests in the suite.
C) No target.
E) Other

[Answer]: A

### Question 10 - Logging
A) **One INFO line each** for job start / end (day, slots, calls, seconds, outcome), chunk end, paragraph edit and parse drops (count only); never note text, journal text or prompts (U1-NFR-SP).
B) Also log the full trace at DEBUG.
E) Other

[Answer]: A

### Question 11 - When one chunk fails
A) **All or nothing** (JR-F1): any failed call fails the job; nothing is saved; the saved journal stays as it was.
B) Save the chunks that finished, mark the rest as missing.
E) Other

[Answer]: A

### Question 12 - Property-based tests
A) **Reuse the U1 Hypothesis profiles** (`dev`, `ci`) and add generators for days, slot lists, journal text with headings and citations, and owner flags, covering P-1 to P-7; plus a property for the chunk split (every stop in exactly one chunk, order kept, limits kept) if Question 5 = A.
B) Example tests only for U4.
E) Other

[Answer]: A

### Question 13 - New dependencies
A) **None**; U4 uses the existing stack.
E) Other

[Answer]: A

### Question 14 - NFR Design stage for U4
A) **Skip NFR Design**; the few patterns (pre-fetch, chunking, per-run known ids, limits) are written as implementation notes inside `nfr-requirements.md`, as in U3.
B) Run NFR Design.
E) Other

[Answer]: A
