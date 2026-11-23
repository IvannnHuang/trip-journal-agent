# Units of Work

**Source**: `aidlc-docs/inception/plans/unit-of-work-plan.md` (approved), `application-design.md` (approved), `stories.md` (approved)
**Deployment model**: one local FastAPI application (`trip_journal`) in one repository. Each unit of work is a group of **modules** inside that application, not a separately deployed service (plan Q10 A).
**Approach**: a shared foundation unit, then feature slices that each deliver their own service, agent part, pages and API routes (plan Q1 B, Q4 A). There are exactly six units (plan Q2 B).

## Summary

| Unit | Name | Primary stories | Owner | Reviewer | Size |
|---|---|---|---|---|---|
| U1 | Foundation | US-17, US-18, US-19, US-20 | Zarif Karim | Ivan Huang | L |
| U2 | Import and Timeline | US-01, US-02, US-03, US-04 | Ivan Huang | Edwin Chen | M |
| U3 | Note Organizer | US-05, US-06, US-07, US-08 | Edwin Chen | Zarif Karim | M |
| U4 | Daily Journal | US-09, US-10, US-11, US-12, US-13 | Zarif Karim | Edwin Chen | L |
| U5 | Trip Q&A | US-14, US-15, US-16 | Ivan Huang | Zarif Karim | M |
| U6 | Sample Data and Evaluation | US-21, US-22, US-23, US-24 | Edwin Chen | Ivan Huang | M |

The owners and reviewers follow plan Q6 A and Q7 A. Each member owns two units and reviews two units owned by others. Zarif, as technical lead, owns the two L units, and U1 comes first, so the team can rebalance at the start of Construction if needed.

---

## U1: Foundation

- **Purpose**: The shared technical base that every feature unit builds on: storage, the LLM client, the agent loop with its tools, grounding, settings, background jobs and the app shell.
- **Owner / reviewer**: Zarif Karim / Ivan Huang
- **First task: model spike** (plan Q8 A). Before the feature units depend on the agent loop, test tool calling with `qwen3:8b` and one alternative tool-capable model on **every teammate's laptop**. Record the success rate on a few scripted questions, the time per step and the memory use. The result decides the default model in NFR Requirements.
- **Components**:
  - C08 SettingsService
  - C09 JobRunner
  - C10 LLM Client (`LLMClient` protocol, `OllamaClient`, `FakeLLMClient`)
  - C11 AgentLoop
  - C12 Tool Registry and the five tools
  - C16 Prompt Library (the loader and the shared "tool results are data" wording)
  - C19 Citations and Grounding
  - C21 Database
  - C22 core repositories (`TripRepository`, `StopRepository`, `NoteRepository` with FTS5 search, `PhotoRepository`, `SettingsRepository`, `PlaceCacheRepository`)
  - C23 PlaceLookup
  - Shared parts of C01 and C02: `main.py`, `config.py`, the base layout template, the job-progress poller fragment, the model-status banner, the "How this was made" trace fragment, the citation-link and unsupported-highlight macros, the Settings page and API, and the jobs API
- **Modules**:
  - `trip_journal/main.py`, `config.py`
  - `data/db.py`, `data/schema.sql` (core tables)
  - `data/repositories.py` (core repositories)
  - `agent/llm.py`, `agent/loop.py`, `agent/tools.py`, `agent/prompts/__init__.py`
  - `domain/grounding.py`
  - `services/settings.py`, `services/jobs.py`, `services/errors.py`
  - `places/lookup.py`
  - `api/settings.py`, `api/jobs.py`
  - `pages/settings.py`
  - `pages/templates/base.html`, `pages/templates/_partials/*`
  - `pages/static/htmx.min.js`
- **Provides to other units**: repositories, `ToolContext` and the default registry, `AgentLoop`, `FakeLLMClient`, `check_text` and `find_unsupported_sentences`, `JobRunner`, `SettingsService.model_status()`, the shared UI fragments and the error types.
- **Definition of done**:
  - US-17 to US-20 accepted
  - Agent tests with `FakeLLMClient` cover the step limit, invalid arguments and unknown tools
  - Grounding has example-based tests and property-based invariant tests (PBT-03)
  - The spike results are recorded
  - ruff and mypy pass; coverage of U1's domain functions and tools is at least 80%

## U2: Import and Timeline

