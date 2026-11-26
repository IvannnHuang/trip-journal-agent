# U1 Foundation - Frontend Components

**Stage**: Construction - Functional Design (plan step B4)
**Source**: US-18, US-19, FR-8.2, FR-10.x, NFR-5 (accessibility), plan answers Q16-Q18, Q25, Q26
**Scope**: the shared Jinja2 + htmx templates and the Settings page that U1 owns. Later units (U2-U5) build their pages on these. Rule ids point to `business-rules.md`.

---

## 1. Template tree

```text
templates/
  base.html                  layout: nav, model banner slot, main
  settings.html              Settings page (extends base.html)
  _partials/
    model_banner.html        model status banner
    job_progress.html        polling job status
    trace.html               "How this was made" panel
    error.html               user-facing error with Try again
    citations.html           macros: cite_link, grounded_text
```

## 2. Shared components

### 2.1 `base.html`
- `<nav>`: Trips, Settings. The current page link has `aria-current="page"`.
- Banner slot: filled from a page-level dependency that runs `model_status()` on every **full** page load (ST-1, ST-4). htmx fragment responses do not include the banner and do not run the check.
- `<main id="main">` with a skip link before the nav.
- Loads the vendored htmx script (no CDN; NFR-2 local only).

### 2.2 `_partials/model_banner.html`
- Input: `UserFacingError | None`. Renders nothing when `None`.
- Shows `message`, then `action` (the command in `<code>`), and a link to Settings.
- `role="alert"` is not used (it would re-announce on every page); `role="status"` with a visible warning icon and text.

### 2.3 `_partials/job_progress.html`
- Input: `JobStatus`.
- While `running`: shows `step` text and a spinner; the element has `hx-get="/jobs/{id}/fragment"`, `hx-trigger="every 1s"`, `hx-swap="outerHTML"`, `aria-live="polite"`.
- When `done` or `failed`: the returned fragment has no `hx-trigger`, so polling stops. `done` renders the caller's result block (given by the unit that started the job); `failed` renders `error.html` plus `trace.html`.

### 2.4 `_partials/trace.html`
- Input: list of `ToolCallRecord`.
- `<details><summary>How this was made</summary>` closed by default.
- One row per call: step, tool name, arguments (compact JSON), returned ids as citation links, error kind and message if any. Ids only, no record text (JB-8).
- Empty trace → "No tools were used."

### 2.5 `_partials/error.html`
- Input: `UserFacingError`, `retry_url`.
- Message, action, the fixed line "Nothing you saved was changed." (ER-3), and a **Try again** button (`hx-post` to `retry_url`) that starts a new job.
- If `trace` is not empty, includes `trace.html` (Q26 A).

### 2.6 `_partials/citations.html`
- `cite_link(kind, id)`: a link to the record (stop, note or photo page, added by U2) showing `[kind:id]` (FR-8.2).
- `grounded_text(report)`: renders each line and sentence; citations become `cite_link`; an unsupported sentence is wrapped in `<mark class="unsupported">` with a warning icon and visually hidden text "Unsupported:" so the flag does not rely on colour alone (NFR-5).

## 3. Settings page (`settings.html`, US-18)

| Element | Behaviour | Rules |
|---|---|---|
| Model name input | text, required, current resolved value | SE-2 |
| Ollama base URL input | text, current resolved value; help text "Must be http on localhost, 127.0.0.1 or [::1]." | SE-3 |
| Place lookup checkbox | unchecked by default; privacy note: "When on, rounded coordinates (about 11 m) of places without a name are sent to OpenStreetMap Nominatim." | SE-4, PL-4, PL-7 |
| Save button | `POST /settings`; on error, the form comes back with each field's error next to it (`aria-describedby`) and values kept; nothing saved | SE-5 |
| Saved message | "Settings saved." after a successful save | |
| Missing-model warning | after save, if the model is not installed: "The model X is not installed." plus `ollama pull X` | ST-6 |
| Status panel | Ollama reachable yes/no, model installed yes/no, base URL in use | ST-2, ST-3 |
| Check again button | `hx-get="/api/settings/model-status"` fragment that refreshes the status panel | ST-1 |

## 4. Routes owned by U1

| Method and path | Returns | Errors |
|---|---|---|
| `GET /settings` | Settings page | |
| `POST /settings` | Settings page with result | form errors in page (400 not used, page re-rendered) |
| `GET /jobs/{id}/fragment` | `job_progress.html` fragment | unknown id → `error.html` with `job_not_found` |
| `GET /api/settings` | `Settings` JSON | |
| `PUT /api/settings` | `Settings` JSON | 422 with field issues (SE-5) |
| `GET /api/settings/model-status` | `ModelStatus` JSON, or the status panel fragment when `HX-Request` is set | |
| `GET /api/jobs/{id}` | `JobStatus` JSON | 404 `job_not_found` (JB-7) |

## 5. Accessibility and UX checks (NFR-5)
- Every input has a `<label>`; errors are linked with `aria-describedby`.
- Status and warnings use text plus icon, never colour alone.
- Job progress updates are announced politely, at most once a second.
- No blank pages: a page whose model is unavailable still renders, with the banner explaining what to do.
