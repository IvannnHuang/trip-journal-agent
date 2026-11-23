# Requirements: Trip Journal Agent

## Intent Analysis Summary

| Item | Value |
|---|---|
| **User request** | Build the product described in `docs/vision.md` and `docs/technical-environment.md` using AI-DLC. This session covers the Inception phase only. |
| **Request type** | New Project (greenfield) |
| **Request clarity** | Clear overall; the vision's open questions were settled through `requirement-verification-questions.md` and `requirement-clarification-questions.md` |
| **Scope estimate** | System-wide: a new local web application with an import pipeline, storage, an agent loop with tools, a grounding checker and several pages |
| **Complexity estimate** | Moderate |
| **Requirements depth** | Standard |

**Product in one sentence:** a local web app that imports one trip's records (stops, notes, photo metadata), organizes the notes with an LLM, writes a cited daily journal the user can edit, and answers questions about the trip. All of it runs on the user's laptop against a local Ollama model.

**Users** (from the vision): the trip logger (primary), the food and place reviewer, and the trip companion who asks questions but did not take notes.

---

## Functional Requirements

Each requirement lists its source: **V** = `docs/vision.md`, **T** = `docs/technical-environment.md`, **Qn** = verification question n, **C1** = clarification question 1.

### FR-1 Trip Import and Trip Management

| ID | Requirement | Source |
|---|---|---|
| FR-1.1 | The user imports one trip from a JSON file in the project's **own documented schema**: a trip, its stops (start and end time, coordinates, optional place name), notes (time, text, optional stop reference) and photo metadata (time, coordinates, optional file name). An optional route summary may be included in the JSON. | V, Q10 A |
| FR-1.2 | GPX files are **not** accepted. | Q11 A |
| FR-1.3 | Every import file is validated against a Pydantic model before anything is stored. Unknown fields are rejected, and files over 20 MB are rejected. Each error message names the field and the record that failed. | V, T |
| FR-1.4 | Times are stored as UTC ISO-8601 strings plus the local UTC offset; coordinates are WGS-84 decimal degrees. | T |
| FR-1.5 | The app stores **several trips**. The user picks the active trip; the timeline, note organizer, journals and Q&A all work on the active trip. | Q12 A |
| FR-1.6 | Importing a trip that already exists (same trip identifier) is **rejected** with a clear message that tells the user to delete the existing trip first. | Q12 A, C1 A |
| FR-1.7 | The user can **delete a trip**. A confirmation warns that the trip's journals and note decisions will also be deleted. To correct a trip, the user deletes it and imports the fixed file. | C1 A |

### FR-2 Day Timeline

| ID | Requirement | Source |
|---|---|---|
| FR-2.1 | A trip's days are derived from the **local date of each stop's start time**, using the UTC offset stored with the record. A stop that runs past midnight belongs to the day it started on. | Q13 A |
| FR-2.2 | Each day has a page that lists its stops in time order, with each stop's notes, photo count and photo metadata (time and location). The user can move between the days of the trip. | V, Q14 A |
| FR-2.3 | Photos are handled as **metadata only**; no images or thumbnails are shown. | Q14 A |

### FR-3 Note Organizer (LLM)

| ID | Requirement | Source |
|---|---|---|
| FR-3.1 | The organizer runs **only when the user asks**, either for one day or for the whole trip. It does not run on import. | Q8 C |
| FR-3.2 | For each raw note it suggests: a category (food / scene / logistics / feedback / other), extracted fields (dish, rating, tip; each only when present) and a stop to attach the note to. | V |
| FR-3.3 | The user reviews suggestions **one by one** (accept, edit or reject each) and can also **accept all** suggestions for a day. | Q9 B |
| FR-3.4 | Only accepted or edited suggestions become organized note data. The raw note text is never changed. | V |
| FR-3.5 | Notes in any language, including notes that mix languages, are understood. Extracted fields are written in English; original-language names (for example dish names) may be kept as short quotes. | Q2 A, Q15 B |

### FR-4 Daily Journal Agent (LLM and Tools)

| ID | Requirement | Source |
|---|---|---|
| FR-4.1 | On request, the agent writes a draft journal for one day. Structure: **a short day-summary paragraph, then one paragraph per stop in time order.** | V, Q1 C |
| FR-4.2 | The user picks a tone for each generation: **casual, concise or detailed**. | T, Q3 A |
| FR-4.3 | The journal is written in **English**. Short original-language phrases may be quoted where useful. | Q2 A |
| FR-4.4 | The agent gathers facts through tools rather than receiving the whole trip in its prompt. Tools: `list_day_stops(day)`, `get_stop_notes(stop_id)`, `find_photos(start, end)`, `search_notes(query)`, `lookup_place(lat, lon)`. | V, T |
| FR-4.5 | The agent loop is the project's own loop over the `openai` SDK. Tool arguments from the model are validated with Pydantic before a tool runs. The loop stops at a final answer or after **8 steps**. | T |
| FR-4.6 | Every generated sentence cites the records it is based on, in the form `[stop:N]`, `[note:N]` or `[photo:N]`. | V, T |
| FR-4.7 | While a journal is being generated, the page shows a **progress indicator with the agent's current step** (for example "calling list_day_stops…"). Output is **not streamed**. | Q20 B |