- **Purpose**: Get a trip into the app and show its days. This is the first thing every persona does.
- **Owner / reviewer**: Ivan Huang / Edwin Chen
- **Components**:
  - C03 ImportService
  - C04 TripService
  - C17 Import Schema and Validation
  - C18 Day Derivation
  - C25 (the **minimal** sample trip only, plan Q5 C: one day, about 4 stops, 8 notes and 10 photos, including one stop past midnight and one note in mixed language)
  - C01 and C02 for trips and days
- **Modules**:
  - `domain/import_schema.py`, `domain/days.py`
  - `services/imports.py`, `services/trips.py`
  - `api/trips.py`, `api/days.py`
  - `pages/trips.py`, `pages/days.py`, with their templates
  - `docs/import-format.md` (the documented schema)
  - `sample_data/minimal_trip.json`
  - `tests/fixtures/` (loader for the minimal trip)
- **Provides to other units**: stored trips and days, the day-timeline page with a slot for each stop's notes (U3 fills in organized fields), and the minimal sample trip as a shared test fixture.
- **Definition of done**:
  - US-01 to US-04 accepted
  - Import validation has example-based tests and a property-based round-trip test (PBT-02); day derivation has invariant tests (PBT-03)
  - API tests cover 422, 409 and 404
  - ruff and mypy pass; coverage is at least 80%

## U3: Note Organizer

- **Purpose**: Turn raw notes into reviewed, structured reviews attached to the right stop.
- **Owner / reviewer**: Edwin Chen / Zarif Karim
- **Components**:
  - C05 OrganizerService
  - C15 NoteOrganizer
  - `SuggestionRepository` (part of C22) and its table in `schema.sql`
  - The organizer prompt (part of C16)
  - C01 and C02 for organizing and reviewing
  - The organized-fields display on timeline stops (US-05)
- **Modules**:
  - `agent/organizer.py`
  - `agent/prompts/organizer.md`
  - `services/organizer.py`
  - `data/repositories.py` (`SuggestionRepository` section)
  - `api/notes.py`
  - `pages/organizer.py`, with templates and the stop review fragment
- **Definition of done**:
  - US-05 to US-08 accepted
  - Tests with `FakeLLMClient` cover valid suggestions, invalid JSON, unknown note ids and the "instruction-like note" case
  - Accept-all has tests showing it leaves edited and rejected suggestions alone
  - ruff and mypy pass; coverage is at least 80%

## U4: Daily Journal

- **Purpose**: The core value of the product: a cited, editable daily journal whose user edits survive every regenerate.
- **Owner / reviewer**: Zarif Karim / Edwin Chen
- **Components**:
  - C06 JournalService
  - C13 JournalAgent
  - C20 Journal Merge
  - `JournalRepository` (part of C22) and its tables
  - The journal prompts with tone variants (part of C16)
  - C01 and C02 for the journal
- **Modules**:
  - `agent/journal.py`
  - `agent/prompts/journal_*.md`
  - `domain/journal_merge.py`
  - `services/journal.py`
  - `data/repositories.py` (`JournalRepository` section)
  - `api/journal.py`
  - `pages/journal.py`, with templates
- **Definition of done**:
  - US-09 to US-13 accepted
  - The merge has property-based tests showing user-owned paragraphs are never changed and every slot is kept (PBT-03), plus example tests for the three regenerate scenarios
  - Scripted agent tests cover a full draft and a step-limit failure
  - The ≤ 90 s target is checked on the slowest demo laptop
  - ruff and mypy pass; coverage is at least 80%

## U5: Trip Q&A

- **Purpose**: Plain-language questions about the active trip, with sourced answers and an honest "not in your records".
- **Owner / reviewer**: Ivan Huang / Zarif Karim
- **Components**:
  - C07 ChatService
  - C14 ChatAgent
  - The chat prompt (part of C16)
  - C01 and C02 for chat (the chat panel keeps the conversation in the page)
- **Modules**:
  - `agent/chat.py`
  - `agent/prompts/chat.md`
  - `services/chat.py`
  - `api/chat.py`
  - `pages/chat.py`, with the chat panel template and fragments
- **Definition of done**:
  - US-14 to US-16 accepted
  - Scripted agent tests cover a cited answer, a follow-up that uses history, the "not in your records" exemption and a trip-scope check
  - The ≤ 30 s target is checked on the slowest demo laptop
  - ruff and mypy pass; coverage is at least 80%

