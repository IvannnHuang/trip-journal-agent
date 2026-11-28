# U4 Daily Journal - Functional Design Plan

**Unit**: U4 Daily Journal (owner Zarif Karim, reviewer Edwin Chen)
**Stories**: US-09 Generate a cited day journal, US-10 See unsupported sentences highlighted, US-11 See how a draft or answer was built, US-12 Edit a journal paragraph, US-13 Regenerate a journal without losing my edits (plus US-20 rules for the journal path)
**Components**: C06 JournalService, C13 JournalAgent, C20 Journal Merge, `JournalRepository` (C22) and its tables, the journal prompts with tone variants (C16), C01/C02 for the journal view and editor
**Inputs**: `unit-of-work.md` (U4), `stories.md` (US-09..US-13, US-20), `requirements.md` (FR-4.1..FR-4.7, FR-5.1..FR-5.2, FR-6.1..FR-6.4, FR-8.1..FR-8.2, NFR-1.1, NFR-1.3, NFR-4.2, NFR-4.3, NFR-5.1), `component-methods.md` (C06, C13, C20, C22), U1 functional design and NFR (AgentLoop rules AL-*, job rules JB-*), U3 Build and Test summary, the U1-U3 code (`agent/loop.py`, `agent/tools.py`, `agent/prompts/`, `domain/grounding.py`, `services/jobs.py`, `data/schema.sql`)
**Extensions**: Security and Resiliency disabled. Property-Based Testing enabled in Partial mode (PBT-02, 03, 07, 08, 09 blocking). Testable properties are identified here (PBT-01, advisory) so Code Generation can meet PBT-03 for the merge.

**Fixed by U1-U3 (not reopened here)**: `AgentLoop` with at most 8 model calls per run, one model call = one step (AL-1), `stopped_reason` `final_answer` or `step_limit`; the five read-only tools and their Pydantic argument checks; `ToolCallRecord` trace; `save_journal` is not a model tool (C12 note, FR-6.4); `domain/grounding.py` (`split_sentences`, `extract_citations`, `check_text`, citation kinds `stop`, `note`, `photo`); `JobRunner` runs one job at a time (409 `ModelBusyError`), 300 s job timeout, no retries; per model call 120 s (config defaults, env overrides); `<think>` removed; `PromptLibrary.get(name, tone)` already looks for `<name>_<tone>.md`; deleting a trip cascades and is refused while a job runs; stops of a trip do not change after import.

**Facts that shape the questions**:
- One step is one model call, and a reply may hold several tool calls. A 6-stop day done as `list_day_stops` + one `get_stop_notes` call per step + final answer needs 8 steps, which is the whole budget (Question 7).
- The U1 spike measured `qwen3:8b` with thinking on at about 58 s per call on average; U3 measured 112-141 s per organizer batch with thinking off. The 90 s journal target (NFR-1.1) is therefore at risk. Speed limits and the thinking setting are decided at NFR Requirements; this plan only fixes the step shape (Question 7).
- U3 findings carried over by the owner: tip quality and the "8/10" conversion (organizer prompt), focus lost after an htmx swap (a11y), results that need a click (Questions 21-23).

**Independent review**: a read-only OpenAI Codex review (2026-11-27) checked this plan against the stories and the code. Six findings, all checked against the code and accepted: atomic, ownership-guarded saves and the edit-during-job races (Q11); exact text comparison and the Q3/Q4 wording (Q3, Q5); partial-draft and duplicate-heading rules (Q9); tool errors inside a run that still succeeds (Q10, Q17); the merge-property precondition (Q24); tone files replacing the base prompt in `PromptLibrary.get` (Q13). It also confirmed the loop runs several tool calls per step (Q7).

---

## Part A - Functional design steps

