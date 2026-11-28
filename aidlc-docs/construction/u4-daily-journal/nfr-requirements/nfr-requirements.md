# U4 Daily Journal - NFR Requirements

**Stage**: Construction - NFR Requirements (plan steps 5 and 7)
**Source**: `aidlc-docs/construction/plans/u4-daily-journal-nfr-requirements-plan.md` (14 answers, all A, owner, 2026-11-28T00:08:56Z) and the journal probe in that plan; `requirements.md` NFR-1 to NFR-7; U4 Functional Design (`business-logic-model.md`, `business-rules.md`, `domain-entities.md`); U1 and U3 `nfr-requirements.md`
**Scope**: the non-functional requirements U4 code must meet. Ids `U4-NFR-<area>.<n>`. U1-U3 requirements still apply and are not repeated unless U4 changes them. NFR Design is skipped (Q14 A), so section 9 gives implementation notes for Code Generation and section 10 lists the Functional Design changes (BL-2, BL-6, JR-G1 and others).

---

## 1. Performance

Speed numbers are **targets**, measured in Build and Test on the measured laptop (U1-NFR-P.1 rule). A miss is recorded with laptop, memory, GPU share and time; it does not block the unit (Q4 A, Q9 A).

| Id | Requirement | Source |
|---|---|---|
| U4-NFR-P.1 | **Thinking off for journal calls** (`reasoning_effort="none"`), passed through a new optional `AgentLoop` parameter. Q&A (U5) chooses its own setting. Probe: thinking on 359 s with both steps over the old 120 s limit; thinking off with pre-fetch 99 s. | Q2 A, probe runs 2, 3 |
| U4-NFR-P.2 | **Journal per-call limit: 300 s** (`JOURNAL_CALL_TIMEOUT_S`). Over it, the call is cancelled and the job fails with `model_timeout`; no retry (JR-F4). Other agent calls keep 120 s. | Q3 A |
| U4-NFR-P.3 | **Journal job limit: `min(300 s × planned calls, 1800 s)`** (`JOURNAL_JOB_TIMEOUT_PER_CALL_S = 300`, `JOURNAL_JOB_TIMEOUT_CAP_S = 1800`). Planned calls = number of chunks, plus 1 for the summary call when there are 2 or more chunks (P.5). Other jobs keep 300 s. | Q3 A |
| U4-NFR-P.4 | **Speed target** on the measured laptop: ≤ 120 s for a day with ≤ 5 stops; ≤ 300 s for a day with about 10 stops (2 chunks + summary). **Stretch target**: NFR-1.1 ≤ 90 s, kept; a miss is recorded in Build and Test with the measured time, as U1 did for NFR-1. | Q4 A |
| U4-NFR-P.5 | **Chunking for the 4,096-token context.** The day's stops (timeline order) are split into chunks of ≤ 6 stops **or** ≤ 4,000 characters of note text (as returned by the tools, TA-7 cut included), whichever is reached first; a stop is never split, so one stop over 4,000 characters forms a chunk of its own. One agent run per chunk writes that chunk's stop slots. With 2 or more chunks, a last call writes `summary` from this run's chunk paragraphs plus the stored paragraphs of the other slots (not the raw notes). A day that fits in one chunk is one run that writes all its slots, `summary` included. No `num_ctx` is sent (Ollama default; 4,096 on this laptop). | Q5 A |
| U4-NFR-P.6 | **No `max_tokens`**; length comes from the tone fragment (casual 2-4 sentences, concise 1-2, detailed 4-6). The per-call limit bounds runaway output. | Q8 A |
| U4-NFR-P.7 | Non-model work: journal page render, paragraph edit `PUT` (re-check included) and citation panel each ≤ 300 ms server time on one day of the reference large trip (U2-NFR-S.2); checked once in Build and Test, not a test in the suite. | Q9 A |
| U4-NFR-P.8 | Pre-fetch (step 0) is database work only and uses no model step; it counts inside the job limit. | Q1 A |

Probe numbers (one laptop, one run each; Windows 11, 15.7 GB RAM, Ollama 0.40.18, `qwen3:8b` Q4_K_M, about 2.3 of 6.0 GB on GPU; minimal trip day, 4 stops, 5 slots):

| Run | Setting | Total | Grounded | Sentences cited |
|---|---|---|---|---|
| 1 | agent, thinking off | 119 s | No (notes never read) | 4 / 15 |
| 2 | agent, thinking on | 359 s | No (fabricated real ids) | 14 / 14 |
| 3 | pre-fetch, thinking off | 99 s | Mostly | 4 / 14 |

