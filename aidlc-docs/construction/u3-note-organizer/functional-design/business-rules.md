# U3 Note Organizer - Business Rules

**Stage**: Functional Design (U3). The owner answered A to all 21 questions on 2026-11-27.
**Rule ids**:

| Prefix | Area |
|---|---|
| OR-RUN | running |
| OR-SAVE | saving |
| OR-V | validating model output |
| OR-F | fields |
| OR-S | stops |
| OR-ST | review states |
| OR-AA | accept all |
| OR-R | raw data |
| OR-D | display |
| OR-E | errors |
| CI | carry-ins |

---

## 1. Running the organizer

| Id | Rule | Source |
|---|---|---|
| OR-RUN0 | The organizer runs only when the user asks, for one day or for the whole trip. Import never runs it. | FR-3.1, US-06 S5 |
| OR-RUN1 | Notes with a decided suggestion (`accepted`, `edited`, `rejected`) are not sent again. Notes with no row or a `pending` row are sent. | Q2 A |
| OR-RUN2 | A note belongs to the day given by DD-3. A day's notes are sent in time order, in batches of at most 10. Each batch carries all of that day's stops. | Q6 A |
| OR-RUN3 | Job time limit = `min(300 s × batches, 1800 s)`. The per-call limit stays 120 s (U1). There are no retries. | Q7 A, U1 AL-8 |
| OR-RUN4 | The run is one `organize` job. While any job runs, a second start gets 409 `model_busy` (U1). | U1 JB rules |
| OR-RUN5 | When there is nothing to send, no job starts. The user sees "Nothing to organize". | FA-2 |
| OR-RUN6 | The model must be ready, otherwise 503 `model_unavailable` with the U1 message and action. | U1 |

## 2. Saving

| Id | Rule | Source |
|---|---|---|
| OR-SAVE1 | Each batch is saved in its own transaction as soon as it returns. A save only writes notes that are still undecided at save time. A pending row is replaced, and a note with no row gets a new one. | Q6 A, FA-3 |
| OR-SAVE2 | A note that got no valid item in this run keeps whatever it had (no row, or its old pending row). | Q10 A |
| OR-SAVE3 | Saved batches stay after a later batch failure, a job timeout or a cancel. | Q7 A |
| OR-SAVE4 | Each row stores `prompt_version` and `model_name`. | evaluation (FR-11) |

## 3. Validating model output (per batch, then per item)

| Id | Rule | Result | Source |
|---|---|---|---|
| OR-V1 | `note` must be a label in this batch | dropped: `unknown note label 'n14'` | Q9 A, Q10 A |
| OR-V2 | `category` must be one of the five values (exact, lower case) | dropped: `category 'drink' not allowed` | Q10 A |
| OR-V3 | `stop` must be null or a stop label in this batch | dropped: `unknown stop label 's9'` | Q5 A, Q10 A |
| OR-V4 | Fields must pass OR-F1..F4 | dropped with the field's reason | Q10 A |
| OR-V5 | A second item for the same note | dropped: `duplicate` (the first one is kept) | Q10 A |
| OR-V6 | Batch failure: an empty reply after AL-9, JSON that does not parse, a top level that is not `{"suggestions": [...]}`, a model error or a call timeout | every note in the batch is listed as "not organized" with the reason `empty_reply`, `invalid_json`, `model_error` or `call_timeout` | Q10 A |
| OR-V7 | The job is `succeeded` (with warnings) if at least one batch worked, and `failed` (`model_error`) if none did | | Q10 A |
| OR-V8 | Extra keys in an item or at the top level are ignored | | robustness |

## 4. Fields (model output and edits)

| Id | Rule | Source |
|---|---|---|
| OR-F1 | `dish`, `rating` and `tip` are optional for every category. They are filled only when the note contains them. | Q11 A, US-06 S1 |
| OR-F2 | Strings are trimmed. An empty string becomes none. `dish` ≤ 80 characters, `tip` ≤ 200 characters. | Q11 A |
| OR-F3 | `rating` is a whole number from 1 to 5. A JSON number with no fraction (`4.0`) is accepted. Strings, fractions and out-of-range values are invalid. | Q11 A, Q12 A, FA-5 |
| OR-F4 | `category` is one of the five English values. `dish` and `tip` are asked for in English. The dish may keep an original-language quote of up to 30 characters; this is a prompt rule only, and the app checks just the length limit. | FR-3.5, Q13 A |

