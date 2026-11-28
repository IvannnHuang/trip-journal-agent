# U4 Daily Journal - Code Generation Plan

**Unit**: U4 Daily Journal (owner Zarif Karim, reviewer Edwin Chen)
**Stories**: US-09 cited day journal, US-10 unsupported sentences highlighted, US-11 how a draft was built, US-12 edit a paragraph, US-13 regenerate without losing edits (`aidlc-docs/inception/application-design/unit-of-work-story-map.md`, U4 rows); US-20 failure display (U1 story, U4 page)
**Inputs**: `construction/u4-daily-journal/functional-design/` (4 files: BL-1..BL-10, JR-*, IC-1..IC-7, P-1..P-7), `construction/u4-daily-journal/nfr-requirements/` (2 files: U4-NFR-*, N-1..N-9, §10 FD changes, P-8), U3 code summary, existing code under `trip_journal/` and `tests/`
**Status**: Part 1 written 2026-11-28T00:16:31Z; approved by owner 2026-11-28T00:18:55Z ("Approve, start Part 2"). This plan is the single source of truth for Part 2.
**Layout**: monolith package `trip_journal/` + `tests/` (U1 D-1). No new runtime or dev dependency (U4-NFR-M.4). Schema addition: tables `journals`, `journal_paragraphs`.

Legend: **[U1]** / **[U2]** / **[U3]** = the step edits a file that unit created (modify in place). Every other path is new. **Who**: `Codex` = implemented by Codex in its own worktree via the `codex` skill (default implementer, owner rule); `Claude` = done in this main chat. Claude reviews every Codex diff, re-runs the key tests and merges only after owner OK.

## Unit context

| Item | Value |
|---|---|
| Depends on | U1 `AgentLoop`, `ToolRegistry` + five tools, `LLMClient` / `FakeLLMClient`, `JobRunner` (per-job limit, U3 D-4), `PromptLibrary`, `grounding.check_text`, error mapping, job fragment and `JobView` registry; U2 `TripService.get_day`, day page, `DaySummary`; U3 `organizer.md`, `note_item.html` review rows |
| Owns | tables `journals`, `journal_paragraphs`; `JournalRepository`; `JournalAgent`; `JournalService`; journal API, page and fragment routes |
| Interfaces | IC-1..IC-7 (domain-entities §7) plus D-1..D-14 below |
| Used later by | U5 (trace fragment, citation panel pattern), U6 (demo journals, US-24) |

## Deviations and decisions