## 2. Scalability

| Id | Requirement | Source |
|---|---|---|
| U4-NFR-S.1 | Single user on one laptop (U1-NFR-S.1). One model job at a time (409 `model_busy`, JR-P4). | NFR-3.1 |
| U4-NFR-S.2 | Busiest day of the reference large trip (22 stops, 115 notes, about 8,400 characters of note text): at least 4 chunks by stop count, so 5 planned calls, job limit 1,500 s. A day that needs more than 6 calls hits the 1,800 s cap; such a day ends `job_timeout` with nothing saved (R.2). Recorded as a known limit; not expected on normal trips. | Q3 A, Q5 A |

## 3. Reliability

Resiliency Baseline: opted out. Project rules.

| Id | Requirement | Source |
|---|---|---|
| U4-NFR-R.1 | The save step stays one `BEGIN IMMEDIATE` transaction with the `WHERE owner = 'generated'` guard (JR-S1); chunking does not add save steps: all chunk results are merged into one `JournalDraft` and saved once. | BL-4, Q11 A |
| U4-NFR-R.2 | **All or nothing** (JR-F1): any failed chunk or summary call (timeout, model error, step limit, no paragraph) fails the whole job; nothing is saved; the saved journal and its trace stay as they were (JR-F2). | Q11 A |
| U4-NFR-R.3 | JR-R3 applies to the whole run: it succeeds if at least one requested slot has text across all chunks. A chunk that writes none of its slots is not a failure by itself; its slots are `missing` (JR-R4). | Q11 A, JR-R3 |
| U4-NFR-R.4 | If a later Ollama ignores `reasoning_effort="none"`, a slow call ends as `model_timeout` at 300 s (P.2), never a hang. | Q2 A |
| U4-NFR-R.5 | `<think>` removal (AL-9) still runs on every reply. | AL-9 |
| U4-NFR-R.6 | Cancel and job timeout cancel the running call; nothing is saved (U1 JB rules, R.2). | U1, Q11 A |

## 4. Security and privacy

Security Baseline: opted out. Project rules still apply.

| Id | Requirement | Source |
|---|---|---|
| U4-NFR-SP.1 | Pre-fetched records enter the history as tool-result messages built by the same `wrap_tool_result` as real tool calls, so the data-not-instructions block (`_shared_tool_data.md`) covers them. | Q1 A |
| U4-NFR-SP.2 | Journal text, model output and user text are HTML-escaped (Jinja autoescape); citations are rendered from escaped text; never marked safe. | NFR-2, U1-NFR-SP |
| U4-NFR-SP.3 | Edit bodies validated by Pydantic (`extra="forbid"`) and JR-V1..V3 before any write; SQL uses parameters only. | JR-V, NFR-6.3 |
| U4-NFR-SP.4 | The only network call is to local Ollama (U1-NFR-SP.1). | NFR-2.1 |

## 5. Grounding

| Id | Requirement | Source |
|---|---|---|
| U4-NFR-G.1 | **Per-run known ids for generated paragraphs**: a citation in a generated paragraph is supported only if its id is in the `returned_ids` of the stored trace of the last successful generation (step 0 included; a stop id counts once `list_day_stops` returned it). User paragraphs keep the trip-wide check. Still computed on read, never stored (JR-G3). | Q6 A |
| U4-NFR-G.2 | Step 0 always covers **all** stops of the day (not only the slots to write), so a regenerate's trace also holds the ids that kept generated paragraphs and the summary may cite. | Q1 A, Q6 A |
| U4-NFR-G.3 | **Quality smoke check**: manual, non-blocking, in U4 Build and Test, on the minimal trip day and one reference-trip day; record per day the unsupported-sentence count, invented facts found, and the time. | Q7 A |
| U4-NFR-G.4 | Prompt strengthened in Code Generation: one citation per sentence with a fact, and a short worked example (probe run 3 cited 4 / 14). | Q7 A |

## 6. Usability and logging

