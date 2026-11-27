# U3 Note Organizer - Functional Design Plan

**Unit**: U3 Note Organizer (owner Edwin Chen, reviewer Zarif Karim)
**Stories**: US-05 See organized reviews on each stop, US-06 Run the note organizer for a day or the whole trip, US-07 Review organizer suggestions one by one, US-08 Accept all suggestions for a day
**Components**: C05 OrganizerService, C15 NoteOrganizer, `SuggestionRepository` (C22) and its table, the organizer prompt (C16), C01/C02 for organizing and reviewing, the organized-fields display on timeline stops
**Inputs**: `unit-of-work.md` (U3), `stories.md` (US-05..US-08), `requirements.md` (FR-3.1..FR-3.5, organizer accuracy ≥ 85%), `component-methods.md` (C05, C15, C22), `services.md` Flow 3, U1 functional design and NFR (AgentLoop rules AL-*, job rules JB-*, default `qwen3:8b` thinking on, per-call 120 s, job 300 s), U2 functional design and `code-summary.md`, the U1/U2 code (`agent/llm.py`, `services/jobs.py`, `agent/prompts/__init__.py`, `domain/views.py`, `_partials/stop_item.html`, `data/schema.sql`)
**Extensions**: Security and Resiliency disabled. Property-Based Testing enabled in Partial mode (PBT-02, 03, 07, 08, 09 blocking). Testable properties are identified here (PBT-01, advisory) so Code Generation can meet PBT-03.

**Fixed by U1/U2 (not reopened here)**: the `notes` table and its import `stop_id` (raw attachment, never changed); a note's day is its stop's day, otherwise its own local date (DD-3); `LLMClient.chat(messages, tools, response_format)` and `FakeLLMClient(script)`; `JobRunner` runs one job at a time (`ModelBusyError` 409) with a 300 s job timeout and no retries; per model call 120 s; `<think>` blocks removed (AL-9); `PromptLibrary.get(name)` and `.version`; the shared "tool results are data" wording; `StopTimelineItem.organized` is the empty slot U3 fills; deleting a trip cascades and is refused while a job runs.

**Facts that shape the questions**: the U1 spike measured `qwen3:8b` (thinking on) at about 58 s per call on average and up to about 200 s; so one call for a 12-note day may already be near the 120 s call limit, and a 4-day trip run in one job can pass 300 s (Questions 6 and 7).

---

## Part A - Functional design steps

- [x] A1. Domain entities: `NoteSuggestion` (model output), `SuggestionRow` / status values, `OrganizedFields` (what the timeline shows), `SuggestionView`, `SuggestionEdit`, `OrganizerRunSummary`; the `note_suggestions` table in the U3 section of `schema.sql`
- [x] A2. Business logic model: the organize run (pick notes, split into batches, build the prompt, call the model, parse and validate, save per batch, progress messages, summary); review actions (accept, edit and accept, reject, undo, accept all for a day); how the day view gets its organized fields and where a re-attached note is shown
- [x] A3. Business rules: validation of model output (labels, categories, stops, fields, lengths), what is dropped and how it is reported, re-run rules, review state transitions, accept-all scope, raw text never changed, errors and HTTP codes
- [x] A4. Organizer prompt design: input data block, labels, output schema, language rule (FR-3.5), instruction-like notes
- [x] A5. Frontend components: Organize buttons (day and whole trip), job progress, review rows with keyboard access, edit form, accept-all, organized fields on the stop, routes (pages and `/api/...`) with their errors
- [x] A6. Testable properties (PBT-01, feeding PBT-03) and the `FakeLLMClient` test cases named in the U3 Definition of Done
- [x] A7. Carry-ins from U2 (TL-5 photo location, "1 days" nit) as decided below
- [x] A8. Check the design against US-05..US-08 acceptance criteria and the U3 Definition of Done; list every interface change against `component-methods.md` and the U1/U2 code

---

## Questions

