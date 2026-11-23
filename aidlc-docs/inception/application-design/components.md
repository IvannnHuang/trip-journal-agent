# Components

**Source decisions**: `aidlc-docs/inception/plans/application-design-plan.md` (Q1–Q13), `requirements.md`, `stories.md`, `docs/technical-environment.md`

## Package Layout

The layout follows `technical-environment.md` and adds one package, `services/`, between the front doors and the agent and domain layers (design Q3 A). Every dependency still points downward.

```text
trip_journal/
  main.py             FastAPI app factory, router registration, startup (database init)
  config.py           Built-in defaults and environment variables for settings
  pages/              Page routes, htmx fragments, Jinja2 templates, static/htmx.min.js
  api/                JSON routers: trips, days, notes, journal, chat, jobs, settings
  services/           One service per feature + the job runner (orchestration)
  agent/              LLM client, agent loop, tool registry and tools, agents, organizer, prompts/
  domain/             Pure functions and models: import schema, days, citations, grounding, journal merge
  data/               sqlite3 connection, schema.sql, repositories
  places/             Place lookup (Nominatim) with rate limit, cache and fallback
scripts/
  evaluate.py         In-process evaluation over the sample trips (design Q13 A)
evaluation/           Labelled notes, question list, manual-review records
sample_data/          Two synthetic trips (no real personal data)
tests/                unit/, agent/, api/, property/ (property-based tests kept separate)
```

## Layer Overview

| Layer | Package | Components |
|---|---|---|
| Presentation | `pages/`, `api/` | C01 Page Routes, C02 JSON API Routers |
| Orchestration | `services/` | C03 ImportService, C04 TripService, C05 OrganizerService, C06 JournalService, C07 ChatService, C08 SettingsService, C09 JobRunner |
| Agent | `agent/` | C10 LLM Client, C11 AgentLoop, C12 Tool Registry and Tools, C13 JournalAgent, C14 ChatAgent, C15 NoteOrganizer, C16 Prompt Library |
| Domain (pure) | `domain/` | C17 Import Schema and Validation, C18 Day Derivation, C19 Citations and Grounding, C20 Journal Merge |
| Data and external | `data/`, `places/` | C21 Database, C22 Repositories, C23 PlaceLookup |
| Tooling | `scripts/`, `evaluation/`, `sample_data/` | C24 Evaluation Runner, C25 Sample Data |

---

## Presentation

### C01 Page Routes (`pages/`)
- **Purpose**: The server-rendered UI that the personas use.
- **Responsibilities**:
  - Render pages: trip list and import, day timeline, journal view and editor, chat panel, settings
  - Return htmx fragments: job progress, suggestion review rows, paragraph edits, chat messages
  - Keep the chat conversation in the page and send it with each question (FR-7.2: never saved)
  - Rely on Jinja2 autoescape for all model text (NFR-3.4); show highlights for unsupported sentences with an icon and text, not color alone (FR-5.2)
- **Interface**: HTTP GET/POST routes returning HTML. Calls services only (design Q4 A).
- **Stories**: US-01 to US-20 (all user-facing stories)

### C02 JSON API Routers (`api/`)
- **Purpose**: The JSON front door over the same services, used by API tests, the evaluation script and any future client.
- **Responsibilities**:
  - Endpoints under `/api/...` for trips, days, notes and suggestions, journal, chat, jobs and settings
  - Validate every request body with a Pydantic model; map service errors to HTTP codes (422 validation, 404 not found, 409 conflict, 503 model unavailable, 429 model busy)
- **Interface**: FastAPI `APIRouter`s; dependencies injected through `Depends`.
- **Stories**: all stories (API equivalents); used by US-23

---

## Orchestration (`services/`)

### C03 ImportService
- **Purpose**: Turns an uploaded file into a stored trip.
- **Responsibilities**: enforce the size limit; parse and validate with the import schema (C17); reject a duplicate `trip_id` (FR-1.6); derive days (C18); store everything in one transaction; build the FTS5 index for notes.
- **Stories**: US-01, US-03, US-21

### C04 TripService
- **Purpose**: Reads and manages trips and days.
- **Responsibilities**: list trips; get and set the active trip; build the day timeline view (stops, notes, organized fields, photo metadata); delete a trip and everything that belongs to it after confirmation (FR-1.7).
- **Stories**: US-02, US-03, US-04, US-05

