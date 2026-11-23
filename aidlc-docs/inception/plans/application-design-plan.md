# Application Design Plan

**Inputs**: `requirements.md`, `stories.md`, `personas.md`, `execution-plan.md` (all approved), `docs/technical-environment.md`
**Outputs**: `aidlc-docs/inception/application-design/` containing `components.md`, `component-methods.md`, `services.md`, `component-dependency.md` and `application-design.md`
**Scope**: Components, their responsibilities and interfaces, method signatures, service orchestration and dependencies. Detailed business rules (merge algorithm, validation rules, schema columns) come later, in Functional Design for each unit.

**Fixed constraints from `technical-environment.md`** (not asked again):
- FastAPI and Pydantic v2; Jinja2 and htmx; `sqlite3` with FTS5; the `openai` SDK pointed at Ollama; httpx
- The project's own agent loop with an 8-step cap
- Layers call downward only (`api/pages → agent/domain → data`), and tools call repositories
- Prompts live in `trip_journal/agent/prompts/`

---

## Part 1: Design Questions

> **Note:** The team asked the AI to suggest answers. The AI suggested each answer with its reason, and the team took the suggestions; the team confirms them when it approves the application design (see `aidlc-docs/audit.md`, 2026-11-23T18:14:19Z).

Answer each question by writing a letter after the `[Answer]:` tag, or choose **X) Other** and describe what you want. A short reason after the letter records why the team chose it. These questions are technical, so the team's technical lead should lead the discussion.

### Component Identification

## Question 1
How should the three LLM features (note organizer, journal agent, Q&A agent) share the agent loop?

A) One generic `AgentLoop` (messages + tool schemas → validated tool calls → repeat, 8-step cap). `JournalAgent` and `ChatAgent` are thin wrappers that each supply their own prompt and tool set

B) A separate loop implementation inside each agent, so each can be tuned on its own

X) Other (please describe after [Answer]: tag below)

[Answer]: A, one loop means the 8-step cap, argument validation and error handling are written and tested once; the two agents differ only in prompt and tool set

## Question 2
Does the **note organizer** use the tool-calling agent loop?

A) No. It makes one LLM call per batch of notes (for example, one day). The stops and notes are passed in as delimited data, and the reply is structured JSON validated by Pydantic. No tools, so it is faster and more predictable on a local 8B model

B) Yes. It uses the agent loop with tools (`list_day_stops`, `get_stop_notes`) like the other two features

C) No tools, and one LLM call per note (simplest prompt, but more calls)

X) Other (please describe after [Answer]: tag below)

[Answer]: A, the organizer needs no lookups beyond the notes and stops it is given, and one structured call per day is faster and easier to validate on an 8B model than a tool loop

### Service Layer Design

## Question 3
Where does the orchestration of a request live? For example: generate a journal, run the grounding check, merge with user-owned paragraphs, then save.

A) A new `services/` package with one service per feature (`ImportService`, `OrganizerService`, `JournalService`, `ChatService`, `SettingsService`). Routers and pages call services; services call the agent, domain and data layers

B) Inside `agent/`: for example `JournalAgent.write_day()` generates, checks, merges and saves. Routers call agents and repositories directly, as in the example endpoint in `technical-environment.md`

C) In the routers themselves; no separate service layer

X) Other (please describe after [Answer]: tag below)

[Answer]: A, services give each feature one place for its request flow (generate, check, merge, save), which keeps routers thin and gives each unit owner a clear boundary; this adds a services/ package to the structure in technical-environment.md

## Question 4
How do the htmx pages and the JSON API relate?

A) Two thin front doors over the same services. The `pages/` routes return HTML pages and htmx fragments; the `api/` routes return JSON (used by tests, the evaluation script and any future client)

B) Pages call the JSON API from htmx and render the JSON in the browser (needs client-side templating)

C) One set of routes that return HTML or JSON depending on the request's `Accept` or `HX-Request` header

X) Other (please describe after [Answer]: tag below)

[Answer]: A, both front doors stay thin and share the same services, so the JSON API can be tested and used by the evaluation script without HTML

## Question 5
How does the page show the agent's **current step** while a journal or answer is generated (FR-4.7, no text streaming)?

A) The request starts a background job and returns a job id. htmx polls a status endpoint about once a second, which returns the current step and then the finished result

B) Server-Sent Events that send only step names ("calling list_day_stops…") and a final "done" event; the result is then fetched as HTML

C) One ordinary request with a generic spinner and no step names (this would not meet FR-4.7 as written)

X) Other (please describe after [Answer]: tag below)

[Answer]: A, polling a status endpoint works with plain htmx (hx-trigger every 1s), needs no SSE extension, and is easy to test

## Question 6
How many LLM jobs can run at the same time? A laptop running Ollama slows down sharply with parallel generations.

A) One at a time across the app. A second request while a job runs gets a clear "the model is busy, try again in a moment" message

B) One at a time, with later requests queued and started automatically in order

C) No limit; Ollama handles concurrency

X) Other (please describe after [Answer]: tag below)

[Answer]: A, one job at a time protects speed on a laptop; a clear busy message is simpler and more predictable than a queue

### Component Methods and Data Contracts

## Question 7
What shape should the JSON import file have? (`requirements.md` left the exact schema to Application Design.)

A) Flat lists with references: `trip` (with a string `trip_id`, a title and a home time zone), `stops[]`, `notes[]` and `photos[]`. Each item has its own id within the file; a note may reference a `stop_id` or none