### FR-5 Grounding Check

| ID | Requirement | Source |
|---|---|---|
| FR-5.1 | Every sentence of a journal draft and of a Q&A answer is checked. A sentence is **unsupported** when it cites nothing, or when it cites a record id that does not exist in the active trip. | V, T |
| FR-5.2 | Unsupported sentences are **kept in the draft and highlighted** in the UI; the user decides whether to edit or delete them. The highlight does not rely on color alone. | Q4 A, Q23 A |
| FR-5.3 | A Q&A reply saying that the answer is not in the user's records is a valid reply and is not flagged as unsupported. | V |

### FR-6 Journal Editing, Saving and Regenerating

| ID | Requirement | Source |
|---|---|---|
| FR-6.1 | The user can edit any paragraph of a draft. A paragraph the user edits is marked **user-owned**. | V, Q6 A |
| FR-6.2 | Regenerating a journal rewrites only the generated paragraphs the user has not touched. User-owned paragraphs are kept exactly as written. | V, Q6 A |
| FR-6.3 | The latest draft and every user edit are **saved automatically** to SQLite. Only the current version of each day's journal is kept; there is no version history. | Q7 A |
| FR-6.4 | The agent's only write operation, `save_journal`, writes generated paragraphs only. It never writes user-owned paragraphs. | T |

### FR-7 Trip Q&A Agent (LLM and Tools)

| ID | Requirement | Source |
|---|---|---|
| FR-7.1 | A chat panel answers questions about the **active trip** by calling the same tools as the journal agent. Questions about other trips are not supported. | V |
| FR-7.2 | The chat is **multi-turn**: follow-up questions use the earlier messages. History is kept only while the page is open and is not saved. | Q16 A |
| FR-7.3 | Answers cite the records they use (FR-4.6) and go through the grounding check (FR-5). When the data has no answer, the reply says so ("not in your records") instead of guessing. | V |
| FR-7.4 | Answers are written in English (FR-4.3) and are not streamed. A progress indicator shows the current agent step (FR-4.7). | Q2 A, Q20 B |

### FR-8 Agent Transparency

| ID | Requirement | Source |
|---|---|---|
| FR-8.1 | For every journal draft and Q&A answer, the UI shows a **collapsible list of the tool calls** the agent made, with their arguments and the record ids each call returned. | V, Q17 A |
| FR-8.2 | Each citation in a journal or answer links to the record it cites. | Q17 A |

### FR-9 Place Lookup

| ID | Requirement | Source |
|---|---|---|
| FR-9.1 | `lookup_place(lat, lon)` reverse-geocodes a coordinate with OpenStreetMap Nominatim. | V, T |
| FR-9.2 | Place lookup is **off by default**; the user turns it on in a setting. | Q18 A |
| FR-9.3 | When place lookup is off or unreachable, the tool returns the place names from the import, and every feature keeps working. | V, T |
| FR-9.4 | Results are cached in SQLite. Requests follow the Nominatim usage policy: at most 1 request per second and an identifying User-Agent. | T |

### FR-10 Settings and LLM Availability

| ID | Requirement | Source |
|---|---|---|
| FR-10.1 | The model name, the Ollama base URL and the place-lookup on/off switch are settings, not hard-coded values. | T, Q18 A |
| FR-10.2 | Only Ollama is supported in the MVP; no hosted-provider option is built. Because the model and base URL are settings, a hosted provider can be added later. | T, Q19 A |
| FR-10.3 | When Ollama is not running or the model is not installed, the app still starts. Import, the timeline, trip deletion and journal editing keep working; the LLM features show a clear message explaining how to start Ollama or pull the model. | Q22 A |

### FR-11 Sample Data and Evaluation

| ID | Requirement | Source |
|---|---|---|
| FR-11.1 | Two **synthetic** trips of 3–4 days each, set in real public cities with invented people and notes. Some notes mix English and Chinese. No real personal data. | V, Q15 B |
| FR-11.2 | A hand-labelled set of at least 40 notes (correct category and stop), and a written list of at least 20 questions with expected answers, including questions that have no answer in the data. | V |
| FR-11.3 | An evaluation script runs over the sample trips and reports the grounding rate (exact citation check), note-organization accuracy and Q&A accuracy. | V, T |
| FR-11.4 | The "0 invented stop names, times or ratings" target is checked by a **team manual review** of the demo-trip journals. No LLM-as-judge is used. | Q5 C |