### C05 OrganizerService
- **Purpose**: Runs the note organizer and applies review decisions.
- **Responsibilities**: run the organizer for a day or the whole trip as a job; store suggestions as pending; accept, edit or reject one suggestion; accept all pending suggestions for a day; never change raw note text (FR-3.4).
- **Stories**: US-06, US-07, US-08

### C06 JournalService
- **Purpose**: Owns the journal request flow.
- **Responsibilities**: start generation or regeneration as a job; call JournalAgent (C13) for a draft; run the grounding check (C19); merge with user-owned paragraphs (C20); perform the `save_journal` step, which writes generated paragraphs only (FR-6.4); save the tool-call trace with the journal (design Q10 A); save user edits as user-owned and re-run grounding on them.
- **Stories**: US-09, US-10, US-11, US-12, US-13, US-20

### C07 ChatService
- **Purpose**: Owns the Q&A request flow.
- **Responsibilities**: start a question as a job, with the conversation supplied by the page; call ChatAgent (C14); run grounding with the "not in your records" exemption (FR-5.3); return the answer, flags and trace without storing them.
- **Stories**: US-14, US-15, US-16, US-20

### C08 SettingsService
- **Purpose**: One source of truth for settings.
- **Responsibilities**: resolve the model name, Ollama base URL and place-lookup switch in this order: saved value in SQLite, then environment variable, then built-in default (design Q11 A); save changes from the Settings page; report model availability (FR-10.3).
- **Stories**: US-17, US-18, US-19

### C09 JobRunner
- **Purpose**: Runs LLM work in the background so pages can poll progress (design Q5 A).
- **Responsibilities**: allow **one LLM job at a time** and refuse a second with a "model busy" error (design Q6 A); record the current step reported by the agent loop; keep the finished result or error for polling; keep jobs in memory only.
- **Stories**: US-09, US-14 (progress), US-06, US-19, US-20

---

## Agent (`agent/`)

### C10 LLM Client
- **Purpose**: The only component that talks to a model (design Q12 A).
- **Responsibilities**: an `LLMClient` protocol with one `chat()` method; `OllamaClient` uses the `openai` SDK against the configured base URL and model, with timeouts; `FakeLLMClient` returns scripted replies for tests (NFR-7.2); a health check reports whether Ollama is reachable and the model is installed.
- **Stories**: US-18, US-19; enables all agent tests

### C11 AgentLoop
- **Purpose**: The project's own tool-calling loop, shared by both agents (design Q1 A).
- **Responsibilities**: send messages and tool schemas; validate each tool call's arguments with the tool's Pydantic model before running it; return validation errors and unknown-tool errors to the model as tool results (US-20); report each step to a progress callback; stop at a final reply or after **8 steps**; return the final text and the full trace.
- **Stories**: US-09, US-14, US-20

### C12 Tool Registry and Tools
- **Purpose**: The read-only tools the agents may call.
- **Responsibilities**: register `list_day_stops`, `get_stop_notes`, `find_photos`, `search_notes` and `lookup_place`, each with a Pydantic argument model and a JSON schema; scope every call to the active trip through a tool context, so the model never passes a trip id (FR-7.1); return results as delimited JSON data with record ids (NFR-3.5); call repositories and PlaceLookup only, never raw SQL (NFR-6.3).
- **Note**: `save_journal` is **not** offered to the model. It is the save step inside JournalService (C06), so the model has no way to write data (FR-6.4, NFR-3.6).
- **Stories**: US-09, US-14, US-17

### C13 JournalAgent
- **Purpose**: Writes one day's draft.
- **Responsibilities**: build the journal prompt for the requested tone; run AgentLoop with all five tools; parse the final reply into slots (a `summary` slot and one slot per `stop_id`; design Q9 A), with a citation on every sentence (FR-4.6).
- **Stories**: US-09, US-13

### C14 ChatAgent
- **Purpose**: Answers one question in context.
- **Responsibilities**: build the chat prompt from the conversation so far and the new question; run AgentLoop with all five tools; require citations, and require the exact sentence "That is not in your records." when the data has no answer.
- **Stories**: US-14, US-15, US-16