| Id | Requirement | Source |
|---|---|---|
| U4-NFR-U.1 | Progress text: "Loading the day's records…" (step 0); with chunks, "Part i of n, step k of 8: <tool>" and "Part i of n: writing…"; "Writing the summary…"; "Saving…". One chunk keeps the BL-9 text. | BL-9, Q5 A |
| U4-NFR-L.1 | INFO lines (key=value, U1 format, `job_id` attached): job start (`trip_id`, `day`, `slots`, `chunks`, `planned_calls`, `tone`); chunk end (`chunk=i/n`, `stops`, `slots_written`, `steps`, `duration_ms`, `outcome`); job end (`slots_written`, `missing`, `calls`, `duration_ms`, `outcome`); paragraph edit (`slot`, `changed`); parse drops (count per reason only). | Q10 A |
| U4-NFR-L.2 | Never logged: note text, journal text, prompts, model replies, edit text (U1-NFR-L.2). | Q10 A |

## 7. Maintainability

| Id | Requirement | Source |
|---|---|---|
| U4-NFR-M.1 | ruff (lint, format) and mypy strict pass on `trip_journal` and `tests`. | NFR-6.5 |
| U4-NFR-M.2 | Prompt in `agent/prompts/journal.md` (+ 3 tone fragments, + a summary-call prompt section) with `prompt_version` stored on the journal row. | BL-6 |
| U4-NFR-M.3 | Chunk split is a pure function (`chunk_stops`) in `agent/journal.py`, separate from I/O, so it is property-tested. | Q12 A |
| U4-NFR-M.4 | No new runtime or dev dependency (Q13 A); layers call downward only (NFR-6.3). | Q13 A |

## 8. Testability

| Id | Requirement | Source |
|---|---|---|
| U4-NFR-T.1 | pytest, ≥ 80% line coverage of U4 modules (`agent/journal.py`, `services/journal.py`, `JournalRepository`, journal API and page routes). | DoD, NFR-7.1 |
| U4-NFR-T.2 | Example tests from business-rules (FakeLLM full draft, step-limit failure, 3 regenerate cases, edit before / after save, tone prompts), plus: journal calls send `reasoning_effort="none"` and `timeout_s=300` (FakeLLMClient records both); step 0 trace records for every stop; a 2-chunk day with summary call; a failing second chunk saves nothing; per-run grounding (an id from the trip but not the trace is unsupported in a generated paragraph and supported in a user paragraph); job limit computed from planned calls. | Q1-Q6, Q11 |
| U4-NFR-T.3 | **PBT-08**: U1 profiles reused (`default` 100 examples, `ci` 500, `print_blob=True`, `deadline=None`, shrinking on). No new profile. | Q12 A |
| U4-NFR-T.4 | **PBT-07** generators in `tests/strategies.py`: days with 0-25 stops and random note lengths; slot lists and owner flags; journal text with `##` headings (valid, junk, duplicate, spaced) and citations; draft mappings. | Q12 A |
| U4-NFR-T.5 | **PBT-03** properties P-1..P-7 (business-rules) plus **P-8 chunk split**: every stop in exactly one chunk, timeline order kept, each chunk ≤ 6 stops, each chunk ≤ 4,000 note characters unless it holds a single stop. | Q12 A |
| U4-NFR-T.6 | No automated test needs Ollama or network (NFR-7.2). | NFR-7.2 |

## 9. Implementation notes for Code Generation (NFR Design skipped, Q14 A)

