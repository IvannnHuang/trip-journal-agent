# Story Generation Plan

**Role**: Product owner
**Inputs**: `aidlc-docs/inception/requirements/requirements.md` (approved), `docs/vision.md`, `aidlc-docs/inception/plans/user-stories-assessment.md`
**Outputs**: `aidlc-docs/inception/user-stories/personas.md`, `aidlc-docs/inception/user-stories/stories.md`

---

## Part 1: Planning Questions

> **Note:** The team asked the AI to suggest answers. The AI suggested each answer with its reason, and the team took the suggestions and approved the plan (see `aidlc-docs/audit.md`, 2026-11-23T17:58:57Z and the story-plan approval entry after it).

Answer each question by writing a letter after the `[Answer]:` tag. If no option fits, choose **X) Other** and describe what you want. A short reason after the letter (for example `[Answer]: B, because…`) records why the team chose it.

### Story Breakdown Approaches (context for Question 1)

| Approach | How stories are grouped | Benefits | Trade-offs |
|---|---|---|---|
| User journey-based | By the steps of a trip logger's evening: import → review notes → write journal → ask questions | Reads like the product's real use; shows hand-offs between features | One feature can appear in several journeys; harder to map to code units |
| Feature-based | One group per MVP feature (import, timeline, organizer, journal, grounding, editing, Q&A, place lookup) | Maps directly to requirements and later to units of work | Less visible how the features connect for the user |
| Persona-based | One group per persona | Makes each user type's needs obvious | Shared features repeat across personas |
| Epic-based (hierarchical) | Epics (large capabilities) containing smaller stories | Gives two levels: epics for planning, stories for testing | Needs clear rules for what is an epic and what is a story |
| Hybrid | For example, feature-based epics with stories written as steps in a journey | Combines traceability with user flow | Needs a stated rule for each level |

## Question 1
How should the stories be organized?

A) User journey-based

B) Feature-based

C) Persona-based

D) Epic-based: one epic per MVP feature, with smaller stories inside each epic

E) Hybrid: feature-based epics, plus a short end-to-end journey per persona that links the stories in order

X) Other (please describe after [Answer]: tag below)

[Answer]: E, epics follow the MVP features so they map cleanly to requirements and later to units of work; one short journey per persona shows how the stories connect in real use

## Question 2
Which personas should `personas.md` contain? The vision names three user types: trip logger (primary), food and place reviewer, and trip companion.

A) The three user types from the vision, one persona each

B) The three user types, plus a "project team as evaluator" persona for the sample-data and evaluation stories (FR-11)

C) Two personas: the trip logger (including the reviewer's needs) and the trip companion

X) Other (please describe after [Answer]: tag below)

[Answer]: B, the evaluator persona gives the sample-data and evaluation work (FR-11) an owner and acceptance criteria tied to the success metrics

## Question 3
What should each persona be based on? (One teammate has built a personal trip-logging app.)

A) The teammate's real trip-logging habits, anonymized (no real names, places or trip data), with the other personas invented to fit the vision

B) Fully invented personas built only from the vision's user-type descriptions

X) Other (please describe after [Answer]: tag below)

[Answer]: B, invented personas built from the vision's user types, so no teammate's real travel habits or data end up in the repository

## Question 4
How does the **trip companion** use the app, given that the MVP is a single-user app on one laptop with no accounts or sharing?

A) The companion uses the trip logger's laptop, with the logger present or not, and asks questions in the same chat panel

B) The companion is a persona whose needs shape the Q&A design (plain-language questions, no knowledge of the data format), but who has no stories of their own

C) Drop the companion from the MVP stories, since sharing is out of scope

X) Other (please describe after [Answer]: tag below)

[Answer]: A, the companion asks questions in the same chat panel on the trip logger's laptop, which fits the single-user, local-only MVP

## Question 5
How does the **food and place reviewer** see their organized reviews (dish, rating, tip)? `requirements.md` shows organized notes on the day timeline but has no separate review view.

A) On the day timeline only: each stop shows its organized notes (dish, rating, tip). No new view

B) A new trip-level "Places I reviewed" list that shows every stop with a rating and links to its day. This changes the requirements, which would be updated through the workflow

X) Other (please describe after [Answer]: tag below)

[Answer]: A, a separate review list would add scope; showing the organized dish, rating and tip on each stop in the day timeline meets the reviewer's need

## Question 6
What size should a story be?

A) One story per user-visible capability (for example "Regenerate a journal and keep my edits"), roughly 15–25 stories in total

B) Finer: about one story per requirement ID, roughly 40 or more stories

C) Coarse: one story per MVP feature, about 8–10 stories, each with many acceptance criteria