## U6: Sample Data and Evaluation

- **Purpose**: Show the vision's success metrics on safe, synthetic data.
- **Owner / reviewer**: Edwin Chen / Ivan Huang
- **Components**: C24 Evaluation Runner; C25 (the **two full** sample trips with every edge case from US-21)
- **Modules**:
  - `sample_data/trip_*.json`
  - `evaluation/note_labels.json`, `evaluation/questions.json`, `evaluation/manual_review/`
  - `scripts/evaluate.py`
- **Definition of done**:
  - US-21 to US-24 accepted
  - At least 40 labelled notes and at least 20 questions, agreed by the team
  - The script prints every metric next to its target, with the model, the prompt version and the machine
  - The manual review of the demo journals is recorded
- **Timing**: the sample trips and labels can start as soon as U2's import format is fixed. The script runs once U3, U4 and U5 are merged.

---

## Code Organization Strategy (greenfield)

One package, `trip_journal/`, at the repository root, following `components.md` (plan Q10 A). Application code never goes in `aidlc-docs/`. Owners are marked by unit.

```text
pyproject.toml, uv.lock                      U1
trip_journal/
  main.py, config.py                         U1
  pages/
    templates/base.html, _partials/          U1
    static/htmx.min.js                       U1
    settings.py                              U1
    trips.py, days.py (+ templates)          U2
    organizer.py (+ templates)               U3
    journal.py (+ templates)                 U4
    chat.py (+ templates)                    U5
  api/
    settings.py, jobs.py                     U1
    trips.py, days.py                        U2
    notes.py                                 U3
    journal.py                               U4
    chat.py                                  U5
  services/
    settings.py, jobs.py, errors.py          U1
    imports.py, trips.py                     U2
    organizer.py                             U3
    journal.py                               U4
    chat.py                                  U5
  agent/
    llm.py, loop.py, tools.py                U1
    prompts/__init__.py                      U1
    organizer.py, prompts/organizer.md       U3
    journal.py, prompts/journal_*.md         U4
    chat.py, prompts/chat.md                 U5
  domain/
    grounding.py                             U1
    import_schema.py, days.py                U2
    journal_merge.py                         U4
  data/
    db.py, schema.sql (core tables)          U1   (U3 and U4 add their tables)
    repositories.py (core repositories)      U1   (U3 and U4 add their repositories)
  places/
    lookup.py                                U1
docs/import-format.md                        U2
sample_data/minimal_trip.json                U2
sample_data/trip_*.json                      U6
evaluation/                                  U6
scripts/evaluate.py                          U6
tests/
  fixtures/                                  U2 (minimal trip), U6 (full trips)
  unit/       test_<module>.py per unit
  agent/      scripted FakeLLMClient tests (U1, U3, U4, U5)
  api/        TestClient tests per router
  property/   property-based tests, kept separate from example tests
```

**Shared files with several editors** (`schema.sql`, `repositories.py`): each unit adds its own clearly marked section in its own pull request, and the reviewer checks that the existing sections are untouched.

**Working method** (README collaboration plan, plan Q3 A):
- One branch per unit
- A pull request reviewed by the unit's reviewer before merging
- ruff, mypy and pytest must pass before merging
- Feature units develop against U1's interfaces, `FakeLLMClient` and the U2 minimal trip, so they don't wait for the real model

## Construction Stages per Unit (from `execution-plan.md`)

| Unit | Functional Design | NFR Requirements | NFR Design | Code Generation |
|---|---|---|---|---|
| U1 | Execute | Execute (includes model choice from the spike; PBT framework, PBT-09) | Execute (step cap, timeouts, one job at a time, rate limit and cache, degrading without Ollama) | Execute |
| U2 | Execute | Execute | Expected to skip (no NFR patterns beyond validation); confirmed at NFR Requirements | Execute |
| U3 | Execute | Execute | Expected to skip; confirmed at NFR Requirements | Execute |
| U4 | Execute | Execute (90 s budget) | Decided at NFR Requirements | Execute |
| U5 | Execute | Execute (30 s budget) | Decided at NFR Requirements | Execute |
| U6 | Execute | Execute | Expected to skip | Execute |

Infrastructure Design is skipped for every unit (local only). Build and Test runs once, after all units.