## 5. Stops

| Id | Rule | Source |
|---|---|---|
| OR-S1 | A suggested or edited stop must be one of the note's day's stops, or none. An edit naming another stop returns 422 `invalid_edit` on `stop_id`. | Q5 A |
| OR-S2 | The display stop of a note is the effective stop of its `accepted` / `edited` row, otherwise the import `notes.stop_id`. None means "Notes not linked to a stop". | Q4 A |
| OR-S3 | After an Undo or a reject, the note goes back to its import stop. | Q4 A, FA-7 |

## 6. Review states (OR-ST)

| From → To | Action | Allowed |
|---|---|---|
| pending → accepted | Accept | yes |
| pending → edited | Edit, then Save and accept | yes (edit only from pending; to change a decided row, use Undo first, FA-8) |
| pending → rejected | Reject | yes |
| accepted / edited / rejected → pending | Undo (restores the model values, clears `f_*`) | yes (Q3 A) |
| pending → pending | Re-run replaces the model values | yes (OR-RUN1) |
| any other | | 409 `suggestion_state` |

| Id | Rule | Source |
|---|---|---|
| OR-ST1 | A note has at most one suggestion row, and so at most one decision. | FA-1 |
| OR-ST2 | A decision is lost only through Undo, a trip delete or a note delete (cascade). | Q2 A, Q3 A |
| OR-ST3 | All controls are real buttons and form fields, reachable with Tab and run with Enter or Space. In the edit form, Esc cancels. | US-07 rule, NFR-5.1 |

## 7. Accept all

| Id | Rule | Source |
|---|---|---|
| OR-AA1 | Accept all for a day sets that day's `pending` rows to `accepted` with the model values. `edited`, `rejected` and `accepted` rows and other days are not touched. | US-08, Q17 A |
| OR-AA2 | There is no confirmation dialog. The response shows "N suggestions accepted". The button is disabled when the day has no pending row. | Q17 A |
| OR-AA3 | Accepted rows can still be undone one by one. | Q3 A |

## 8. Raw data

| Id | Rule | Source |
|---|---|---|
| OR-R1 | U3 never writes `notes.text` or `notes.stop_id`. `SuggestionRepository` has no method that touches `notes`. | FR-3.4, US-07 rule |
| OR-R2 | Day derivation is unchanged by organizing, so no day is added or removed. | DD rules (U2) |

## 9. Display

| Id | Rule | Source |
|---|---|---|
| OR-D1 | An `accepted` / `edited` note shows its raw text, then one line: category tag · `Dish: …` · `Rating: n / 5` · `Tip: …`, with only the fields that are set. An "edited" mark is shown when edited. | US-05, Q18 A |
| OR-D2 | A `pending` note shows its raw text, then a dashed box labelled "Suggestion – not saved" with the suggested values and the Accept / Edit / Reject buttons. | Q18 A |
| OR-D3 | A `rejected` note shows its raw text and a small "Suggestion rejected" line with Undo. A never-organized note shows only its raw text. | US-05 S2, Q3 A |
| OR-D4 | Ratings are text ("4 / 5"), never only icons. | US-05 rule |
| OR-D5 | All note and model text is HTML-escaped (Jinja autoescape, as U2 TL-8). | U2 |

## 10. Errors

| Id | Case | HTTP / code |
|---|---|---|
| OR-E1 | Unknown trip / day | 404 `trip_not_found` / `day_not_found` (U2) |
| OR-E2 | Unknown suggestion | 404 `suggestion_not_found` |
| OR-E3 | Action not allowed from the current status | 409 `suggestion_state`, with the message "This suggestion was already {status}. Undo it first." |
| OR-E4 | Invalid edit | 422 `invalid_edit`, with `{field: message}` |
| OR-E5 | Model not ready / another job running | 503 `model_unavailable` / 409 `model_busy` (U1) |
| OR-E6 | Trip delete while organizing | 409 `job_running` (U2) |

## 11. Carry-ins from U2

