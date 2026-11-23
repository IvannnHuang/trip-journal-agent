# Requirements Verification Questions

These questions clarify the requirements for **Trip Journal Agent**, based on `docs/vision.md` and `docs/technical-environment.md`.

Answer each question by writing the letter of your choice after the `[Answer]:` tag. If no option fits, choose **X) Other** and describe what you want after the tag. You can add a short note after any letter (for example `[Answer]: B, but only for food notes`).

There are 23 project questions in five sections, then 3 extension opt-in questions.

> **Note:** The AI recommended an answer and a reason for each question. The team agreed to take all of the recommendations, and the answers below record them (see `aidlc-docs/audit.md`, 2026-11-23T17:46:25Z). Each question gives the reason it is asked; "Vision open question" means `docs/vision.md` lists it as undecided.

---

## Section 1: Journal Generation

## Question 1
How should a day journal be structured? (Vision open question)

A) One paragraph per stop, in time order, each paragraph citing its stop and notes

B) A free-form narrative of the day, with citations inline in each sentence, grouping stops where it reads better (for example, a morning or a meal)

C) A short day summary paragraph first, then one paragraph per stop

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 2
Which language should the journal and the Q&A answers be written in, given notes that mix languages (for example Chinese and English in one note)? (Vision open question)

A) Always English; quote short original-language phrases (such as dish names) where useful

B) A setting chooses the output language (for example English or Chinese); notes in any language are understood

C) Follow the language most notes for that day are written in

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
Which journal tones should the MVP offer? (The example endpoint in `technical-environment.md` uses `casual | concise | detailed`.)

A) The three tones casual, concise and detailed, chosen per generation

B) One fixed tone only (simpler prompts and evaluation)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
What should happen to a sentence the grounding check finds unsupported (no citation, or a citation to a record that does not exist)?

A) Keep it in the draft and highlight it in the UI; the user decides whether to edit or delete it

B) Ask the agent once to rewrite the unsupported sentences; anything still unsupported is highlighted

C) Remove it from the draft automatically and list what was removed

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
How should grounding be measured for the success metric (≥ 95% of sentences cited, 0 invented facts)? (Vision open question)

A) Exact citation check only: each sentence cites at least one existing record id

B) Exact citation check in the app, plus an LLM-as-judge check in the offline evaluation script that verifies the cited record actually supports the sentence

C) Exact citation check plus a manual review by the team of the demo-trip journals, with no LLM judge

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 6
At what level should the app track user edits, so that "regenerate" never overwrites user text?

A) Paragraph level: any paragraph the user edited is marked user-owned and kept as is; only untouched generated paragraphs are rewritten

B) Paragraph level, with an explicit lock or unlock toggle per paragraph as well (edited paragraphs are locked automatically)

C) Whole journal: once the user edits anything, regenerate creates a separate new draft next to the edited one

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7
How should journals be saved?

A) Automatically: the latest generated draft and every user edit are saved to SQLite; only the current version is kept

B) Automatically, and earlier versions are kept so the user can view or restore a previous version

C) Only when the user clicks Save; an unsaved draft is lost when the page is closed

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Section 2: Note Organizer

## Question 8
When should the note organizer run? (Vision open question)

A) Automatically after import, for all notes in the trip

B) Only when the user asks, one day at a time

C) Only when the user asks, for one day or for the whole trip

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 9
How does the user review the organizer's suggestions (category, dish, rating, tip, suggested stop)?

A) One by one: accept, edit or reject each note's suggestion

B) One by one, plus "accept all" for a day

C) Suggestions are applied automatically; the user corrects only the wrong ones afterwards

X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Section 3: Trip Data and Import

## Question 10
What JSON import format should the MVP support? (Vision open question)

A) Our own documented JSON schema, designed during this project (trip, days, stops, notes, photo metadata)

B) The export format of the trip-logging app one teammate has built, used as is

C) Our own documented schema, plus a small converter script for the teammate's app export

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11
Should the import also accept a GPX file for the route? (Vision open question)

A) No: JSON only; the route, if any, is a summary inside the JSON (no map view in the MVP)

B) Yes: an optional GPX file alongside the JSON, used only for display and distance stats

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 12
How many trips does the app hold, and what happens when the same trip is imported again?

A) Several trips can be stored; the user picks the active trip. Re-importing a trip that already exists is rejected with a clear message

B) Several trips can be stored; re-importing a trip replaces it, after a confirmation that warns that its journals and note decisions will be deleted

C) Only one trip at a time; a new import replaces the current trip after a confirmation

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 13
How is a "day" defined, for trips that cross time zones or for stops that run past midnight?

A) By the local date of the stop's start time, using the UTC offset stored with each record

B) By an explicit list of days in the import file; each stop names the day it belongs to

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 14
What should the app do with photos in the MVP? (Photo content understanding is out of scope.)

