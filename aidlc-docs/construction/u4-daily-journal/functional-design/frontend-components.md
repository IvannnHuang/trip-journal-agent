# U4 Daily Journal - Frontend Components

> **Summary**: the journal page and its htmx fragments: header with tone picker and Write / Regenerate, job progress, draft reading view with citation buttons and unsupported highlights, per-paragraph editor with autosave, citation detail panel and "How this was made". Server-rendered Jinja2 + htmx, same base layout and styles as U2/U3. All UI text below is the English default; strings go through the existing UI text helper.

## 1. Routes

| Kind | Method and path | Returns | Errors |
|---|---|---|---|
| Page | GET `/trips/{id}/days/{day}/journal` | Full journal page | 404 page (JR-E1) |
| Fragment | GET `/trips/{id}/days/{day}/journal/fragment` | `#journal-body` (after a job) | 404 |
| Fragment | GET `/trips/{id}/days/{day}/journal/paragraphs/{slot}/edit` | Editor for one paragraph | 404 |
| Fragment | GET `/trips/{id}/days/{day}/journal/paragraphs/{slot}` | Reading view for one paragraph (Done) | 404 |
| Fragment | GET `/trips/{id}/citations/{kind}/{cid}` | Citation panel (JR-C1) | 422 bad kind |
| Fragment | GET `/jobs/{job_id}/fragment` | Existing U3 job fragment, journal variant | 404 |
| API | GET `/api/trips/{id}/days/{day}/journal` | `JournalView` JSON | 404 |
| API | POST `/api/trips/{id}/days/{day}/journal` body `{tone}` | 202 `JobRef`, or 200 `{nothing_to_regenerate: true, message}` | 404, 409, 422, 503 |
| API | PUT `/api/trips/{id}/days/{day}/journal/paragraphs/{slot}` body `{text}` | 200 paragraph view + `unsupported_count` | 404, 422 |

htmx requests to the API routes ask for HTML (`HX-Request` header) and get the matching fragment; other callers get JSON (same pattern as U3).

## 2. Component tree

```text
JournalPage  (/trips/{id}/days/{day}/journal)
├── JournalHeader        h1 "Journal - <date>", back link to the day timeline
│   ├── TonePicker       <select> casual / concise / detailed (JR-T1)
│   ├── WriteButton      "Write journal" (no journal) | "Regenerate" (journal exists)
│   └── LiveRegion       aria-live="polite": "Draft ready", errors (JR-UI3)
├── JobArea  #journal-job   progress fragment while a job runs (BL-9)
└── JournalBody  #journal-body
    ├── EmptyState        "Not written yet. Choose a tone and press Write journal." | "No records for this day."
    ├── MessageLine       partial / tool-error / nothing-to-regenerate messages
    ├── UnsupportedCount  "N unsupported sentences" -> link to first <mark> (JR-G4)
    ├── ParagraphList
    │   └── ParagraphBlock  #p-<slot-safe>   (one per slot, order = slot_order)
    │       ├── h2 heading (tabindex=-1)  "Day summary" | "<stop name> · <time>"
    │       ├── OwnerLabel  "edited by you" (user only)
    │       ├── ReadingView  sentences with CitationButtons, <mark> for unsupported
    │       │   or StateText "Not written yet" (not_written) / "Removed by you" (removed, editor-side only)
    │       ├── EditButton  "Edit"
    │       └── CitationPanel slot (empty until a citation is opened)
    └── TraceDetails  <details> "How this was made" (JR-TR1)
```

`slot-safe` = slot with `:` replaced by `-` (e.g. `p-stop-12`).

## 3. Components

### TonePicker and WriteButton
- Write is disabled with the reason as visible text when the day has no records (JR-P2) or the model is not ready (U1 status text).
- `hx-post` to the journal API with `hx-include` of the tone; target `#journal-job`. Responses: 202 → progress fragment; 200 nothing to regenerate → message in `MessageLine` and live region; 409 → "Another job is running. Try again when it finishes."; 503 → model status text.
- While a job runs, the button is disabled and shows "Generating… your edits are kept." (JR-S3).