| # | Note | From |
|---|---|---|
| N-1 | **Pre-fetch step 0** (`JournalAgent`): call `registry.execute(ToolCall(name="list_day_stops", arguments={"day": ...}), context)` and then `get_stop_notes` for each returned stop, through the same registry path as model calls (validation, `wrap_tool_result`, `returned_ids`). Record each as a `ToolCallRecord` with `step=0`. Build the history as an assistant message with synthetic `tool_calls` (ids `prefetch-<n>`) followed by one `tool` message per result, so the model sees normal tool results. A chunk's history holds `list_day_stops` plus only that chunk's `get_stop_notes` results; the trace holds all of them once. | Q1 A, G.2 |
| N-2 | **AgentLoop changes**: new optional `reasoning_effort: str \| None = None` and the existing `call_timeout_s`; `_call` passes both `reasoning_effort` and `timeout_s=self.call_timeout_s` to `llm.chat`. **The SDK client's backstop is 120 s** (`OllamaClient(timeout_s=MODEL_CALL_TIMEOUT_S)`), so without the per-request `timeout_s` the SDK would end a journal call at 120 s (same trap as U3 N-2). `run` accepts initial history messages (the step-0 block). Default behaviour for other callers unchanged. | Q2 A, Q3 A |
| N-3 | **Chunking**: `chunk_stops(stops_with_note_chars, max_stops=6, max_chars=4000) -> list[list[stop_id]]`, greedy in timeline order; close a chunk when adding the next stop would pass either limit. Only stops whose slot is in `todo` need a chunk; a chunk whose stops are all user-owned is not run. `summary` is written in the single run when there is one chunk, else by the summary call. Config constants `JOURNAL_CHUNK_MAX_STOPS`, `JOURNAL_CHUNK_MAX_CHARS`. | Q5 A |
| N-4 | **Summary call**: user message holds this run's chunk paragraphs (with their citations) and the stored paragraphs of other slots as data; tools stay available; it writes only `## summary`. Its parse uses `requested={summary}`. | Q5 A |
| N-5 | **Per-run known ids** (`JournalService.get_journal`): `run_ids` = union of `returned_ids` over the stored trace; generated paragraphs check against `run_ids`, user paragraphs against trip ids (`check_text` called with the right set per paragraph). | Q6 A |
| N-6 | **Limits** in `config.py`: `JOURNAL_CALL_TIMEOUT_S = 300.0`, `JOURNAL_JOB_TIMEOUT_PER_CALL_S = 300.0`, `JOURNAL_JOB_TIMEOUT_CAP_S = 1800.0`; the service computes the job limit from the chunk plan before submitting (as U3 does per batch). | Q3 A |
| N-7 | **One draft, one save**: chunk drafts are merged into one `JournalDraft` (slots union, dropped list, trace = step 0 + all chunk steps in order) before BL-4. | R.1 |
| N-8 | **Prompt** (BL-6 tool plan replaced): "The day's records are already loaded above. Use `find_photos`, `search_notes` or `lookup_place` only if you need photos or other records. Answer in your first reply if you can." Add the per-sentence citation rule with a two-sentence worked example. | Q1 A, Q7 A |
| N-9 | Timing with `time.perf_counter()` around step 0, each chunk, the summary call and the job; fields as L.1. | L.1 |

## 10. Changes to Functional Design and U1

| Rule | Change | Source |
|---|---|---|
| BL-2 | Agent run becomes: step 0 pre-fetch (N-1), then one `AgentLoop` run per chunk (N-3) and a summary call when chunked (N-4), thinking off, per-call 300 s; the "per call 120 s, job 300 s" line is replaced by P.2 / P.3 | Q1, Q2, Q3, Q5 |
| BL-6 | Tool plan row replaced: records are pre-loaded, tools only for photos or other days (N-8); citation rule strengthened with an example (G.4); summary-call section added | Q1 A, Q7 A |
| BL-9 | Progress texts for step 0, parts and summary (U.1) | Q5 A |
| JR-G1 | Known ids: trip-wide for **user** paragraphs; per-run trace ids for **generated** paragraphs (G.1) | Q6 A |
| JR-F1 / JR-R3 | Apply to the whole chunked run: any failed call fails the job; success needs one written slot across all chunks (R.2, R.3) | Q11 A |
| JR-TR1 | Trace shows step 0 records ("loaded by the app") and chunk / summary step groups | Q1 A, Q5 A |
| U1 C10 `AgentLoop` | Optional `reasoning_effort`, per-request `timeout_s`, initial history (N-2) | Q2, Q3 |
| Testable properties | P-8 chunk split added (T.5) | Q12 A |

**Open item for the owner (not blocking)**: step 0 loads only stop notes. Notes without a stop (JR-SL2, the probe's tram 28 note) reach the model only if it calls `search_notes` itself, which the probe suggests it rarely does. They are not in the summary's records by default. Can be added later as a `search_notes`-by-day pre-fetch if Build and Test shows the gap matters.

## 11. Extension compliance

| Extension / rule | Status | Note |
|---|---|---|
| Security Baseline | N/A (opted out) | per `aidlc-state.md` |
| Resiliency Baseline | N/A (opted out) | per `aidlc-state.md` |
| PBT-09 framework selection (blocking) | Compliant | Hypothesis, decided in U1, reused |
| PBT-07 generator quality (blocking) | Compliant at requirements level | T.4; built at Code Generation |
| PBT-08 shrinking and reproducibility (blocking) | Compliant at requirements level | T.3 |
| PBT-02 round trip (blocking) | N/A at this stage | Journal text is parsed one way (`parse_journal_output`); `trace_json` uses Pydantic dump / validate, its round trip is tested at Code Generation if a custom serializer is added |
| PBT-03 invariants (blocking) | N/A at this stage | P-1..P-8 listed in T.5; implemented at Code Generation |
| Other PBT rules (advisory) | N/A at this stage | |