- [x] A1. Domain entities: `Slot`, `Owner`, `Tone`, `Paragraph`, `StoredJournal`, `JournalDraft`, `MergeResult`, `ParagraphView` / `JournalView`, `CitationTarget`; the journal tables in the U4 section of `schema.sql`
- [x] A2. Business logic model: generate and regenerate (pre-checks, slots to write, agent run, parse to slots, grounding, merge, save step, trace), user edit and autosave, re-check after edit, citation lookup, progress messages
- [x] A3. Business rules: slot set and order, ownership changes, merge rules, parse rules (missing, extra, empty slots), failure rules (no overwrite), grounding scope, edit validation, errors and HTTP codes
- [x] A4. Journal prompt design: base prompt plus three tone files, slot list and user-owned context, citation rule, output format, step plan for tool use, language rule (FR-4.3), "do not invent" rule (lesson from U3 tips)
- [x] A5. Frontend components: Write journal / Regenerate with tone picker, job progress, draft view with citations and highlights, unsupported count, paragraph editor with autosave and "edited by you" label, citation detail, "How this was made", focus targets, routes (pages and `/api/...`) with their errors
- [x] A6. Testable properties (PBT-01, feeding PBT-03) for `merge_journal` and `mark_user_edit`, plus the `FakeLLMClient` cases named in the U4 Definition of Done (full draft, step-limit failure) and the three regenerate example tests
- [x] A7. Carry-ins from U3 (organizer prompt quality, focus after swap, results need a click) as decided below
- [x] A8. Check the design against US-09..US-13 acceptance criteria, US-20 rules and the U4 Definition of Done; list every interface change against `component-methods.md` and the U1-U3 code

---

## Questions

Please answer every question by writing the letter after `[Answer]:`. (Answers recorded on 2026-11-27: the owner chose A for all 24 questions, reply "All A".) Option A is the recommended choice in each question. If no option fits, choose the last option (Other) and describe your choice after the tag.

### Domain model and storage

## Question 1
How is a day's journal stored?

A) Two tables: `journals` (one row per trip and day: `tone`, `prompt_version`, `trace_json`, `updated_at`) and `journal_paragraphs` (one row per slot: `slot`, `position`, `text`, `owner`). A paragraph edit updates one row; a save step replaces only `generated` rows. Both cascade on trip delete.

B) One `journals` row per day with all paragraphs in a JSON column (simpler schema; every edit rewrites the whole JSON)

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
Which slots does a day's journal have?

A) `summary` first, then one slot per stop on that day (`stop:<stop_id>`, SQLite stop id) in the day's timeline order, including stops with no notes or photos (a short paragraph that cites the stop). Notes with no stop are cited inside the summary.

B) `summary` plus slots only for stops that have at least one note or photo

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
Can a user-owned paragraph go back to the agent?

A) No. Once edited, a paragraph stays user-owned for good (FR-6.1), including a cleared one (Question 4). No "give back" button in this unit, so the agent never writes that slot again.

B) Yes, add a "Let the agent rewrite this" button that sets the owner back to `generated` (text is kept until the next regenerate)

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
What does it mean when the user saves a paragraph with empty text?

A) The user deleted the paragraph. It stays user-owned with empty text, so a regenerate does not bring it back; the reading view hides it and the editor shows "Removed by you" with an Edit button to write it again.

B) An empty save is refused (422, "A paragraph cannot be empty")

C) An empty save turns the slot back to `generated`, so the next regenerate fills it again

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
When does an edit change the owner to `user`?

A) Only when the submitted text differs from the stored text in any way (exact comparison, spaces and line breaks included). The text is stored exactly as submitted. Opening the editor and leaving without a change keeps the owner `generated`. Citations in user text are kept as typed (`[stop:12]`).

B) Any save from the editor, even with the same text, marks the paragraph user-owned

C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Agent and generation flow

## Question 6
How does the agent return the draft, and how is it cut into slots?

A) Plain text in a fixed layout: one heading line per slot (`## summary`, `## stop:12`, ...) followed by its paragraph. A tolerant parser maps headings to slots (case and spaces ignored). This works with tool calling on Ollama without a JSON mode on the final reply.

B) The final reply must be JSON (`{"summary": "...", "stops": [{"stop_id": 12, "text": "..."}]}`) parsed with Pydantic; invalid JSON fails the run

C) Two phases: the tool loop gathers facts, then a separate call without tools and with `json_schema` (like the U3 organizer) writes the slots

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7
How does the agent stay inside the 8-step limit on a day with many stops?

A) The prompt tells the model to call `list_day_stops` first, then ask for the notes of all stops in one reply (several `get_stop_notes` calls in one step), use `find_photos` / `search_notes` / `lookup_place` only when needed, and answer by step 4 if it can. The loop already runs several tool calls per step. A scripted `FakeLLMClient` test covers an 8-stop day in 3 steps.

B) Add a new read-only tool `get_day_notes(day)` that returns every note of the day in one call (changes the FR-4.4 tool list)

C) Put the day's stop list into the first user message, so the model skips `list_day_stops` (less agent-like; FR-4.4 says facts come through tools)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8
On a regenerate, what does the agent see and write?