| Id | Rule | Source |
|---|---|---|
| CI-1 (TL-5) | Each photo line on the day page shows the local time, then the coordinates to 4 decimals (`38.7118, -9.1301`) or "no location", then the file name. It is done in U3 Code Generation with a test. | Q20 A |
| CI-2 (nit) | The trip list says "1 day" for one day and "n days" otherwise. It is done in U3 Code Generation with a test. | Q21 A |

## 12. Open assumptions (from the answers; confirm in review)

| Id | Assumption |
|---|---|
| FA-1 | There is one suggestion row per note (UNIQUE `note_id`). This follows from Q2 A and Q3 A. |
| FA-2 | When nothing is left to send, no job is started and a message is shown. |
| FA-3 | A batch save skips notes the user decided while the job ran. |
| FA-4 | Review actions and Accept all are allowed while an organize job runs, because they use no model. |
| FA-5 | A rating of `4.0` counts as 4. `"4"` (a string) is invalid. |
| FA-6 | Review actions re-render the day's whole stop region, so a moved note appears under its new stop at once. |
| FA-7 | Undo or reject puts the note back under its import stop. |
| FA-8 | Edit is offered only on pending rows. A decided row is changed through Undo, then Edit. |

## 13. Items for NFR Requirements (not decided here)

| Id | Item |
|---|---|
| NFR-O1 | Does Ollama's OpenAI-compatible endpoint honour `response_format` `json_schema` with qwen3 thinking on? Otherwise fall back to `json_object`. |
| NFR-O2 | A speed target per batch and per day. Should the organizer run with thinking off? U1 chose thinking on for all calls. |
| NFR-O3 | The organizer accuracy target (≥ 85% correct category and stop) is measured by U6. Is a U3 smoke check wanted? |

## 14. Story and Definition of Done check

| Item | Covered by |
|---|---|
| US-05 S1 / S2 / rule | OR-D1, OR-D3, OR-D4 |
| US-06 S1 day | OR-RUN1..2, OR-V*, OR-F1 |
| US-06 S2 trip | OR-RUN3, the overview pending counts |
| US-06 S3 mixed language | OR-F4, prompt §5 |
| US-06 S4 instruction-like note | prompt §5 item 6, OR-V1 (labels limit the effect), test T-O4 |
| US-06 S5 not on import | OR-RUN0 |
| US-07 S1 / S2 / S3 / rules | OR-ST, OR-S1..S3, OR-R1, OR-ST3 |
| US-08 S1 / S2 | OR-AA1 |
| DoD: FakeLLMClient tests (valid, invalid JSON, unknown note ids, instruction-like) | §15 T-O1..T-O4 |
| DoD: accept-all leaves edited and rejected rows alone | OR-AA1, P-O1, T-O6 |

## 15. Tests to plan (Q19 A)

**Property tests** (PBT-03, blocking in Partial mode; Hypothesis profiles from U1):

| Id | Property |
|---|---|
| P-O1 | For any mix of statuses over several days, accept all for day D changes exactly D's `pending` rows to `accepted`, and nothing else. |
| P-O2 | Any sequence of review actions and re-runs leaves `notes.text` and `notes.stop_id` byte-for-byte equal. |
| P-O3 | For any reply (random JSON, labels, values), the parser yields at most one suggestion per note, only for labels in the batch, every kept item passes OR-F1..F4 and OR-S1, and every input note is either suggested or in `not_organized`. |
| P-O4 | A stateful test (`RuleBasedStateMachine`) of accept / edit / reject / undo / accept all / re-run keeps OR-ST1, and a decided row changes only through Undo. |

**Example tests** (`FakeLLMClient`):

| Id | Test |
|---|---|
| T-O1 | A valid batch reply is saved as pending, with the right ids. |
| T-O2 | Invalid JSON fails that batch only, and the other batches are saved. |
| T-O3 | An unknown note label or stop label is dropped and reported. |
| T-O4 | An instruction-like note stays inside `<trip_data>` in the prompt, and a reply that sets every rating to 5 still only changes labelled items that pass validation. |
| T-O5 | A batch split happens at 11 notes. |
| T-O6 | The US-08 S1 numbers: 12 rows, 2 edited, 1 rejected, so 9 are accepted. |
| T-O7 | `timeout_s` scaling. |
| T-O8 | A job timeout keeps the saved batches. |
| T-O9 | 404 / 409 / 422 / 503 at the API. |
| T-O10 | The CI-1 and CI-2 renders. |