---

## Non-Functional Requirements

### NFR-1 Performance

| ID | Requirement | Source |
|---|---|---|
| NFR-1.1 | A day-journal draft is ready in ≤ 90 s and a Q&A answer in ≤ 30 s with the local model. | V |
| NFR-1.2 | These targets are measured on **the team's slowest laptop that will run the demo**. The laptop model and its memory are recorded with the measurement. | Q21 A |
| NFR-1.3 | Prompts stay small: the agent fetches only the records it needs through tools, and the loop is capped at 8 steps (FR-4.5). | V, T |

### NFR-2 Privacy

| ID | Requirement | Source |
|---|---|---|
| NFR-2.1 | Everything runs on the laptop. The server binds to `127.0.0.1` only, and no hosted LLM is used. | T, Q19 A |
| NFR-2.2 | The only outbound call is the optional place lookup, which is off by default (FR-9.2). | T, Q18 A |
| NFR-2.3 | Only synthetic sample data is committed. The local database folder `data/` and `.env` are git-ignored. | T |

### NFR-3 Security

The Security Baseline extension is **disabled** for this project (see Extension Configuration). The security basics in `technical-environment.md` remain project requirements.

| ID | Requirement | Source |
|---|---|---|
| NFR-3.1 | No authentication: single user on localhost. | T |
| NFR-3.2 | Every import file and request body is a Pydantic model (FR-1.3). | T |
| NFR-3.3 | `eval()`, `exec()` and `pickle` are never used on imported data. | T |
| NFR-3.4 | LLM output is untrusted: tool arguments are validated before tools run, and model text is HTML-escaped by Jinja2 autoescape before display. | T |
| NFR-3.5 | Defense against prompt injection: note text reaches the model only as data inside clearly delimited tool results, never as instructions. Tools cannot reach the file system or the network, except the place lookup. | T |
| NFR-3.6 | All tools are read-only except `save_journal` (FR-6.4). | T |

### NFR-4 Reliability

The Resiliency Baseline extension is **disabled** for this project. The requirements below come from the vision, the technical environment and the team's answers.

| ID | Requirement | Source |
|---|---|---|
| NFR-4.1 | The app degrades gracefully when Ollama or the place lookup is unavailable (FR-9.3, FR-10.3). | Q22 A, T |
| NFR-4.2 | A tool call with invalid arguments, a failing tool or an agent that reaches the step limit ends with a clear error message to the user. The server keeps running and no data is corrupted. | V, T |
| NFR-4.3 | User-edited journal text is never lost by a regenerate (100%, FR-6.2) or by an autosave (FR-6.3). | V |
| NFR-4.4 | Deleting a trip requires a confirmation (FR-1.7). | C1 A |

### NFR-5 Usability and Accessibility

| ID | Requirement | Source |
|---|---|---|
| NFR-5.1 | The pages use semantic HTML, forms and buttons work from the keyboard, text has readable contrast, and highlighted text is not marked by color alone. No formal WCAG audit is required. | Q23 A |
| NFR-5.2 | Error messages (import validation, missing model, agent failure) say what went wrong and what the user can do next. | V, Q22 A |

### NFR-6 Maintainability and Technology Constraints

| ID | Requirement | Source |
|---|---|---|
| NFR-6.1 | The stack is Python 3.12+ and uv, with FastAPI and Pydantic v2, Jinja2 and htmx (no JavaScript build step), SQLite through `sqlite3` with FTS5 for note search, the `openai` SDK pointed at Ollama, httpx and uvicorn. | T |
| NFR-6.2 | The libraries listed under "Do NOT Use" in `technical-environment.md` are not used (for example LangChain, vector databases, `requests`, SQLAlchemy, React and Streamlit). | T |
| NFR-6.3 | Layers call downward only (`api/pages → agent/domain → data`). Tools call repositories; the agent loop never runs raw SQL. | T |
| NFR-6.4 | Prompts live in versioned files under `trip_journal/agent/prompts/`. | T |
| NFR-6.5 | ruff (lint and format) and mypy pass before any merge. | T |

### NFR-7 Testability

| ID | Requirement | Source |
|---|---|---|
| NFR-7.1 | pytest unit tests cover the domain functions and tools with at least 80% line coverage (pytest-cov). | T |
| NFR-7.2 | Agent tests use a fake LLM client that returns scripted tool calls. They cover the loop, the step limit, argument validation and error handling, with no real model needed. | T |
| NFR-7.3 | API tests use FastAPI `TestClient` and cover each endpoint's success and error cases. | T |
| NFR-7.4 | Property-based testing applies in **Partial** mode (rules PBT-02, PBT-03, PBT-07, PBT-08 and PBT-09 are blocking). Likely candidates are round-trip tests for import parsing and serialization (PBT-02), and invariant tests for the grounding check and the journal merge, including "user-owned paragraphs always survive a regenerate" (PBT-03). The framework choice (Hypothesis is the recommended Python option) is made at NFR Requirements (PBT-09). | Extension opt-in |

