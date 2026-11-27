# U3 Note Organizer - NFR Requirements

**Stage**: Construction - NFR Requirements (plan steps 5 and 7)
**Source**: `aidlc-docs/construction/plans/u3-note-organizer-nfr-requirements-plan.md` (12 answers, all A, owner, 2026-11-27T13:46:37Z), the probe in that plan (`spike_results/organizer-probe-*_20261127.json`), `requirements.md` NFR-1 to NFR-7, U3 Functional Design (`business-rules.md`, `business-logic-model.md`), U1 and U2 `nfr-requirements.md`
**Scope**: the non-functional requirements U3 code must meet. Ids `U3-NFR-<area>.<n>`. U1 and U2 requirements still apply and are not repeated unless U3 changes or adds to them. NFR Design is skipped (Q12 A), so section 9 gives implementation notes for Code Generation. This closes the Functional Design open items NFR-O1 (Q1), NFR-O2 (Q2, Q3) and NFR-O3 (Q6).

---

## 1. Performance

All speed numbers are **targets**, measured in Build and Test on the measured laptop (same rule as U1-NFR-P.1). A miss is recorded with the laptop model, memory, GPU share and timing; it does not block the unit (Q3 A, Q7 A).

| Id | Requirement | Source |
|---|---|---|
| U3-NFR-P.1 | **Thinking off for the organizer call** (`reasoning_effort="none"`). The Q&A and journal agent calls keep thinking on (U1-NFR-M.1 unchanged). Probe: thinking on 342 s or more per 10-note batch; thinking off 116 s. | Q2 A, probe runs 1-6 |
| U3-NFR-P.2 | **Organizer per-call limit: 240 s.** Over it, the call is cancelled and the batch fails with `call_timeout` (OR-V6); the run moves on. The agent loop keeps 120 s (U1-NFR-P.2). No retries (AL-8). | Q3 A |
| U3-NFR-P.3 | Speed target: ≤ 120 s per 10-note batch; so a 10-note day ≤ 2 min and a 30-note day (3 batches) ≤ 6 min. | Q3 A |
| U3-NFR-P.4 | Job limit unchanged: `min(300 s × batches, 1800 s)` (OR-RUN3). A 240 s call fits inside the 300 s per batch. | Q3 A, OR-RUN3 |
| U3-NFR-P.5 | Review actions (Accept, Edit and accept, Reject, Undo, Accept all) have a server-time target of ≤ 300 ms each, including the re-rendered stop region, on one day of the reference large trip (U2-NFR-S.2). They never call the model. | Q7 A, FA-4 |
| U3-NFR-P.6 | **Prompt size**: each note's text is cut to 1,000 characters in the prompt (as TA-7), with a "(truncated)" mark in the prompt only; the stored text is unchanged. A batch closes at 10 notes **or** when its note text passes 6,000 characters, whichever comes first (a single note always fits, being ≤ 1,000). The app sends no `num_ctx` (Ollama default, 4096 on the probe laptop; the probe batch used about 650 prompt tokens). | Q5 A |
| U3-NFR-P.7 | Day page with suggestions: the trip's suggestions are loaded in one query with its notes (business-logic §6); U2-NFR-P.4 (≤ 300 ms per day page) still applies. | business-logic §6, U2-NFR-P.4 |

Probe numbers for reference (one laptop, one run each; Windows 11, 15.7 GB RAM, about 2.3 of 6.0 GB of `qwen3:8b` on GPU):

| Setting | Time per 10-note batch | Valid items |
|---|---|---|
| `json_schema`, thinking on | 342 s, then 2 runs > 600 s | 10 / 10 (the run that finished) |
| `json_schema`, `reasoning_effort="none"` | 116 s | 10 / 10 |

## 2. Scalability

| Id | Requirement | Source |
|---|---|---|
| U3-NFR-S.1 | Single user on one laptop (U1-NFR-S.1). One organize job at a time (409 `model_busy`). | NFR-3.1, OR-RUN4 |
| U3-NFR-S.2 | **Whole-trip runs on large trips are partial by design.** A run organizes as many batches as fit in the job limit (about 15 batches, 150 notes, at the probe speed) and then ends with `job_timeout`; saved batches stay (OR-SAVE3). The summary says "Run again to continue with the remaining N notes." A re-run continues with the notes left (OR-RUN1). | Q4 A |
| U3-NFR-S.3 | The reference for a full run is a normal trip: the minimal sample trip and one day of the reference large trip. The reference large trip is used for the review-action and day-page timing (P.5, P.7), not for a full organize run. | Q4 A |

## 3. Reliability

Resiliency Baseline: opted out. These are the project's own rules.

