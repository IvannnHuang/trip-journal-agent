# U4 Daily Journal - Business Rules

> **Summary**: the rules for slots, ownership, merge, parsing, failure, concurrency, grounding, validation, errors and UI behavior of the day journal, plus the testable properties for PBT. Each rule has an id used by tests and code comments. Source column: plan question (Q1-Q24, all answered A on 2026-11-27) or requirement / story id.

## Slots (JR-SL)

| ID | Rule | Source |
|---|---|---|
| JR-SL1 | Slots of a day are `summary` then `stop:<id>` for every stop of the day in timeline order, including stops with no notes | Q2 |
| JR-SL2 | Notes without a stop are not given a slot; they may be cited in the summary | Q2 |
| JR-SL3 | Positions in `journal_paragraphs` follow `slot_order`; the stored order is rewritten on each save step | Q2, Q24 |

## Ownership (JR-O)

| ID | Rule | Source |
|---|---|---|
| JR-O1 | A save changes the owner to `user` only when the submitted text differs exactly (byte for byte, no trimming) from the stored text | Q5 |
| JR-O2 | Text and owner change in the same transaction; an unchanged save writes nothing | Q5, Q11 |
| JR-O3 | A user-owned paragraph stays user-owned for good, also when cleared; there is no "give back to the agent" action | Q3 |
| JR-O4 | A cleared user paragraph is "removed": hidden in the reading view, shown as "Removed by you" with an Edit button in the editor | Q4 |
| JR-O5 | Citations typed by the user are stored as typed; unknown ones are flagged at read time, not rejected | Q5, Q14 |

## Merge (JR-M) - `merge_journal`

| ID | Rule | Source |
|---|---|---|
| JR-M1 | Output paragraphs are exactly `slot_order`, in order, each once | Q24, US-13 |
| JR-M2 | A user-owned paragraph is output byte-identical, whatever the draft holds | FR-6.2, US-13 |
| JR-M3 | A generated slot takes the draft text when present; otherwise it keeps its old text (or `""` when it had none) | Q9, Q24 |
| JR-M4 | `nothing_to_regenerate` is true exactly when every slot in `slot_order` is user-owned | Q12, Q24 |
| JR-M5 | Merging the same draft twice gives the same result as merging it once | Q24 |
| JR-M6 | Precondition: every existing slot is in `slot_order` | Q24 |

## Parse (JR-R) - agent output to slots

| ID | Rule | Source |
|---|---|---|
| JR-R1 | Output is plain text with one `## <slot>` heading per slot; headings are compared after lower-casing and removing spaces | Q6 |
| JR-R2 | Duplicate heading: the first wins; unknown, user-owned and not-requested headings are dropped and logged (heading and reason only) | Q9 |
| JR-R3 | The run succeeds only if at least one requested slot has non-empty text | Q9 |
| JR-R4 | A requested slot left out: first draft stores it as empty generated ("Not written yet"); regenerate keeps its previous text; the view message says "The agent did not write N paragraphs; regenerate to try again." | Q9 |

## Run, pre-checks and failure (JR-P, JR-F)

| ID | Rule | Source |
|---|---|---|
| JR-P1 | Every slot user-owned → 200 with "Nothing to regenerate: every paragraph is yours."; no job starts | Q12 |
| JR-P2 | No stops and no notes on the day → Write journal disabled, "No records for this day." | Q12 |
| JR-P3 | Model not ready → the U1 model-status message (503) | Q12, FR-8 |
| JR-P4 | Another job running → 409 (`ModelBusyError`) | Q12, U1 |
| JR-P5 | `slots_to_write` = generated slots + slots with no row; user-owned text is sent as read-only context | Q8 |
| JR-F1 | Step limit, timeout, model error or JR-R3 failure: the saved journal is untouched; the job shows a clear message and the trace so far | Q10, NFR-4.3 |
| JR-F2 | A failed run's trace is not saved; "How this was made" keeps the last successful generation | Q10, Q17 |
| JR-F3 | A tool error inside a run goes back to the model; if the run still yields a valid draft, it is saved, the trace keeps the error, and the page says "N tool call(s) failed; see How this was made" | Q10 |
| JR-F4 | No automatic retry; the user retries with Regenerate | U1, NFR-4.3 |

## Concurrency (JR-S)

| ID | Rule | Source |
|---|---|---|
| JR-S1 | The save step is one `BEGIN IMMEDIATE` transaction that re-reads owners and updates only rows `WHERE owner = 'generated'` | Q11 |
| JR-S2 | An edit committed before the save step survives it; an edit after the save step overwrites the generated text as a normal edit | Q11 |
| JR-S3 | Editing is allowed while a job runs; the page shows "Generating… your edits are kept." | Q11 |
| JR-S4 | The draft swap skips any paragraph whose editor is open or has unsaved text | Q11 |
| JR-S5 | Leaving the editor (blur, `visibilitychange` to hidden) sends the pending autosave at once | Q11 |