X) Other (please describe after [Answer]: tag below)

[Answer]: A, one story per user-visible capability keeps each story small and testable without splitting every requirement into its own story

## Question 7
Which format should the acceptance criteria use?

A) Given / When / Then scenarios for every criterion

B) Checklists of testable statements

C) Given / When / Then for the main and error scenarios, plus checklist items for smaller rules (such as limits and formats)

X) Other (please describe after [Answer]: tag below)

[Answer]: C, Given / When / Then for the main and error scenarios keeps them testable; checklist items suit small rules such as limits and formats

## Question 8
Where should error and edge cases go? Examples: invalid import file, re-import rejected, Ollama not running, agent reaches the 8-step limit, a question with no answer in the data.

A) As acceptance criteria inside the story they belong to

B) As separate stories (for example "See a clear message when the model is not running")

C) Inside the story, except cross-cutting cases (Ollama missing, step limit reached) that get their own stories

X) Other (please describe after [Answer]: tag below)

[Answer]: C, most edge cases belong inside their story; Ollama missing and the step limit affect several features, so each gets its own story

## Question 9
How should non-functional requirements (speed targets, privacy, accessibility) appear in the stories?

A) As acceptance criteria on the stories they affect (for example "the draft is ready in ≤ 90 s on the slowest demo laptop")

B) Only in `requirements.md`, not in the stories

C) As a separate group of quality stories (for example "As a trip logger, I want my location data to stay on my laptop")

X) Other (please describe after [Answer]: tag below)

[Answer]: A, a speed or privacy target is only testable when it is attached to the story it affects

## Question 10
Should team-facing work (synthetic sample trips, the labelled evaluation set, the evaluation script) be written as user stories?

A) Yes, as stories for the team or evaluator persona, with acceptance criteria tied to the success metrics

B) No; these stay as requirements (FR-11) and are planned in the units of work only

X) Other (please describe after [Answer]: tag below)

[Answer]: A, see Question 2

## Question 11
How should stories trace back to requirements?

A) Each story lists the requirement IDs it covers (for example FR-6.1, FR-6.2), and a table at the end shows that every FR is covered by at least one story

B) Each story lists the requirement IDs it covers; no coverage table

C) No traceability; the stories stand alone

X) Other (please describe after [Answer]: tag below)

[Answer]: A, the coverage table shows that every functional requirement has at least one story before Application Design starts

## Question 12
Should each story carry a relative size estimate (the "Estimable" part of INVEST)?

A) Yes: S / M / L relative size for each story

B) No size estimates in the stories

X) Other (please describe after [Answer]: tag below)

[Answer]: A, relative sizes help when the stories are grouped into units of work

---

## Part 2: Generation Checklist

These steps run only after the planning answers are analyzed and the team approves this plan.

- [x] Step 1: Draft `personas.md`
  - [x] Write each persona chosen in Question 2 (on the basis chosen in Question 3): name, background, travel habits, goals, frustrations, comfort with technology, and the features they use
  - [x] Describe how the trip companion uses the app (Question 4) and how the reviewer sees reviews (Question 5)
  - [x] Map each persona to the stories they take part in
- [x] Step 2: Draft the story structure in `stories.md`
  - [x] Organize the stories using the approach from Question 1
  - [x] Add end-to-end journeys if Question 1 calls for them
- [x] Step 3: Write the user stories
  - [x] Use the "As a [persona], I want [capability], so that [benefit]" format
  - [x] Size each story per Question 6, and add estimates if Question 12 calls for them
  - [x] Write acceptance criteria for every story in the format from Question 7
  - [x] Place error and edge cases per Question 8
  - [x] Place non-functional requirements per Question 9
  - [x] Include or leave out team-facing stories per Question 10
  - [x] Add traceability per Question 11
- [x] Step 4: Check quality
  - [x] Check each story against INVEST: Independent, Negotiable, Valuable, Estimable, Small, Testable
  - [x] Confirm every functional requirement in `requirements.md` is covered by at least one story, or is noted as covered elsewhere
  - [x] Confirm the stories are consistent with `requirements.md` and `docs/vision.md` (no new scope unless the team approved it)
- [x] Step 5: Finish
  - [x] Save `personas.md` and `stories.md` under `aidlc-docs/inception/user-stories/`
  - [x] Update `aidlc-state.md` and `audit.md`

## Mandatory Story Artifacts
- [x] Generate stories.md with user stories following INVEST criteria
- [x] Generate personas.md with user archetypes and characteristics
- [x] Ensure stories are Independent, Negotiable, Valuable, Estimable, Small, Testable
- [x] Include acceptance criteria for each story
- [x] Map personas to relevant user stories
