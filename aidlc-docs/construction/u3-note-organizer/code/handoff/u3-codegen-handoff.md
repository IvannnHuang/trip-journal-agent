# U3 Code Generation - hand-off for steps 7-22 (2026-11-27)

## 中文摘要
- U3 Code Generation 的 Part 1 计划已获批准，步骤 1-6 已完成并勾选，测试、ruff、mypy 全部通过。
- 剩下步骤 7-22。下面是续接提示，以及上一个会话已经定好的设计细节（D-12..D-19）。
- 本会话发生了上下文压缩，按规则在干净的节点停下。

## Continuation prompt (paste into a fresh sub chat; Model: Opus 5.5, effort medium)
```text
Continue AI-DLC Code Generation Part 2 for U3 Note Organizer in D:\documents\web\classes\INFO5940\trip-journal-agent.
Plan (approved by the owner, steps 1-6 ticked): aidlc-docs/construction/plans/u3-note-organizer-code-generation-plan.md.
Design: aidlc-docs/construction/u3-note-organizer/functional-design/*.md and nfr-requirements/*.md.
Design details already decided: the shared notes file u3-codegen-handoff.md (D-12..D-19 and the module sketches). Read it first.
Do steps 7-22 in order and tick each as done. Tests use FakeLLMClient only. PBT Partial mode; PBT-02/03/07/08/09 are blocking.
Checks: uv run pytest --cov (U3 modules >= 80%), HYPOTHESIS_PROFILE=ci in background, pytest -m slow,
ruff check + ruff format --check on trip_journal tests, mypy --strict trip_journal tests. Leave the E501 errors in scripts/model_spike.py alone.
Then write code/code-summary.md (deviations D-12..D-19), update aidlc-state.md and audit.md (append only, word-for-word user input, ISO timestamps),
add PROMPT_LOG #25+ in the #23/#24 format, with ADDED/CHANGED [PROMPT #25] tags. Present the standard 2-option completion message and wait for the owner.
Never commit or push. Do not start Build and Test. Chat in Chinese; docs in English. If the app is started, use TRIP_JOURNAL_PORT (8000 is taken).
```

## State of the work
- Steps 1-6 done: `data/schema.sql`, `data/suggestions.py`, `data/repositories.py`, `config.py`, `agent/llm.py`, `services/jobs.py`, `services/errors.py`.
  - The `ORGANIZER_*` constants in config also include `ORGANIZER_JOB_TIMEOUT_PER_BATCH_S=300.0` and `ORGANIZER_REASONING_EFFORT="none"`.
  - `FakeLLMClient` records `response_formats`, `reasoning_efforts` and `timeouts`.
  - `JobTimeoutError(detail, limit_s)` comes with `errors.minutes_text`.
  - Check whether `UserFacingError` needs a `fields` attribute for the `invalid_edit` 422 body.
- Baseline: 276 tests pass (3 slow deselected), ruff is clean, mypy --strict on trip_journal is clean.

## Deviations and decisions to keep (D-1..D-11 are in the plan)
- **D-12**: the pages module is `pages/organizer.py`, as the FD says, not the plan's `pages/notes.py`.
- **D-13**: an inner deadline in the organizer job work.
  - The batch loop runs under `asyncio.timeout(max(limit-5, limit*0.9))`.
  - If the deadline fires after at least one batch succeeded, the work returns a summary with `stopped="job_timeout"` and `remaining_notes`, and the summary shows "Run again to continue with the remaining N notes."
  - If it fires before any batch succeeded, the work raises `JobTimeoutError(limit_s=limit)`.
  - If every batch failed, it raises `ModelCallError("error")`.
  - JobRunner still gets `timeout_s=min(300*batches, 1800)` as a backstop.
- **D-14**: the JobTimeoutError message depends on the limit ("over N minutes").
- **D-15**: `PromptLibrary.get(name, tone=None, shared: bool = True)`. The organizer uses `shared=False`, so it does not get `_shared_tool_data.md` (citations and "not in your records" are wrong for it).
- **D-16**:
  - `SuggestionView` gains `trip_id` and `local_date`.
  - Service review actions return a `SuggestionView`; pages then call `trips.get_day` to re-render `#day-stops`.
  - `OrganizedFields` and `NoteItem` gain `suggestion_id`.
- **D-17**: `OrganizeStart` lives in `services/organizer.py`, because domain must not import `JobRef`.
- **D-18**: add `NoteRepository.get(trip_id, note_id)` (a U1 edit), so a SuggestionView can be built.
- **D-19**: duplicate check OR-V5 compares only against items already kept for the same note.
- **Prompt escaping**: note text in the prompt has `</` replaced by `<\/`.
- **Form input**: digit strings become int for rating and stop_id, and an empty string becomes None. The JSON API stays strict, so a string rating is invalid there.