| ID | Item | Decision | Why |
|---|---|---|---|
| D-1 | `model_busy` status | Keep U1's HTTP **429** for `ModelBusyError`; FD JR-P4 "409" is the same text slip as U3 D-5. Page text unchanged ("Another job is running…") | U1 tests pin 429 |
| D-2 | **[U1]** `AgentLoop` (N-2) | New optional `reasoning_effort: str \| None = None` and `request_timeout_s: float \| None = None`; `_call` passes both to `llm.chat`. Defaults `None` keep every U1/U3 caller byte-identical. Journal sets `call_timeout_s = request_timeout_s = 300.0`. No "initial history" parameter: `run(messages=...)` already takes the step-0 block | Smallest change; same SDK-backstop fix as U3 D-3 |
| D-3 | **[U1]** `ToolCallRecord` | Gains `group: str \| None = None` (`"prefetch"`, `"part 1"`…, `"summary"`), default `None`, so old `trace_json` still validates. Step-0 records have `step=0, group="prefetch"` | JR-TR1 step groups; backward compatible |
| D-4 | Prompt composition (IC-6) | `JournalAgent` builds `get("journal") + "\n\n" + get("journal_tone_<tone>", shared=False)`; summary call adds `get("journal_summary", shared=False)`. `PromptLibrary.get(name, tone=)` is **not** used (it replaces the base file instead of appending) | IC-6, JR-T2 |
| D-5 | Repository file | `JournalRepository` and `StoredJournal` in new `trip_journal/data/journals.py`, exposed as `Repositories.journals` | U3 precedent (`data/suggestions.py`) keeps `repositories.py` from growing |
| D-6 | Chunk plan before the job (N-3, N-6) | `JournalService` computes the chunk plan from the database with the same `truncate_text` the tool uses, so the job limit `min(300 × planned_calls, 1800)` is known before `JobRunner.start`. `JournalAgent` still runs step 0 through the registry for history and trace. A test asserts the plan's per-stop char counts equal the step-0 tool results | Job limit needs the plan first |
| D-7 | Pre-fetch history (N-1) | Per chunk: user message, then one assistant message with synthetic `tool_calls` (`prefetch-0` `list_day_stops`, `prefetch-<n>` `get_stop_notes` for that chunk's stops), then one `tool` message per result built by `registry.execute` (so `wrap_tool_result` + `_shared_tool_data.md` cover them, U4-NFR-SP.1). Trace holds every step-0 call once | N-1 |
| D-8 | Per-run grounding (N-5) | `run_ids` = union of `returned_ids` in the stored trace; generated paragraphs `check_text(text, run_ids, allow_not_in_records=False)`, user paragraphs the same with `TripRepository.known_citation_ids`. Computed on read only | U4-NFR-G.1, JR-G3 |
| D-9 | Job kind and result | Job kind `journal`; `JobView("journal/result.html")` registered in `main.py`; the result fragment carries the new `#journal-body` and the "Draft ready" live text | BL-9, U3 job fragment reuse |
| D-10 | Timeline badge (JR-UI4) | **[U2]** `DayView` gains `journal_exists: bool`, filled by `TripService.get_day` via `JournalRepository.exists` (one query) | Smallest U2 change |
| D-11 | Page JS | New `trip_journal/pages/static/journal.js` (no build step): draft swap that skips open / dirty editors (JR-S4), `visibilitychange` keepalive save (JR-S5), focus moves (JR-UI2), citation panel Escape (JR-C2). Everything else is htmx attributes | FD §3 |
| D-12 | Notes without a stop | Not pre-fetched (open item in NFR §9 stays open, recorded in code summary); they reach the model only through `search_notes` | Owner kept it non-blocking |
| D-13 | Progress text | One chunk: BL-9 texts; chunked: U4-NFR-U.1 texts ("Loading the day's records…", "Part i of n, step k of 8: <tool>", "Part i of n: writing…", "Writing the summary…", "Saving…") | U.1 |
| D-14 | JR-CI1 tip language | `organize.md` tip rule becomes "a short phrase quoted from the note (original language allowed), empty if none"; the English-only line keeps `dish` in English only. Rating examples add "9/10 becomes 5" | JR-CI1; the old English-only rule conflicts with quoting |
| D-15 | Days with > 50 stops | No pagination of `list_day_stops` (U1 50-record cap kept); stop citations past the cap may show unsupported in generated paragraphs; accepted known limit, recorded in the code summary. Decided by Claude 2026-11-28 after Codex C1 raised it (small, reversible) | U4 envelope ≤ 50 stops/day (reference trip ~21/day) |
| D-16 | Rows for stops no longer in the day | `get_journal` shows only slots in the current `slot_order`; rows for vanished stops stay stored but hidden (not deleted, reversible). Also: citation ids capped at 18 digits in `CITATION_RE` [U1] (huge ids broke `int()`), and `start_generation` re-runs BL-1 steps 1-4 after the model-status await. From the C1 Codex review; owner chose hide on read 2026-11-28 | Codex review findings 1-3 |

## Steps

### A. Data
- [x] 1. **[U1]** `trip_journal/data/schema.sql` - U4 section after the U3 section: `journals` and `journal_paragraphs` exactly as domain-entities §5 (CHECKs, PK, FK cascade), `CREATE TABLE IF NOT EXISTS`. *(Codex, C1)*
- [x] 2. `trip_journal/data/journals.py` - `StoredJournal`, `JournalRepository`: `get`, `exists`, `save_generated(trip_id, day, order, draft_slots, tone, trace, prompt_version, model_name) -> MergeResult` (one `BEGIN IMMEDIATE`: re-read owners, `merge_journal`, INSERT missing rows, `UPDATE … WHERE owner = 'generated'`, rewrite positions JR-SL3, upsert `journals`; JR-S1), `save_user_edit(trip_id, day, slot, text) -> Paragraph` (exact compare, text + owner in one transaction, touch `updated_at`, no write when unchanged; JR-O1, JR-O2). **[U1]** `data/repositories.py` - `Repositories.journals` (D-5). Trace stored with Pydantic dump / validate. *(Codex, C1)* — US-12, US-13

### B. U1 edits
- [x] 3. **[U1]** `trip_journal/config.py` - `JOURNAL_CALL_TIMEOUT_S = 300.0`, `JOURNAL_JOB_TIMEOUT_PER_CALL_S = 300.0`, `JOURNAL_JOB_TIMEOUT_CAP_S = 1800.0`, `JOURNAL_CHUNK_MAX_STOPS = 6`, `JOURNAL_CHUNK_MAX_CHARS = 4000`, `JOURNAL_REASONING_EFFORT = "none"`, `JOURNAL_MAX_PARAGRAPH_CHARS = 5000` (N-6, JR-V2). *(Codex, C1)*
- [x] 4. **[U1]** `trip_journal/agent/loop.py` - D-2, D-3. *(Codex, C1)*
- [x] 5. **[U1]** `trip_journal/services/errors.py` - `NOT_FOUND_MESSAGES` for `journal_not_found`, `slot_not_found`, `day_not_found` if missing; `ParagraphTooLongError` 422 `invalid_edit` "Paragraph is too long (max 5000 characters)."; `NoRecordsError` 422 `no_records` "No records for this day."; `to_user_facing` maps both. *(Codex, C1)*

### C. Domain and agent
- [x] 6. `trip_journal/domain/journal_merge.py` - pure: `Slot`, `Owner`, `Tone`, `Paragraph`, `MergeResult`, `stop_slot`, `parse_slot`, `slot_safe` (`:` → `-`), `slot_order`, `slots_to_write`, `merge_journal` (JR-M1..M6), `mark_user_edit` (JR-O1). *(Codex, C1)* — US-13
- [x] 7. `trip_journal/agent/prompts/journal.md` (version header; role, records pre-loaded N-8, slot rule, user text as context only, per-sentence citation rule with a two-sentence worked example G.4, do-not-invent, language of the notes), `journal_tone_casual.md` (2-4 sentences), `journal_tone_concise.md` (1-2), `journal_tone_detailed.md` (4-6), `journal_summary.md` (summary call: write only `## summary` from the given paragraphs, keep their citations; N-4). *(Claude: prompt wording drives grounding quality)* — US-09
- [x] 8. `trip_journal/agent/journal.py` - `DroppedHeading`, `JournalDraft`, `ChunkPlan`, `chunk_stops(stops_with_chars, max_stops, max_chars)` (pure, greedy, a stop never split; N-3, P-8), `parse_journal_output(text, requested, user_owned)` (BL-3, `<think>` stripped, JR-R1..R3, drop log counts only), `build_prefetch(...)` (D-7), `JournalAgent.write_day(context, day, tone, plan, slots_to_write, user_paragraphs, stored_paragraphs, on_progress)`: step 0 → one `AgentLoop(max_steps=8, reasoning_effort="none", call_timeout_s=request_timeout_s=300)` run per chunk that has a slot to write → summary call when ≥ 2 chunks (N-4) → one merged `JournalDraft` (N-7); any `step_limit` / `ModelCallError` fails the whole run (U4-NFR-R.2); success needs ≥ 1 slot across chunks (R.3); timing and L.1 log lines with `perf_counter` (N-9). *(Codex, C1)* — US-09, US-11

### D. Services and wiring
- [x] 9. `trip_journal/services/journal.py` - `JournalService`: `start_generation(trip_id, day, tone) -> JobRef | NothingToRegenerate` (BL-1 order exactly; job limit `min(300 × planned_calls, 1800)` D-6; job work = agent run + "Saving…" + `save_generated`, message lines JR-R4 / JR-F3), `get_journal(trip_id, day) -> JournalView` (BL-7, headings, `state`, `SentenceView` with escaped text + citation buttons, D-8 grounding, `unsupported_count` JR-G2), `edit_paragraph(trip_id, day, slot, text)` (BL-5, JR-V1, JR-V2, allowed during a job JR-S3), `get_citation(trip_id, kind, id) -> CitationTarget` (BL-8, JR-C1), log line for edits (`slot`, `changed`). View models `SentenceView`, `ParagraphView`, `JournalView`, `CitationTarget`, `NothingToRegenerate` in **[U2]** `trip_journal/domain/views.py`. *(Codex, C1)* — US-09..US-13
- [x] 10. **[U2]** `trip_journal/services/trips.py` + `domain/views.py` - D-10. **[U1]** `api/deps.py` - `AppState.journal`; **[U1]** `main.py` - build `JournalService` (uses `llm_factory`, `PromptLibrary`), register `JobView` D-9, include routers. *(Codex, C1)*

### E. API
- [x] 11. `trip_journal/api/journal.py` - GET / POST `/api/trips/{id}/days/{day}/journal` (body `{tone}` `extra="forbid"`, JR-V3 422; 202 `JobRef`, 200 `{nothing_to_regenerate: true, message}`, 404, 422 `no_records`, 429, 503), PUT `/api/trips/{id}/days/{day}/journal/paragraphs/{slot}` (body `{text}`; 200 paragraph view + `unsupported_count`; 404, 422). htmx requests (`HX-Request`) get fragments, other callers JSON (U3 pattern). *(Codex, C1)*

### F. Pages, templates, static
- [x] 12. `trip_journal/pages/journal.py` - GET `/trips/{id}/days/{day}/journal` (page), `/journal/fragment`, `/journal/paragraphs/{slot}/edit`, `/journal/paragraphs/{slot}`, `/trips/{id}/citations/{kind}/{cid}` (422 bad kind). *(Codex, C2)*
- [x] 13. Templates (all text English as written in frontend-components.md; Jinja autoescape, never `|safe` on journal text, U4-NFR-SP.2): `journal/page.html` (header, TonePicker, Write / Regenerate with disabled reasons, `aria-live` region, `#journal-job`, `#journal-body`), `journal/result.html` (job result, D-9), `_partials/journal_body.html` (empty state, message line, unsupported count link JR-G4, paragraph list, trace), `_partials/journal_paragraph.html` (reading view, `<mark class="unsupported">` + icon + visually-hidden "unsupported", owner label, "Not written yet" / "Removed by you", Edit), `_partials/journal_editor.html` (label + textarea, `hx-put` `input changed delay:1s, blur`, `hx-sync="this:replace"`, `role="status"` line, Done, oob count), `_partials/citation_panel.html`, `_partials/journal_trace.html` (`<details>` with step groups D-3, "loaded by the app" for step 0, tone / model / prompt version / local time). **[U2]** `days/day.html` - Journal link + "drafted" / "not written" badge (JR-UI4). **[U1]** `pages/static/app.css` - unsupported mark, cite button, panel, removed line only. New `pages/static/journal.js` (D-11). *(Codex, C2)* — US-09..US-13
- [x] 14. `data-testid` values exactly as FD §5: `write-journal`, `tone-picker`, `journal-paragraph-<slot-safe>`, `edit-<slot-safe>`, `autosave-status`, `unsupported-count`, `cite-<kind>-<id>`, `cite-panel`, `trace-details`; plus `journal-link` on the day page and `journal-message`, `journal-live`. Tests assert each. *(Codex, C2)*

### G. U3 carry-ins (BL-10)
- [x] 15. JR-CI1: **[U3]** `trip_journal/agent/prompts/organizer.md` - tip and rating rules per D-14 *(Claude)*; FakeLLM regression tests in **[U3]** `tests/unit/test_organizer_parse.py` / `test_organizer_prompt.py`: prompt text holds the new tip and "9/10" rules; a reply with tip quoted from the note and rating 4 for "8/10" is kept unchanged *(Codex, C2)*. 18-note smoke re-run is a Build and Test item.
- [x] 16. JR-CI2: **[U2/U3]** `days/day.html` or `_partials/note_item.html` - after an accept / reject / edit / undo swap, focus goes to the next pending row, else the stop heading (`tabindex="-1"`); page test asserts the focus hook markup (`data-focus-next`) and the JS selector. *(Codex, C2)*

### H. Tests (FakeLLMClient only, never real Ollama, U4-NFR-T.6)
- [x] 17. **[U1]** `tests/strategies.py` (PBT-07): days with 0-25 stops and random note lengths, slot orders from 0-8 distinct ids, existing paragraphs with random owners / Unicode texts incl. `""` and leading spaces, drafts with junk slots, journal text with valid / junk / duplicate / spaced `##` headings and citations. **[U1]** `tests/conftest.py` - journal fixtures (trip with an 8-stop day and a 13-stop day). *(Codex, C1)*
- [x] 18. Unit tests *(Codex, C1)*: `tests/unit/test_journal_merge.py` (`slot_order` 0 and 3 stops, three regenerate cases all generated / mixed / all user, `mark_user_edit`), `test_journal_parse.py` (each drop reason, spaced headings, empty body = missing, no slot → `ModelCallError`), `test_journal_chunks.py` (6-stop cut, 4,000-char cut, one big stop alone, plan chars = step-0 results D-6), `test_journal_prompt.py` (each tone assembly holds base citation rule, slot rule and its tone text; summary prompt), `test_journal_agent.py` (FakeLLM full draft for an 8-stop day in 3 steps; step 0 records for every stop with `step=0`; journal calls record `reasoning_effort="none"` and `timeout_s=300`; 2-chunk day + summary call; failing second chunk → error, nothing saved; step limit → `AgentStepLimitError`; tool error kept in trace and message), `test_journal_repo.py` (save_generated guard, edit just before / just after the save step JR-S2, unchanged edit writes nothing, positions rewritten, trace round trip), `test_journal_service.py` (BL-1 order incl. nothing-to-regenerate 200 and no-records, job limit from planned calls, per-run grounding: trip id not in trace unsupported in generated and supported in user paragraph, JR-R4 / JR-F3 messages, L.1 log lines hold no note or journal text). **[U1]** `tests/agent/test_loop.py` - D-2 defaults unchanged and new params passed; D-3 old trace JSON still validates.
- [x] 19. API / page tests *(Codex, C2)*: `tests/api/test_journal_api.py` (status codes above, JSON vs htmx fragment, 5,001-char edit 422, edit during a running job allowed), `tests/api/test_journal_pages.py` (page states: empty, no records disabled, written, removed, unsupported `<mark>` + hidden text, citation buttons and panel incl. "Record not found in this trip.", trace groups, job result fragment with "Draft ready", escaping of `<script>` in note and journal text, all test ids), **[U2]** `tests/api/test_trip_pages.py` (badge), **[U3]** `tests/api/test_organizer_pages.py` (CI2 hook).
- [x] 20. Property tests *(Codex, C1)*: `tests/property/test_journal_props.py` - P-1..P-6 on `merge_journal` / `mark_user_edit`, P-7 on `parse_journal_output`, P-8 on `chunk_stops`; PBT-02 round trip `StoredJournal` save → `get` (paragraphs, tone, trace) equal. U1 profiles reused (PBT-08).

### I. Verify and record
- [x] 21. *(Claude)* Review each Codex diff (C1 then C2) against this plan and the FD rules; `uv run pytest --cov` (U4 modules ≥ 80%, U4-NFR-T.1), `HYPOTHESIS_PROFILE=ci` run in background, `ruff check trip_journal tests`, `ruff format --check trip_journal tests`, `mypy --strict trip_journal tests` (`scripts/model_spike.py` and `spike_results*` left untouched). Fix or send back findings; second-model read-only review of the save-step transaction and edit concurrency (high-risk area).
- [x] 22. *(Claude)* `aidlc-docs/construction/u4-daily-journal/code/code-summary.md` (modified vs created files, D-1..D-14, open item D-12, test counts, coverage); tick this plan and the U4 stories; `aidlc-state.md`; `audit.md`; PROMPT_LOG entries; `ADDED [PROMPT #n]` / `CHANGED [PROMPT #n]` tags in code.

## Codex dispatch

| Batch | Steps | Branch / worktree | Returns |
|---|---|---|---|
| C1 backend | 1-6, 8-11, 17, 18, 20 (needs step 7 prompts first) | own worktree, branch `codex/u4-backend` | diff, `pytest` + `ruff` + `mypy` output |
| C2 frontend | 12-14, 15 (tests), 16, 19 | own worktree from C1 result, `codex/u4-frontend` | diff, test output, page screenshots of empty / written / editor / citation / trace states |

Claude does steps 7, 15 (prompt text), 21, 22. Order: 7 → C1 → review → C2 → review → 21 → 22. If Codex is out of quota, ask the owner (continue on Claude Sonnet or wait), per owner rule.

## Story traceability

| Story | Steps |
|---|---|
| US-09 cited day journal | 7, 8, 9, 11, 13, 18, 19 |
| US-10 unsupported highlighted | 9 (D-8), 13, 19 |
| US-11 how it was made | 4 (D-3), 8, 13 (trace), 19 |
| US-12 edit a paragraph | 2, 6, 9, 11, 13, 18, 19 |
| US-13 regenerate keeps edits | 2, 6, 9, 18, 20 |
| US-20 clear failure (U4 page) | 8, 9, 13, 19 |

## PBT mapping

| Rule | Property | Test |
|---|---|---|
| PBT-02 round trip (blocking) | `StoredJournal` save → get equal; `ToolCallRecord` dump → validate | test_journal_props, test_journal_repo |
| PBT-03 invariants (blocking) | P-1..P-8 | test_journal_props |
| PBT-07 generators (blocking) | step 17 strategies | - |
| PBT-08 shrinking / repro (blocking) | U1 profiles, `print_blob=True`, `deadline=None` | - |
| PBT-09 framework (blocking) | Hypothesis (U1) | - |

## Build and Test items (not Code Generation)
Manual quality smoke check (U4-NFR-G.3) on the minimal trip day and one reference-trip day; speed P.4 on the measured laptop; P.7 ≤ 300 ms once; U3 18-note smoke re-run (JR-CI1); browser checks from FD §5. Manual runs use `TRIP_JOURNAL_PORT`.

## Owner answers (Part 1)
- 2026-11-28T00:18:55Z: "Approve, start Part 2" - plan approved as written (D-1..D-14, Codex C1/C2 split).