### JobArea (progress)
- Reuses the U3 job fragment polling (`hx-trigger="every 1s"`) with text "Step N of 8: <tool>", "Writing the journal…", "Saving…".
- Done: the fragment loads the new `#journal-body`; a small page script swaps each ParagraphBlock except blocks with an open editor or unsaved text, which stay as they are (JR-S4). Focus moves to the first paragraph heading; live region says "Draft ready".
- Failed: error message plus a collapsed trace of the run so far; the body stays unchanged (JR-F1).

### ReadingView and CitationButton
- Each sentence is a `<span>`; unsupported ones are `<mark class="unsupported">` with an inline warning icon (`aria-hidden`) and `<span class="visually-hidden">unsupported</span>`, dotted underline in CSS (JR-G4).
- Each citation `[note:41]` renders as `<button class="cite" aria-expanded="false" aria-controls="cite-panel-<slot-safe>">note 41</button>`; `hx-get` the citation route into that paragraph's CitationPanel.

### CitationPanel
- Content per kind (BL-8); unknown id → "Record not found in this trip."
- Close button and Escape (`hx-on:keydown`) empty the panel, set `aria-expanded="false"` and return focus to the opening button (JR-C2). Opening another citation replaces the panel.

### ParagraphEditor
- Edit swaps the ReadingView for a `<label>`ed `<textarea>` with the raw text (`hx-get` edit fragment, `hx-swap="outerHTML"`), focus into the textarea.
- Autosave: `hx-put` to the paragraph API, `hx-trigger="input changed delay:1s, blur"`, `hx-sync="this:replace"` so the last request wins (BL-5).
- Status line (`role="status"`): "Saved", "Saving…", "Not saved: <reason>" (422 text, or "Connection lost; your text is still here." on network error; the text is never cleared on error).
- `visibilitychange` to hidden sends any pending save with `fetch(..., {keepalive: true})` (JR-S5).
- After save focus stays in the textarea; the unsupported count in the body updates out of band (`hx-swap-oob`).
- Done swaps back to the ReadingView for that paragraph and focuses its Edit button (JR-UI2).
- A removed paragraph has no text in the reading flow; its block shrinks to one compact line "Removed by you" plus its Edit button, so it can be reopened (JR-O4).

### TraceDetails
- `<details><summary>How this was made</summary>`: a table of tool calls (step, name, arguments as compact JSON, returned ids, or "Error: <kind>: <message>"), then tone, model, prompt version and local generation time (JR-TR1).
- Shown only when a journal exists; a tool-error message line links here (JR-F3).

### Timeline badge (U2 page change)
- Day header on `/trips/{id}/days/{day}` gets a "Journal" link with badge "drafted" or "not written" (JR-UI4), using `JournalRepository.exists`.

## 4. Accessibility and focus summary

| Event | Focus target | Announcement |
|---|---|---|
| Draft finished | First paragraph heading in `#journal-body` | "Draft ready" |
| Job failed | Error message (tabindex=-1) | Error text |
| Nothing to regenerate | Stays on Regenerate | Message text |
| Edit opened | Textarea | - |
| Autosave | Stays in textarea | Status line (polite) |
| Done | That paragraph's Edit button | - |
| Citation closed | The citation button | - |
| U3 review row swap (carry-in) | Next pending row, else stop heading | - |

Keyboard: every control is a native button, link, select or textarea; no custom key handling except Escape on the citation panel. Contrast and target sizes follow the U2/U3 styles.

## 5. Test hooks

Stable `data-testid` values: `write-journal`, `tone-picker`, `journal-paragraph-<slot-safe>`, `edit-<slot-safe>`, `autosave-status`, `unsupported-count`, `cite-<kind>-<id>`, `cite-panel`, `trace-details`. Browser checks in Build and Test: generate → draft swap and focus; edit during a job survives; citation open / Escape; trace content after a tool error.