| Id | Requirement | Source |
|---|---|---|
| U3-NFR-R.1 | Each batch save is one explicit transaction (`BEGIN IMMEDIATE` … `COMMIT`, `ROLLBACK` on error, as U2-NFR-R.1). The "still undecided" check and the write are in the same transaction (FA-3). | OR-SAVE1, FA-3 |
| U3-NFR-R.2 | Each review action and Accept all is one transaction. | business-logic §4 |
| U3-NFR-R.3 | **Ollama lost during a run**: as designed. Each later batch fails fast with `model_error`; no status check between batches. The run ends `failed` if no batch worked, else `succeeded` with warnings; the summary lists the failed batches; a re-run continues with the notes left. | Q9 A, OR-V6, OR-V7 |
| U3-NFR-R.4 | Output format: `response_format` `json_schema` (schema `OrganizerReply`), **no fallback** to `json_object` (a fallback would be a second call, against AL-8). The parser still applies OR-V1..V8, so a reply that ignores the schema fails the batch as `invalid_json`. Probe: Ollama 0.40.18 honours `json_schema` with thinking on and off; thinking text stays out of `content`. | Q1 A, NFR-O1 |
| U3-NFR-R.5 | `<think>` removal (AL-9) still runs on the reply, in case a future Ollama puts thinking back into `content`. | AL-9 |
| U3-NFR-R.6 | If a later Ollama ignores `reasoning_effort="none"`, the slow call ends as `call_timeout` at 240 s (P.2), never a hang. | Q2 A |
| U3-NFR-R.7 | Cancel and job timeout keep saved batches (OR-SAVE3); the running model call is cancelled (U1 JB rules). | OR-SAVE3 |

## 4. Security and privacy

Security Baseline: opted out (skipped). Project rules still apply.

| Id | Requirement | Source |
|---|---|---|
| U3-NFR-SP.1 | Note text goes to the model only inside `<trip_data>`, followed by the data-not-instructions line; the model can only touch notes and stops by batch label (OR-V1, OR-V3). | prompt §5, Q14 A (FD) |
| U3-NFR-SP.2 | All model output and note text is HTML-escaped (Jinja autoescape); never marked safe. | OR-D5 |
| U3-NFR-SP.3 | Edits are validated by a Pydantic model (`extra="forbid"`) and OR-F / OR-S1 before any write. | OR-E4 |
| U3-NFR-SP.4 | SQL uses parameters only. U3 never writes `notes.text` or `notes.stop_id` (OR-R1). | NFR-6.3, OR-R1 |
| U3-NFR-SP.5 | The only network call is to local Ollama (U1-NFR-SP.1). | NFR-2.1 |

## 5. Usability

| Id | Requirement | Source |
|---|---|---|
| U3-NFR-U.1 | Progress text per batch ("Organizing day n of N (date), batch i of I"), through the U1 job poller. | business-logic §2 |
| U3-NFR-U.2 | A partial whole-trip run tells the user how many notes are left and that a re-run continues (S.2). | Q4 A |
| U3-NFR-U.3 | Keyboard use and text ratings as OR-ST3 and OR-D4; error messages with the fixed wording in OR-E1..E6. | NFR-5.1, NFR-5.2 |

## 6. Logging

Same library, output and format as U1 (key=value lines, `job_id` attached by the U1 context variable).

| Id | Requirement | Source |
|---|---|---|
| U3-NFR-L.1 | One INFO line per batch: `trip_id`, `day`, `batch=i/I`, `notes`, `kept`, `dropped`, `not_organized`, `outcome` (`ok`, `empty_reply`, `invalid_json`, `model_error`, `call_timeout`), `duration_ms`. Drop reasons are logged only as codes and counts. | Q8 A |
| U3-NFR-L.2 | One INFO line per run: `trip_id`, `day` (or `all`), `batches`, `ok_batches`, totals of kept / dropped / not organized, `duration_ms`, final job status. | Q8 A |
| U3-NFR-L.3 | One INFO line per review action: `suggestion_id`, `action`, `from`, `to`; Accept all logs `trip_id`, `day` and the count. | Q8 A |
| U3-NFR-L.4 | Never logged: note text, model reply text, dish, tip, edit values. | Q8 A, U1-NFR-L.2 |

## 7. Maintainability

| Id | Requirement | Source |
|---|---|---|
| U3-NFR-M.1 | ruff (lint, format) and mypy strict pass on `trip_journal` and `tests`. | NFR-6.5 |
| U3-NFR-M.2 | One Pydantic model `OrganizerReply` is the source of the JSON schema sent to Ollama (`model_json_schema()`) and of the reply's shape check. | Q11 A |
| U3-NFR-M.3 | The organizer prompt lives in `agent/prompts/organizer.md` with a `prompt_version` stored on every row (OR-SAVE4). | OR-SAVE4 |
| U3-NFR-M.4 | Layers call downward only: pages / api → services → agent, domain, repositories. | NFR-6.3 |

## 8. Testability

