# U3 Code Generation Part 2 - hand-off note 2 (2026-11-27)

The second sub chat hit a context compaction while still reading code, before it wrote any of it. It stopped at a clean step, as the brief says.

## State
- Plan `aidlc-docs/construction/plans/u3-note-organizer-code-generation-plan.md`: steps 1-6 are ticked and **7-22 are not started**. No code files changed in this sub chat.
- `aidlc-docs/audit.md`: one entry was appended, "Code Generation - Part 2 Continued in a New Sub Chat (U3 Note Organizer)", 2026-11-27T14:25:00Z, with the full brief verbatim. The next sub chat appends its own brief after it.
- Baseline (unchanged): 276 passed, 3 deselected.

## Read `u3-codegen-handoff.md` first
All of D-1..D-19 and the module sketches are still valid and are in that note. The next sub chat should read it plus the 4 FD files and `nfr-requirements.md`, not re-derive them.

## New decision (record as D-20 in code-summary.md)
- D-20: `OrganizerService.start` checks model readiness with `llm.status()` on the factory-built client, not `SettingsService.model_status()`. This lets FakeLLMClient's `status_value` drive the 503 path in tests.
  - The default `llm_factory` builds `OllamaClient(settings.ollama_base_url, settings.model_name, timeout_s=ORGANIZER_CALL_TIMEOUT_S, http=state.http)`, which is the same probe that SettingsService uses.
  - Check that `OllamaClient` accepts `http`. Its signature is `OllamaClient(base_url, model, timeout_s=120, http=None)`.
- Notes for a day = notes whose `local_date == day`. A linked note already carries its stop's day (DD-3).

## Facts gathered this time (to save the next sub chat from reading again)
- `api/jobs.py`: only `GET /api/jobs/{id}`. The HTML job fragment route `/jobs/{id}/fragment` lives in the pages module (find it with grep for "fragment" in `trip_journal/pages/`). It renders `_partials/job_progress.html` with `job`, `view` (`state.job_views.get(job.kind)`) and `retry_url`.
- `_partials/job_progress.html`:
  - running: polls `hx-get="/jobs/{id}/fragment" every 1s`, outerHTML, `data-testid="job-progress"`, `data-state`;
  - done: `{% include view.result_template %}` plus the trace;
  - failed: `_partials/error.html` with `error=job.error` and `retry_url`. The retry button is `hx-post=retry_url hx-target="closest .job"`.
- `_partials/stop_item.html`:
  - the notes are an inline `<li data-testid="note-{id}">{{ when(note) }} {{ note.text }}</li>`; D-7 moves this into `_partials/note_item.html`;
  - `when` is a macro defined in this file, so it has to move into note_item too (or into a shared macro file);
  - photos: `<li data-testid="photo-{id}">{{ when(photo) }}{% if photo.file_name %} · {{ photo.file_name }}{% endif %}</li>` is where CI-1 adds `· lat, lon` or `· no location`. `PhotoMeta` may need lat / lon fields; check `domain/views.py` `PhotoMeta` and `TripService._photo_meta`.
- `days/day.html`:
  - `<ol class="timeline" data-testid="day-stops">` and `<section class="panel" data-testid="day-other-notes">`, with the unlinked notes inline and no `when` macro (time only);
  - D-8 wraps both in `<section id="day-stops" data-testid="day-stops-region">`, and the organizer bar goes above it.
- `trips/overview.html`: the day row is `<li data-testid="overview-day-{date}">`. Add the "N to review" span there, and the "Organize the whole trip" form.
- `trips/list.html`: `{{ trip.days | length }} days` is where the CI-2 plural fix goes.

## Still not read
`pages/trips.py` (the rest), the job fragment route, `tests/conftest.py`, `tests/strategies.py`, `test_trip_pages.py`, `test_trips_service.py`, `test_views.py`, `app.css`, the PROMPT_LOG #23 / #24 format, `aidlc-state.md`, the U2 `code-summary.md` format.

## Advice for the next sub chat
16 steps is too much for one context. Split it in two:
- (a) steps 7-13: domain, agent, prompt, service, views, wiring, JSON API, with the unit tests for those modules;
- (b) steps 14-22: pages, templates, the rest of the tests, PBT, perf, checks, docs.