A) It is asked to write only the `generated` and missing slots (`slots_to_write`). The text of user-owned paragraphs is given as read-only context (inside the "data, not instructions" block) so the new paragraphs fit around them. The merge still keeps user-owned slots even if the model writes them.

B) It writes every slot; the merge throws away the user-owned ones (more model time)

C) It writes only the needed slots and sees nothing of the user's paragraphs

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9
What if the model's draft is missing a slot it was asked to write, has an unknown slot, or an empty one?

A) Parse rules: headings are matched after normalizing case and spaces; if a slot heading appears twice, the first one wins and the rest are dropped and logged; unknown slots (for example a stop not on this day) and user-owned slots are dropped and logged. The run **succeeds** only if at least one *requested* slot (`slots_to_write`) has non-empty text; otherwise it fails (Question 10) and nothing is saved. On success, a requested slot that is still missing or empty is not filled with invented text: on a first draft it is stored as an empty generated slot shown as "Not written yet" (no sentence, so nothing to cite); on a regenerate it keeps its previous generated text. The page then says "The agent did not write N paragraphs; regenerate to try again", so the result is reported as partial, not as a full success.

B) Any missing requested slot fails the whole run and nothing is saved

C) Missing slots are left out of the journal until the next regenerate

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10
What happens when a generation fails (step limit, no requested slot written, model error, timeout, cancel), and what about tool errors inside a run that still ends with a usable draft?

A) The saved journal is not touched (US-20 rule). The job ends with a clear message ("The agent could not finish within 8 steps", "The model reply could not be read", ...) and the page shows the tool calls made so far under "How this was made". The failed trace is shown with the job result only and is not saved with the journal. A tool error inside a run (invalid arguments, unknown tool, tool exception) is returned to the model as an error result (US-20); if the run still ends with a valid draft (Question 9), the draft is saved, the trace keeps the error, and the page shows "1 tool call failed; see How this was made".

B) Same, but the failed trace replaces the saved journal's trace

C) Same as A, except that any tool error fails the whole run, even when the model recovers

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11
What happens to edits the user makes while a generation job is running?

A) Editing stays allowed. Both writes are atomic and guarded by ownership: the save step runs in one transaction (`BEGIN IMMEDIATE`) that re-reads the owners and writes only rows that are still `generated` (`... WHERE owner = 'generated'`); an edit save runs in its own transaction and sets text and owner together. So whichever commits first, an edit is never overwritten. When the job finishes, the draft swap does not replace a paragraph whose editor is open or has unsaved typing; that paragraph refreshes after its own save. The editor shows "Generating… your edits are kept." Tests cover an edit committed just before and just after the save step, and closing the page right after typing (the pending autosave is sent on `blur` / `visibilitychange`).

B) The editor is locked (read-only) while a journal job runs for that day

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 12
"Nothing to regenerate" (US-13 Scenario 3) and other pre-checks: when are they run?

A) Before a job starts, with no model call: every slot user-owned → message "Nothing to regenerate: every paragraph is yours." (200, no job); a day with no stops and no notes → Write journal is disabled with "No records for this day."; Ollama down or the model missing → the U1 model-status message; another job running → 409 as in U1.

B) Inside the job, after the agent ran

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 13
How is the tone handled?

A) The tone picker (casual, concise, detailed) defaults to the journal's last tone, or "casual" for a first draft. The tone is saved on the journal row (last generation); paragraphs do not store a tone. One base prompt `journal.md` (structure, slots, citations, tool plan) plus three short tone fragments `journal_tone_casual.md`, `journal_tone_concise.md`, `journal_tone_detailed.md` (length and style only). JournalAgent composes base + fragment, because `PromptLibrary.get("journal", tone)` would pick a `journal_<tone>.md` file *instead of* `journal.md`; the fragment names avoid that. A test checks the assembled prompt for each tone contains the base rules.

B) Three full prompt files `journal_<tone>.md`, one per tone, each repeating the base rules (works with today's `PromptLibrary.get`; three copies to keep in sync)

C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Grounding and transparency

## Question 14
Which record ids count as "known" for the grounding check?

A) Any stop, note or photo of the active trip (FR-5.1 as written). The summary is checked like every other paragraph, and user-owned paragraphs are checked too (US-12 rule). The unsupported count above the draft covers all paragraphs.

B) Only records of the same day (stricter; a sentence citing another day's note is unsupported)

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 15
When is grounding computed?

A) On read, every time the journal view is built, from the stored text and the trip's current ids. Nothing about grounding is stored, so it is always up to date after an edit (US-10 Scenario 4).