A) Metadata only: photo count per stop and a list of time and location records; no images shown

B) Metadata, plus thumbnails when the import includes a local file path for a photo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 15
What should the synthetic sample trips contain? (The vision asks for two trips of 3–4 days with no real personal data.)

A) Two trips in real public cities with invented people and notes; notes in English only

B) Two trips in real public cities with invented people and notes; some notes mixing English and Chinese, to test mixed-language handling

C) Two trips in fictional places, so nothing can be looked up or matched to real data

X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Section 4: Trip Q&A and Place Lookup

## Question 16
How should the Q&A chat work?

A) Multi-turn: follow-up questions ("and the day after?") use the earlier messages; history is kept only while the page is open

B) Multi-turn, and the chat history is saved per trip in SQLite

C) Single-turn: each question is answered on its own, with no history

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 17
How much of the agent's work should the UI show for a Q&A answer or a journal draft?

A) A collapsible list of the tools called, with their arguments and the record ids returned; citations link to the records

B) Only the tool names, plus links from each citation to its record

C) Full detail, including the raw tool results passed to the model (useful for debugging and the demo)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 18
Place lookup (OpenStreetMap Nominatim) sends coordinates off the laptop. Should it be on by default?

A) Off by default; the user turns it on in a setting. Without it, the agent uses place names from the import

B) On by default, with a setting to turn it off; results are cached

C) Not used at all in the MVP; only place names from the import are used

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Section 5: Non-Functional Requirements

## Question 19
Should the MVP build the "hosted LLM behind an explicit setting" option from `technical-environment.md`?

A) No: Ollama only. The model name and base URL are settings, so a hosted provider can be added later

B) Yes: an explicit setting allows an OpenAI-compatible hosted provider, with a warning, and only with sample data

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 20
Should journal drafts and Q&A answers stream to the page as they are generated? (The vision lists streaming as a mitigation for slow laptops.)

A) Yes, both stream

B) No streaming; show a progress indicator with the current agent step (for example "calling list_day_stops…") until the result is ready

C) Q&A answers stream; journal drafts show a progress indicator

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 21
On which hardware are the speed targets (journal ≤ 90 s, Q&A answer ≤ 30 s) measured?

A) On the team's slowest laptop that will run the demo

B) On one named reference laptop, which we record in the requirements

C) Best effort on any laptop; the targets are goals, not pass/fail criteria

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 22
What should happen when Ollama is not running, or the model is not installed?

A) The app still starts; import, timeline and journal editing work; LLM features show a clear message on how to start Ollama or pull the model

B) The app refuses to start and prints instructions

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 23
What accessibility and usability standard should the pages meet?

A) Basic: semantic HTML, keyboard-usable forms and buttons, readable contrast, and highlighted text not shown by color alone

B) WCAG 2.1 AA, checked with an automated tool

C) No specific standard for the MVP

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Extension Opt-In Questions

## Question: Security Extensions
Should security extension rules be enforced for this project?

A) Yes — enforce all SECURITY rules as blocking constraints (recommended for production-grade applications)

B) No — skip all SECURITY rules (suitable for PoCs, prototypes, and experimental projects)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question: Resiliency Extensions
Should the resiliency baseline be applied to this project?

**What this extension is.** Enabling it applies a set of **directional, design-time best practices** for building resilient systems, derived from the **AWS Well-Architected Framework (Reliability Pillar)** and resilience-review guidance. It steers requirements, design, and code toward fault tolerance, high availability, observability, and recoverability — covering 15 practice areas across business goals, change management, observability, high availability, disaster recovery, and continuous improvement.

**What this extension is NOT.** Enabling it does **not** make your workload production-ready, nor does it certify or guarantee any availability, RTO, or RPO target. It is a **starting point** that scaffolds good resiliency decisions early — it is not a substitute for a formal **AWS Well-Architected Review** of the built system.

Treat the output as a well-grounded **first draft of your resiliency posture** to build on and validate — not a finished, production-certified result.

A) Yes — apply the resiliency baseline as directional best practices and design-time guidance (recommended for business-critical workloads, as an informed starting point that you can validate and harden before go-live)

B) No — skip the resiliency baseline (suitable for PoCs, prototypes, and experimental projects where rapid iteration matters more than reliability)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question: Property-Based Testing Extension
Should property-based testing (PBT) rules be enforced for this project?

A) Yes — enforce all PBT rules as blocking constraints (recommended for projects with business logic, data transformations, serialization, or stateful components)

B) Partial — enforce PBT rules only for pure functions and serialization round-trips (suitable for projects with limited algorithmic complexity)

C) No — skip all PBT rules (suitable for simple CRUD applications, UI-only projects, or thin integration layers with no significant business logic)

X) Other (please describe after [Answer]: tag below)

[Answer]: B