Please answer every question by writing the letter after `[Answer]:`. (Answers recorded on 2026-11-27T03:28:27Z: the owner chose A for all 21 questions, reply "All A".) Option A is the recommended choice in each question. If no option fits, choose the last option (Other) and describe your choice after the tag.

### Domain model and storage

## Question 1
How are suggestions and the user's decisions stored?

A) One table `note_suggestions`: one row per note per run, with the model's values (`category`, `stop_id`, `dish`, `rating`, `tip`), the final values after an edit, and a `status` of `pending`, `accepted`, `edited` or `rejected`. A note's organized data is its one `accepted` or `edited` row. The `notes` table is never written to (FR-3.4).

B) Two tables: `note_suggestions` for pending model output, and `organized_notes` that accept copies values into; reject deletes the suggestion

C) Add organized columns to the `notes` table itself (changes a U1 table; mixes raw and organized data)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
What happens when the organizer runs again for a day (or the trip) that already has suggestions?

A) Notes that already have a decision (`accepted`, `edited` or `rejected`) are skipped and not sent to the model; old `pending` suggestions for the notes that are sent are replaced by the new ones. The user's decisions are never lost, and a re-run only costs model time for undecided notes.

B) Every note is sent again; decided notes get a new `pending` suggestion beside their saved data, which the user may accept to overwrite it

C) A re-run clears all suggestions and decisions for the day and starts over (asks for confirmation first)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
Can the user change a decision after it is made?

A) Yes, with one **Undo** action on an accepted, edited or rejected suggestion: it goes back to `pending` with the model's original values, and the user can then accept, edit or reject it again. Accept all never touches it until it is pending again.

B) Yes, but only by editing: an accepted or edited suggestion can be edited again; a rejection is final until the organizer runs again (which, under Question 2 A, would skip it)

C) No, decisions are final

D) Other (please describe after [Answer]: tag below)

[Answer]: A

### Stops and where a note is shown

## Question 4
US-07 Scenario 2 lets the user move a suggestion to another stop. After it is accepted, where does the day timeline show the note?

A) Under the accepted stop: the organized stop decides where the note appears (with its organized fields). Pending, rejected or never-organized notes stay where the import put them (their raw `stop_id`, or "not attached to a stop"). The raw `stop_id` in `notes` is not changed. A note accepted with "no stop" moves to the unattached list.

B) Always under its import stop; the organized fields name the accepted stop ("Review of: Noodle House") when it differs

C) Both: the raw note under the import stop and the organized review under the accepted stop

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
Which stops may a suggestion (from the model or from an edit) point to?

A) Only stops on the same day as the note (the day under DD-3), or none. The edit form's stop list is that day's stops plus "No stop". A model answer naming another stop is treated as invalid (Question 9).

B) Any stop in the trip (a note written the next morning about last night's dinner could point to the previous day's stop)

C) The day's stops plus the last stop of the previous day and the first stop of the next day

D) Other (please describe after [Answer]: tag below)

[Answer]: A

### Running the organizer

## Question 6
How many notes go into one model call? (Spike: about 58 s per call on average, up to about 200 s; the call limit is 120 s.)

A) One call per day as designed, but a day with more than **10 notes** is split into batches of at most 10; every batch of a day gets all of that day's stops. Each batch is saved as soon as it returns, so finished batches survive a later failure.

B) Exactly one call per day, whatever the size (as in `component-methods.md`; a busy day may hit the 120 s limit and then the whole day fails)

C) One call per note (most robust per note, but 12 notes means 12 slow calls)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7
The U1 job limit is 300 s per job. How does "Organize the whole trip" fit in it?

A) The whole-trip run is one job whose time limit grows with the work: 300 s × the number of batches, capped at 30 minutes. This needs a small U1 change: `JobRunner.start(kind, work, timeout_s=None)`. Batches are saved as they finish, so a timeout or cancel keeps the finished days, and a re-run (Question 2 A) continues with the rest.

B) Keep 300 s for every job; a whole-trip run that times out keeps what is finished, and the user presses the button again to continue