### C15 NoteOrganizer
- **Purpose**: Suggests categories, fields and stops for raw notes (design Q2 A).
- **Responsibilities**: one structured LLM call per batch (one day). Stops and notes go in as delimited data; the reply is JSON validated into `NoteSuggestion` models. Suggestions that fail validation, or that reference unknown notes or stops, are dropped and reported. Extracted fields are in English (FR-3.5).
- **Stories**: US-06

### C16 Prompt Library (`agent/prompts/`)
- **Purpose**: Versioned prompt files (NFR-6.4).
- **Responsibilities**: one file each for the journal (with tone variants), chat and organizer prompts; a loader that returns a prompt by name and version; standard wording that tool results are data, never instructions.
- **Stories**: US-06, US-09, US-14

---

## Domain (`domain/`, pure functions)

### C17 Import Schema and Validation
- **Purpose**: Defines and checks the import file (design Q7 A).
- **Responsibilities**: Pydantic models with `extra="forbid"`: `TripFile` (`trip`, `stops[]`, `notes[]`, `photos[]`), with string ids in the file and references by those ids. Cross-record checks: unique ids, a note's `stop_id` must exist, end time not before start time, valid offsets and coordinates. Errors name the field and the record (FR-1.3).
- **Stories**: US-01, US-21

### C18 Day Derivation
- **Purpose**: Maps records to trip days (FR-2.1).
- **Responsibilities**: compute a record's local date from its UTC time and offset; group stops by the local date of their start; order each day's stops by start time.
- **Stories**: US-04

### C19 Citations and Grounding
- **Purpose**: Finds unsupported sentences (FR-5).
- **Responsibilities**: split text into sentences; extract `[stop:N]`, `[note:N]` and `[photo:N]` citations; flag sentences that cite nothing or cite ids outside the known set for the active trip; exempt the exact "That is not in your records." sentence in chat answers (FR-5.3); produce citation targets for links (FR-8.2).
- **Stories**: US-10, US-11, US-14, US-16

### C20 Journal Merge
- **Purpose**: Combines a new draft with the stored journal (FR-6.2).
- **Responsibilities**: by slot, keep every user-owned paragraph unchanged and replace only generated slots; report "nothing to regenerate" when all slots are user-owned. A pure function, and the main target for property-based invariant tests (PBT-03).
- **Stories**: US-13

---

## Data and External

### C21 Database (`data/db.py`, `data/schema.sql`)
- **Purpose**: The SQLite connection and schema.
- **Responsibilities**: open `data/trip.db` (or a path from settings, or a temporary path for tests and evaluation); create tables and the FTS5 note index on startup; enable foreign keys with cascading deletes; provide a transaction context.

### C22 Repositories (`data/repositories.py`)
- **Purpose**: All SQL lives here (NFR-6.3).
- **Responsibilities**: `TripRepository`, `StopRepository`, `NoteRepository` (including FTS5 search), `PhotoRepository`, `SuggestionRepository`, `JournalRepository` (paragraph slots with owner, plus the saved trace), `SettingsRepository` and `PlaceCacheRepository`. Every record stores its SQLite row id and its `source_id` from the import file (design Q8 A).

### C23 PlaceLookup (`places/`)
- **Purpose**: Reverse geocoding that respects the user's choice and the usage policy (FR-9).
- **Responsibilities**: if place lookup is off, return the imported name; otherwise check the cache, then call Nominatim with httpx (timeout, at most 1 request per second, identifying User-Agent), cache the result, and fall back to the imported name on any failure.
- **Stories**: US-17

---

## Tooling

### C24 Evaluation Runner (`scripts/evaluate.py`, `evaluation/`)
- **Purpose**: Measures the vision's success metrics (FR-11.3).
- **Responsibilities**: build the services in process against a temporary database (design Q13 A); import the sample trips; run the organizer, journals and questions; compare the results with `evaluation/` labels by file `source_id`; print the grounding rate, organizer accuracy, Q&A accuracy and timings next to their targets, together with the model name and the machine.
- **Stories**: US-22, US-23, US-24 (US-24's manual review records are kept in `evaluation/`)

### C25 Sample Data (`sample_data/`)
- **Purpose**: Two synthetic trips that cover every story's edge cases (FR-11.1).
- **Stories**: US-21