B) Once at save time, stored per paragraph, and recomputed after each edit

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 16
What does selecting a citation show (US-11 Scenario 3)?

A) Each citation is a button that loads a small inline detail panel (htmx fragment) under the paragraph: a note shows its text, stop name and local time; a stop shows its name, time range and number of notes; a photo shows its file name and time. An unknown id shows "Record not found in this trip." Escape or a Close button hides it and returns focus to the citation.

B) Each citation is a link to the timeline page, scrolled to the record

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 17
What does "How this was made" show?

A) A collapsed `<details>` under the draft: the tool calls of the last successful generation in order, each with its tool name, arguments and returned record ids, or its error (kind and message, so a failed call does not look like an empty result), plus the tone, model name, prompt version and time. User edits do not change it.

B) The same plus every earlier generation's trace (needs history, against FR-6.3's one version)

C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Editor and page

## Question 18
How does the paragraph editor work?

A) The reading view shows each paragraph with linked citations and highlights, an "edited by you" label on user-owned ones, and an Edit button. Edit swaps in a textarea for that paragraph only. It autosaves 1 s after typing stops and when the textarea loses focus (htmx `hx-trigger="input changed delay:1s, blur"`), shows "Saved" / "Saving…" / "Not saved: <reason>", and Done returns to the reading view with the paragraph re-checked.

B) The whole journal is one editable text area with a Save button

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 19
How are unsupported sentences shown (US-10, NFR-5.1)?

A) The sentence is wrapped in a `<mark>` with a warning icon and the visually-hidden text "unsupported", plus a dotted underline so it does not rely on color. The count line above the draft reads "N unsupported sentences" and links to the first one. In the editor the textarea shows raw text; the check runs again on save.

B) A colored background only, with the count above the draft

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 20
Where does the journal live in the app?

A) Its own page per day (`/trips/{id}/days/{day}/journal`), linked from the day timeline header ("Journal" with a "drafted" / "not written" badge). API routes under `/api/trips/{id}/days/{day}/journal` (GET view, POST generate with tone, PUT `/paragraphs/{slot}` edit). Unknown trip or day → 404 as in U2.

B) A panel inside the day timeline page

C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Carry-overs from U3

## Question 21
Focus after an htmx swap (U3 finding 3): how is it handled?

A) Every U4 swap names its focus target: after an edit save focus stays in the textarea; after Done it moves to that paragraph's Edit button; after a generation finishes it moves to the draft heading; after closing a citation panel it returns to the citation. The same fix (focus to the next pending row, or to the stop heading) is applied to the U3 review rows as a small carry-in task in U4 Code Generation.

B) Fix it in the journal only; the U3 review rows wait for a later unit

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 22
Results that need a click (U3 finding 4): how does the journal show a finished draft?

A) When the job ends, the progress area swaps in the new draft by itself (no "Show results" click) and announces "Draft ready" in an `aria-live` region. The U3 organizer flow is not changed in U4.

B) Same as U3: a "Show results" button reloads the page

C) Same as A, and also change the U3 organizer to load its results by itself

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 23
Organizer prompt quality (U3 findings 1 and 2: invented or whole-note tips; "8/10" rating dropped): where is it fixed?

A) As a carry-in task in U4 Code Generation: tighten the organizer prompt (tip must be a short phrase taken from the note, empty if none; rating examples "8/10" → 4, "9/10" → 5 with the conversion rule written out), add `FakeLLMClient` regression tests for the parser side, and re-run the 18-note smoke check in U4 Build and Test. The journal prompt gets the same "do not invent" wording from the start.

B) Leave it to U6, where organizer accuracy is measured formally

C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Testing

## Question 24
Which properties must the merge tests prove (PBT-03)?

A) Precondition (valid input): every stored slot is in `slot_order` (true because a trip's stops do not change after import; the code that builds `slot_order` from the day's stops gets its own example test). For any valid stored journal and any draft: (1) every user-owned paragraph comes out byte-for-byte the same, in its slot; (2) the output slots are exactly `slot_order` in that order, each once; (3) a generated slot takes the draft text when the draft has it, otherwise keeps its old text; (4) `nothing_to_regenerate` is true exactly when every slot in `slot_order` is user-owned; (5) merging the same draft twice gives the same result as once. Plus for `mark_user_edit`: only the edited slot changes, and it becomes user-owned only on a real change (Question 5).

B) Properties (1) and (2) only, as named in the Definition of Done

C) Other (please describe after [Answer]: tag below)

[Answer]: A