B) Nested: `trip` → `stops[]` → `notes[]` under each stop, plus top-level `unattached_notes[]` and `photos[]`

X) Other (please describe after [Answer]: tag below)

[Answer]: A, flat lists with references are easier to validate with Pydantic and to write by hand for the sample trips; nesting would hide unattached notes in a special case

## Question 8
Which ids appear in citations such as `[stop:12]`?

A) SQLite row ids, which are unique across all trips. The tools return them, and the grounding check looks them up in the active trip

B) The ids from the import file, scoped to the trip (the check resolves them inside the active trip)

X) Other (please describe after [Answer]: tag below)

[Answer]: A, row ids are unique across trips so a citation can never point into another trip; each record also keeps its id from the file (source id) so the labelled evaluation set (US-22) can refer to stable file ids

## Question 9
How is each journal paragraph identified, so that "regenerate keeps user-owned paragraphs" knows what to replace?

A) By its slot in the fixed structure: `summary`, or the `stop_id` it describes. Regenerate fills only the slots that are not user-owned

B) By position (paragraph 1, 2, 3…); regenerate replaces unedited paragraphs at the same positions

X) Other (please describe after [Answer]: tag below)

[Answer]: A, the journal structure is fixed (summary plus one paragraph per stop), so a slot gives each paragraph a stable identity that survives regenerate even if the number of stops with text changes

## Question 10
Is the agent's tool-call list ("How this was made", FR-8.1) kept after the page is closed?

A) For journals, the list from the latest generation is saved with the journal and shown again later. For chat answers, it is kept only in the open page, like the chat history

B) Never saved; it is shown only right after a generation or an answer

C) Saved for both journals and chat answers

X) Other (please describe after [Answer]: tag below)

[Answer]: A, a saved journal should still show how it was made after a reload; chat answers follow the chat history rule (kept only in the open page)

## Question 11
How are settings (model name, Ollama base URL, place lookup on or off) stored and changed?

A) Defaults come from environment variables (a git-ignored `.env` is allowed). A Settings page saves changes to a `settings` table in SQLite, and saved values override the defaults without a restart

B) Environment variables only. Changing a setting means editing `.env` and restarting the app

C) A Settings page only, stored in SQLite, with built-in defaults

X) Other (please describe after [Answer]: tag below)

[Answer]: A, environment defaults keep the app runnable with no setup, and a Settings page lets the user turn on place lookup or switch models without editing files or restarting

### Component Dependencies and Design Patterns

## Question 12
How should the LLM client be abstracted, so that agent tests can use a fake client (NFR-7.2)?

A) A small `LLMClient` protocol (one `chat(messages, tools) -> reply` method), with an `OllamaClient` built on the `openai` SDK and a `FakeLLMClient` for tests, injected through FastAPI `Depends`

B) Agents use the `openai` client directly, and tests mock the SDK's HTTP calls

X) Other (please describe after [Answer]: tag below)

[Answer]: A, a one-method protocol keeps agents independent of the SDK and lets agent tests inject scripted replies through Depends

## Question 13
How does the evaluation script (US-23) run the product?

A) In process: a `scripts/evaluate.py` run with `uv run` builds the services against a temporary database, imports the sample trips and calls the services directly

B) Over HTTP against a running app, using the JSON API

X) Other (please describe after [Answer]: tag below)

[Answer]: A, in-process runs are faster, need no running server, and use a temporary database so the real data/trip.db is never touched

---

## Part 2: Design Generation Checklist

These steps run only after the answers are analyzed and any follow-up questions are resolved.

- [x] Step 1: Identify components
  - [x] List the components per layer (presentation, services or orchestration, agent, domain, data, places), following the answers to Questions 1–4
  - [x] Write each component's purpose, responsibilities and interface
- [x] Step 2: Define component methods
  - [x] Write method signatures with input and output types (Pydantic models or dataclasses named, not fully specified)
  - [x] Define the tool schemas for `list_day_stops`, `get_stop_notes`, `find_photos`, `search_notes`, `lookup_place` and the `save_journal` step
  - [x] Outline the import schema shape (Question 7), the citation ids (Question 8) and paragraph identity (Question 9)
- [x] Step 3: Define services and orchestration
  - [x] Describe the request flows for import, organize notes, write a journal, regenerate, ask a question and delete a trip
  - [x] Describe how progress is reported (Question 5), the concurrency rule (Question 6), how tool-call lists are kept (Question 10) and settings (Question 11)
- [x] Step 4: Define dependencies and communication
  - [x] Build a dependency matrix and check that every dependency points downward
  - [x] Draw a data-flow diagram for the journal and Q&A paths, with a text alternative
  - [x] Define the LLM client abstraction (Question 12) and how the evaluation script connects (Question 13)
- [x] Step 5: Validate
  - [x] Check that every story in `stories.md` is served by at least one component
  - [x] Check consistency with `requirements.md` and `technical-environment.md`, including the prohibited libraries
  - [x] Validate Mermaid and ASCII content before writing files

## Mandatory Design Artifacts
- [x] Generate components.md with component definitions and high-level responsibilities
- [x] Generate component-methods.md with method signatures (business rules detailed later in Functional Design)
- [x] Generate services.md with service definitions and orchestration patterns
- [x] Generate component-dependency.md with dependency relationships and communication patterns
- [x] Generate application-design.md consolidating the documents above
- [x] Validate design completeness and consistency