| Id | Requirement | Source |
|---|---|---|
| U3-NFR-T.1 | pytest, ≥ 80% line coverage of U3 modules (`agent/organizer.py`, `services/organizer.py`, the `SuggestionRepository` section, `api/notes.py`, `pages/organizer.py`). | unit-of-work DoD, NFR-7.1 |
| U3-NFR-T.2 | Example tests T-O1..T-O10 (business-rules §15) with `FakeLLMClient`; plus: the organizer call sends `reasoning_effort="none"` and the `json_schema` response format (FakeLLMClient records the arguments); the 240 s organizer limit (simulated with a short limit); the 6,000-character batch split and the 1,000-character cut. | Q2 A, Q3 A, Q5 A |
| U3-NFR-T.3 | **PBT reproducibility (PBT-08)**: U1 profiles reused (`default` 100 examples, `ci` 500, `print_blob=True`, `deadline=None`, shrinking on; seed passed in the pre-merge run). P-O4 (`RuleBasedStateMachine`) uses `stateful_step_count=30`. No new profile. | Q10 A |
| U3-NFR-T.4 | **PBT generators (PBT-07)** in the shared `tests/strategies.py`: valid reply items built from the batch's labels and the five categories (optional dish / rating / tip within OR-F limits); mutation strategies (unknown note or stop label, wrong category, rating as string / fraction / out of range, over-long strings, duplicate notes, extra keys, non-object top level); arbitrary JSON values. Status-mix and action-sequence strategies for P-O1, P-O2, P-O4 over several days. | Q10 A |
| U3-NFR-T.5 | **Properties** P-O1..P-O4 (PBT-03, blocking). | business-rules §15 |
| U3-NFR-T.6 | No automated test needs Ollama or network. | NFR-7.2 |
| U3-NFR-T.7 | **Accuracy smoke check (NFR-O3)**: manual and non-blocking, in U3 Build and Test. Run the organizer once on a fixed labelled set (the minimal sample trip plus the 10-note probe day in the plan) and record category and stop accuracy and time per batch. The formal ≥ 85% measurement (FR-11) stays in U6. | Q6 A |

## 9. Implementation notes for Code Generation (NFR Design skipped, Q12 A)

| # | Note | From |
|---|---|---|
| N-1 | `LLMClient.chat` gets an optional `reasoning_effort: str \| None = None`; `OllamaClient` passes it to `chat.completions.create` only when set; `FakeLLMClient` records it. Agent loop calls do not set it. | P.1 |
| N-2 | The organizer wraps its call in `asyncio.timeout(ORGANIZER_CALL_TIMEOUT_S)` with `ORGANIZER_CALL_TIMEOUT_S = 240.0` in `config.py`. **The SDK client's own timeout is 120 s today** (`OllamaClient(timeout_s=MODEL_CALL_TIMEOUT_S)`, the backstop from U1 NFR Design), so the organizer call must also pass a per-request `timeout=` of at least 240 s (or the backstop must be raised); otherwise the SDK ends it at 120 s. | P.2 |
| N-3 | `response_format={"type": "json_schema", "json_schema": {"name": "OrganizerReply", "schema": OrganizerReply.model_json_schema()}}`; no fallback path. | R.4, M.2 |
| N-4 | Batching: per day, in time order, start a new batch at 10 notes or when adding the next note would pass 6,000 characters of (cut) note text. | P.6 |
| N-5 | Batch save and review actions: `BEGIN IMMEDIATE`, repository calls with `commit=False` (U2 IC-2), `commit`; `rollback` on any exception. The save's `UPDATE … WHERE status = 'pending'` / insert-if-absent keeps FA-3 inside the transaction. | R.1, R.2 |
| N-6 | Log lines with `time.perf_counter()` around each batch and the run; fields as L.1-L.3. | L.1-L.3 |
| N-7 | Prompt wording (from the probe): spell out the rating conversion with an example ("8/10" → 4), and say `tip` is a piece of advice found in the note, never the whole note; leave it null otherwise. Use labels in `note` and `stop`. | probe run 6 |

## 10. Changes to Functional Design and U1

| Rule | Change | Source |
|---|---|---|
| OR-RUN2 | A batch also closes when its note text passes 6,000 characters; note text is cut to 1,000 characters in the prompt | Q5 A |
| OR-RUN3 / AL-8 | Organizer per-call limit is 240 s (agent loop stays 120 s) | Q3 A |
| business-logic §3 step 3 | `json_schema` only; the open `json_object` fallback (NFR-O1) is dropped | Q1 A |
| U1-NFR-M.1 | Thinking stays on for agent calls; the organizer sends `reasoning_effort="none"` | Q2 A |
| C10 `LLMClient` | New optional `reasoning_effort` argument (N-1) | Q2 A |
| business-rules §13 | NFR-O1..O3 closed (Q1, Q2 + Q3, Q6) | this stage |

## 11. Extension compliance

| Extension / rule | Status | Note |
|---|---|---|
| Security Baseline | N/A (opted out) | Skipped per `aidlc-state.md` |
| Resiliency Baseline | N/A (opted out) | Skipped per `aidlc-state.md` |
| PBT-09 framework selection (blocking) | Compliant | Hypothesis, decided in U1 and reused |
| PBT-07 generator quality (blocking) | Compliant at requirements level | Generators specified in T.4; built and checked at Code Generation |
| PBT-08 shrinking and reproducibility (blocking) | Compliant at requirements level | T.3 |
| PBT-02 (blocking) | N/A | U3 has no serialize / parse round trip of its own; the reply parser is one-way (covered by P-O3 under PBT-03) |
| PBT-03 (blocking) | N/A at this stage | P-O1..P-O4 listed in T.5; implemented at Code Generation |
| Other PBT rules (advisory) | N/A at this stage | |