---

## Success Metrics (from the vision, with how each is measured)

| Metric | Target | How it is measured |
|---|---|---|
| Journal grounding | ≥ 95% of journal sentences cite at least one existing record; 0 invented stop names, times or ratings | Exact citation check in the evaluation script, plus a team manual review of the demo journals (FR-11.3, FR-11.4) |
| Note organization accuracy | ≥ 85% correct category and stop | Evaluation script against the ≥ 40 hand-labelled notes (FR-11.2) |
| Q&A accuracy | ≥ 80% correct; questions with no answer in the data get "not in your records" | Evaluation script against the ≥ 20 written questions (FR-11.2) |
| Speed | Journal ≤ 90 s, Q&A answer ≤ 30 s | Timed on the team's slowest demo laptop (NFR-1.2) |
| User edits respected | 100% of user-edited text survives a regenerate | Example-based and property-based tests of the journal merge (NFR-7.4) |

---

## Out of Scope for the MVP

These come from the vision, with the team's answers added: mobile app and live GPS tracking; stop detection from raw GPS; GPX import (Q11); speech-to-text; photo content understanding and showing photos (Q14); recap videos; trip recommendations; Q&A across several trips; accounts, multiple users and cloud hosting; hosted LLM providers (Q19); HTML/PDF export and sharing; map view; journal version history (Q7); saved chat history (Q16); streaming output (Q20); an LLM-as-judge (Q5).

---

## Assumptions and Items Carried Forward

| Item | Where it is resolved |
|---|---|
| The exact JSON schema (field names, how a trip is identified, how notes reference stops) | Application Design / Functional Design |
| How settings are stored and changed (environment variables, a settings page, or both) | Application Design |
| What a stop paragraph says when the stop has no notes | Functional Design |
| Which local model gives reliable tool calling on the team's laptops (`qwen3:8b` first; test a second model early) | Construction (early spike), recorded in NFR Requirements |
| Which laptop is the team's slowest demo laptop | Recorded when performance is measured (NFR-1.2) |

---

## Decision Record

| Question | Answer | Decision |
|---|---|---|
| Q1 Journal structure | C | Day-summary paragraph, then one paragraph per stop |
| Q2 Output language | A | English; short original-language quotes allowed |
| Q3 Tones | A | Casual, concise, detailed |
| Q4 Unsupported sentence | A | Keep and highlight |
| Q5 Grounding measurement | C | Exact citation check plus team manual review |
| Q6 Edit tracking | A | Paragraph level; edited paragraphs are user-owned |
| Q7 Saving | A | Autosave; current version only |
| Q8 Organizer trigger | C | On demand, for one day or the whole trip |
| Q9 Organizer review | B | One by one, plus accept all for a day |
| Q10 Import format | A | Own documented JSON schema |
| Q11 GPX | A | Not supported |
| Q12 Trips / re-import | A | Several trips; re-import rejected |
| C1 Correcting a trip | A | Delete trip (with confirmation), then re-import |
| Q13 Day definition | A | Local date of the stop's start time |
| Q14 Photos | A | Metadata only |
| Q15 Sample trips | B | Real cities, invented content, some mixed English and Chinese notes |
| Q16 Q&A chat | A | Multi-turn; history kept only in the open page |
| Q17 Agent visibility | A | Collapsible tool-call list; citations link to records |
| Q18 Place lookup default | A | Off by default |
| Q19 Hosted LLM | A | Not built; Ollama only |
| Q20 Streaming | B | No streaming; progress indicator with the current agent step |
| Q21 Speed hardware | A | The team's slowest demo laptop |
| Q22 No Ollama | A | App starts; LLM features show guidance |
| Q23 Accessibility | A | Basic accessibility |
| Security Baseline | B | Disabled |
| Resiliency Baseline | B | Disabled |
| Property-Based Testing | B | Partial mode |

---

## Key Requirements Summary

- **Core value:** a cited, editable daily journal and a cited Q&A over one imported trip. A per-sentence citation check flags anything unsupported, and regenerating never overwrites user text.
- **Agent design:** the project's own tool-calling loop (5 read-only tools plus `save_journal`, 8-step cap, Pydantic-validated arguments) over a local Ollama model.
- **Privacy first:** localhost only, no hosted LLM, place lookup off by default, synthetic sample data only.
- **Quality gates:** coverage ≥ 80%, tests with a fake LLM client, API tests, partial property-based testing, ruff and mypy, and an evaluation script for the vision's success metrics.