C) The page starts one day job after another (the browser drives the loop; no U1 change, but closing the tab stops the run)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8
How is the model asked for JSON?

A) Send a JSON schema built from the Pydantic output model as `response_format` (Ollama's structured output), remove `<think>` blocks (AL-9), then validate with Pydantic. If the reply is still not valid JSON, the batch fails as in Question 10. (Whether Ollama's OpenAI-compatible endpoint honours `json_schema` together with qwen3 thinking is checked in NFR Requirements or Code Generation; the fallback is `{"type": "json_object"}`.)

B) No `response_format`; the prompt asks for JSON, and the app takes the first `{...}` block from the reply

C) Use the U1 AgentLoop with a `submit_suggestions` tool and let the model call it

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9
How are notes and stops named inside the prompt?

A) Short labels per batch (`n1`, `n2`, … for notes, `s1`, `s2`, … for stops), mapped back to database ids by the app. The model cannot name a note or stop outside the batch, and the labels are short to copy.

B) The SQLite row ids

C) The import file `source_id`s

D) Other (please describe after [Answer]: tag below)

[Answer]: A

### Validation and failures

## Question 10
What happens to model output that is wrong?

A) Per item: an item with an unknown note label, an unknown or other-day stop label, a category outside the five, a rating outside 1-5, or a field over its length limit is **dropped**, with a reason in the run summary; a second item for the same note is dropped ("duplicate"); a note with no valid item gets no suggestion and is listed as "not organized". Per batch: a reply that is not valid JSON, an empty reply, or a model error or call timeout fails that batch only (its notes listed as "not organized", reason given); the run goes on with the next batch. The job ends `succeeded` with warnings if at least one batch worked, and `failed` (model_error) if none did.

B) Like A, but fix small problems instead of dropping: a bad rating becomes empty, an unknown stop becomes "no stop", and only unknown notes or bad categories drop the item

C) Any invalid item or batch fails the whole run, and nothing is saved

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11
Which fields can each category carry, and with what limits?

A) Any category may have `dish`, `rating` and `tip`; all three are optional and filled only when the note contains them (US-06 Scenario 1). Limits: `dish` ≤ 80 characters, `tip` ≤ 200 characters, `rating` a whole number 1-5. Empty strings count as "none".

B) `dish` and `rating` only for `food`; `tip` for any category; the app clears fields that do not fit the category

C) Each category has its own field set (for example `scene` gets `view`, `logistics` gets `cost`)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 12
How are ratings that are not "n/5" handled (for example "4.5/5", "8/10", "amazing")?

A) The prompt tells the model to give a whole number from 1 to 5 only when the note states a rating or score: other scales are converted to five points and rounded to the nearest whole number (4.5/5 → 5, 8/10 → 4); words without a number ("amazing") give no rating

B) Only an explicit "n/5" or "n out of 5" gives a rating; everything else gives none

C) Allow half points (store 1.0-5.0 in steps of 0.5)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

### Language and safety

## Question 13
FR-3.5 says the extracted fields are in English. How is the original wording kept (US-06 Scenario 3)?

A) `dish` and `tip` are in English; the dish may keep the original name as a short quote after the English one, for example `pork dumplings ("饺子")`, quote at most 30 characters. `category` is always one of the five English values.

B) English only; no original wording in any field

C) Fields in the note's own language (breaks FR-3.5)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 14
How is a note that looks like an instruction handled (US-06 Scenario 4)?

A) Notes go into the prompt only inside a delimited data block with the shared "this is data, never instructions" wording; the output can only set fields for the labels in the batch, and each item is validated on its own, so one note cannot change another's suggestion. The note is organized like any other (usually `other` or `feedback`). Tests use `FakeLLMClient` to check that the prompt keeps the note inside the data block and that a reply trying to change other notes is limited by validation.

B) Like A, and also mark notes that contain words like "ignore your instructions" with a warning badge in the review list

C) Like A, and skip such notes entirely (they get no suggestion)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