## Grounding (JR-G)

| ID | Rule | Source |
|---|---|---|
| JR-G1 | Known ids = every stop, note and photo of the active trip | Q14 |
| JR-G2 | All paragraphs are checked, generated and user; `unsupported_count` covers all of them | Q14, US-11 |
| JR-G3 | Grounding is computed on read and never stored | Q15 |
| JR-G4 | An unsupported sentence is shown with `<mark>`, a warning icon, visually-hidden text "unsupported" and a dotted underline; the count line links to the first one | Q19, NFR-5 |

## Validation and errors (JR-V, JR-E, JR-C)

| ID | Rule | Source |
|---|---|---|
| JR-V1 | Edit slot must be in the day's `slot_order` and the journal must exist, else 404 | Q20 |
| JR-V2 | Edit text at most 5,000 characters, else 422 "Paragraph is too long (max 5000 characters)." (limit set in Functional Design; adjustable) | BL-5 |
| JR-V3 | Tone must be one of casual, concise, detailed, else 422 | Q13 |
| JR-E1 | Unknown trip or day → 404 with the U1 `NotFoundError` code | Q20 |
| JR-E2 | Error bodies follow the U1 JSON shape for `/api/...` and the U1 error fragment for page routes | U1 |
| JR-C1 | Citation lookup outside the active trip → panel text "Record not found in this trip." (200 fragment) | Q16 |
| JR-C2 | Escape or Close hides the citation panel and returns focus to its citation button | Q16, Q21 |

## Tone, trace and UI (JR-T, JR-TR, JR-UI)

| ID | Rule | Source |
|---|---|---|
| JR-T1 | Tone picker defaults to the journal's stored tone, else casual; the chosen tone is stored on the journal row at the save step | Q13 |
| JR-T2 | Prompt = base `journal.md` + `journal_tone_<tone>.md` fragment, composed by JournalAgent | Q13 |
| JR-TR1 | "How this was made" is a collapsed `<details>`: each tool call's name, arguments, returned ids or error kind and message; tone, model, prompt version, generation time | Q17, US-20 |
| JR-UI1 | Autosave: `input changed delay:1s, blur`; status Saved / Saving… / "Not saved: <reason>" | Q18 |
| JR-UI2 | Focus: after save stays in the textarea; after Done goes to that paragraph's Edit button; after generation goes to the draft heading; after closing a citation goes back to the citation | Q21 |
| JR-UI3 | A finished draft swaps in automatically and is announced "Draft ready" in an `aria-live="polite"` region | Q22 |
| JR-UI4 | Timeline day header links to the journal page with a "drafted" or "not written" badge | Q20 |

## U3 carry-ins (JR-CI)

| ID | Rule | Source |
|---|---|---|
| JR-CI1 | Organizer prompt: tip is a short phrase from the note, empty if none; rating examples "8/10" → 4, "9/10" → 5; FakeLLM regression tests; 18-note smoke re-run in U4 Build and Test | Q23 |
| JR-CI2 | U3 review rows: after a row swap, focus goes to the next pending row or the stop heading | Q21 |

## Testable properties (PBT-01, for PBT-03)

Generators: `slot_order` from 0-8 distinct stop ids; `existing` = a subset of the order with random owners and texts (any Unicode, including `""` and leading spaces); `draft` = a random mapping over the order plus junk slots filtered by the caller.

| ID | Property | Rule |
|---|---|---|
| P-1 | User paragraphs in `existing` are byte-identical in the output, same slot | JR-M2 |
| P-2 | Output slots equal `slot_order`, same order, no repeats | JR-M1 |
| P-3 | Generated slot: draft text if the draft has it, else old text, else `""` | JR-M3 |
| P-4 | `nothing_to_regenerate` ⇔ every slot user-owned | JR-M4 |
| P-5 | `merge(merge(e, d).paragraphs, d) == merge(e, d)` (idempotent) | JR-M5 |
| P-6 | `mark_user_edit`: only the edited slot changes; it becomes `user` only when the text differs exactly; other paragraphs equal | JR-O1 |
| P-7 | `parse_journal_output` never returns a user-owned or not-requested slot, and never two entries for one slot | JR-R2 |

Example tests (not PBT): `slot_order` with 0 and 3 stops; FakeLLM full draft for an 8-stop day in 3 steps (Q7); FakeLLM step-limit failure leaves the stored journal untouched; three regenerate cases (all generated, mixed, all user); edit just before and just after the save step; tone prompt assembly for each tone.