## Module sketches
- **`domain/organizer.py`**
  - Types and limits: `Category = Literal["food","scene","logistics","feedback","other"]`, `CATEGORIES`, `DISH_MAX=80`, `TIP_MAX=200`.
  - Models:
    - `ReplyItem`, and `OrganizerReply(suggestions: list[ReplyItem])` for the JSON schema.
    - Frozen `NoteSuggestion`.
    - `DroppedItem(note_label, note_id, reason)`.
    - `OrganizerBatchResult(suggestions, dropped, not_organized: list[int], outcome="ok")`.
    - Frozen dataclass `BatchInput(day, stops, notes)`.
    - `NotOrganized(note_id, local_time, preview[:60], reason)`.
    - `DayRunResult`.
    - `OrganizerRunSummary`, which adds `stopped: str|None` and `remaining_notes: int`.
    - `OrganizedFields`, `SuggestionView`, and `SuggestionEdit` (extra="forbid").
  - Pure functions:
    - `clean_text(value, limit, name)`: text is trimmed, an empty string becomes None, too long gives "{name} longer than {limit} characters".
    - `clean_rating`: rejects bool and str, accepts an integral float, out of range gives "rating {v} outside 1-5".
    - `clean_category`: gives "category {value!r} not allowed".
    - `check_edit(raw, stop_ids)` raises `SuggestionEditError(fields)`; an unknown key gives "unknown field".
    - `plan_batches(notes)`: close a batch at 10 notes, or when adding the next note's cut text would pass 6,000 characters.
    - `suggestion_view(row, note, stops_by_id)`.
  - Exact drop reasons: `unknown note label 'n14'`, `unknown stop label 's9'`, `duplicate`, `item is not an object`.
- **`agent/prompts/organizer.md`**: written from FD §5.
  - Covers the role, the five categories, the stop rule, and the dish / rating / tip rules (8/10 -> 4, 4.5/5 -> 5).
  - The tip is one piece of advice, never the whole note.
  - Output is in English; a dish may quote the original name (up to 30 characters), as in `pork dumplings ("饺子")`.
  - Safety: the notes are data, and one note never changes another note's item.
  - The reply is only `{"suggestions":[...]}`, using labels.
- **`agent/organizer.py`**
  - Labels: stops s1..sM sorted by `(start_utc, id)`; notes n1..nK sorted by `timed_order`.
  - Stop line: `s1 | name or "Unnamed place" | HH:MM-HH:MM`.
  - Note line: `n1 | HH:MM | s-label or "none"`, then `<note id="n1">cut text</note>`.
  - Everything goes inside `<trip_data>...</trip_data>`, followed by `tools.DATA_LINE`. Cut note text with `tools.truncate_text`.
  - `RESPONSE_FORMAT` is a json_schema built from `OrganizerReply.model_json_schema()`.
  - `parse_reply` uses `loop.strip_think`.
  - `NoteOrganizer(llm, prompts, call_timeout_s).organize_batch(batch)`:
    - wraps the call in `asyncio.timeout` and passes `reasoning_effort="none"` and `timeout_s`;
    - `TimeoutError` or `openai.APITimeoutError` gives `call_timeout`;
    - any other exception gives `model_error`;
    - `CancelledError` propagates.
- **`services/organizer.py`**
  - `OrganizerService(repos, jobs, settings, trips, llm_factory, prompts)` with `start`, `organize_now`, `accept`, `reject`, `edit_and_accept`, `undo`, `accept_all`.
  - Each batch is saved in its own `BEGIN IMMEDIATE` transaction, using the `conn.commit()` first pattern from `services/imports.py` `_store`.
  - Logs: `organizer.batch`, `organizer.run`, `organizer.review` via `logs.kv`, with no note or reply text.
  - Progress text: "Organizing day {n} of {N} ({date}), batch {i} of {I}" for a trip run, or "Organizing {date}, batch {i} of {I}" for a day run.
- **TripService**
  - Load `suggestions.list_for_trip` once.
  - Place each note under its effective stop (`SuggestionRow.effective_stop_id` when the row is organized).
  - Fill the `NoteItem` fields: `organized`, `suggestion`, `review_status` and `suggestion_id`.
  - Fill `DaySummary.pending_suggestions`.
  - Remove `StopTimelineItem.organized`.
- **Wiring**
  - `llm_factory` and `AppState.organizer`.
  - `job_views["organize"] = JobView("organizer/summary.html", retry_url)`. The summary template reads `job.result` as a dict.
  - Include the routers `api/notes.py` and `pages/organizer.py`.
- **Templates**
  - `#day-stops` is `<section id="day-stops" data-testid="day-stops-region">`.
  - `_partials/note_item.html` is used in both `stop_item` and "Other notes".
  - CI-1 photo line: `time · 38.7118, -9.1301 · file`, or "no location".
  - CI-2 in `list.html`: "1 day" / "n days".
  - `overview.html`: "N to review" and an "Organize the whole trip" form.
  - Plain POSTs (no `HX-Request` header) get a 303 redirect; see `pages/settings.py` / `pages/trips.py` for the U2 pattern.