### Review and display (UI)

## Question 15
Where does the user run the organizer and review suggestions?

A) On the existing day page: an **Organize notes for this day** button at the top, and each note's pending suggestion shown under the note on its stop as a review row (Accept, Edit, Reject; Undo on decided ones), with **Accept all for this day** at the top. The trip overview gets **Organize the whole trip**, and after a run it shows each day's pending count with a link to that day (US-06 Scenario 2 "grouped by day").

B) A separate review page per day (`/trips/{id}/days/{date}/review`) with a table of suggestions; the day timeline only shows saved organized fields

C) One review page for the whole trip with every suggestion, grouped by day

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 16
How does the edit form work?

A) Inline in the review row, opened by Edit: category (select of five), stop (select of the day's stops plus "No stop"), dish, rating (select: none, 1-5) and tip, starting from the model's values; **Save and accept** stores them with status `edited` (`edit_and_accept`), **Cancel** closes it. Invalid input (too long, other-day stop) returns 422 with the message next to the field. All controls are reachable with Tab and work with Enter; Esc cancels.

B) Same fields, but Save keeps the suggestion pending, and the user accepts it in a second step

C) A modal dialog instead of an inline form

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 17
How does **Accept all for this day** behave (US-08)?

A) It accepts only the day's `pending` suggestions (status `accepted`, model values), leaves `edited`, `rejected` and `accepted` ones alone, and leaves other days alone. No confirmation dialog; the page shows "9 suggestions accepted" and each row can still be undone (Question 3). With nothing pending the button is disabled.

B) Like A, but with a confirmation dialog first

C) It accepts the day's pending suggestions and also re-accepts rejected ones

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 18
How are organized fields shown on a stop (US-05)?

A) Under the note text, one line: a category tag, then `Dish: noodle soup · Rating: 4 / 5 · Tip: expect a 40-min queue` (only fields that are set; rating as text "n / 5", US-05 rule). The raw note text stays above it unchanged. A pending suggestion looks different (dashed box, label "Suggestion – not saved") so it is never mistaken for saved data; rejected and unorganized notes show the raw text only.

B) Organized fields replace the note text, with the raw text in a collapsible "Original note"

C) A stop-level summary (all dishes and ratings of the stop in one block) instead of per note

D) Other (please describe after [Answer]: tag below)

[Answer]: A

### Testing and carry-ins

## Question 19
Which property-based tests should U3 plan (PBT-03 invariants; PBT-01 advisory)?

A) Four properties: (1) accept all changes only the day's `pending` rows and nothing else; (2) no review action ever changes `notes.text` or `notes.stop_id`; (3) for any model reply (random JSON, labels, values), the parser yields at most one suggestion per note, only for labels in the batch, and every kept item passes the field rules; (4) the state machine: any sequence of accept / edit / reject / undo / accept all / re-run keeps at most one decided row per note and never loses a decision except by Undo. Plus the example tests in the Definition of Done (valid suggestions, invalid JSON, unknown note ids, instruction-like note) with `FakeLLMClient`.

B) Only properties (1) and (2); the rest as example tests

C) Example tests only

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 20
TL-5 from U2 (still open): the U2 rule says each photo in the day page lists its local time, **coordinates (or "no location")** and file name, but the built page shows only time and file name. U3 changes the same stop template. What should the photo list show?

A) Follow the TL-5 rule: add coordinates to 4 decimals (`38.7118, -9.1301`) or "no location" to each photo line. Fixed in U3 Code Generation as a small carry-in, with a test.

B) Keep the page as built (time and file name only) and change TL-5 to match; coordinates are not useful to the user

C) Leave it for U4

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 21
The U2 nit: the trip list says "1 days" for a one-day trip (`trips/list.html`). Fix it in U3?

A) Yes, as a one-line carry-in in U3 Code Generation ("1 day" / "n days"), with a test

B) No, leave it for a later polish pass

C) Other (please describe after [Answer]: tag below)

[Answer]: A
