# U3 Note Organizer - Domain Entities

**Stage**: Functional Design (U3). The owner answered A to all 21 questions on 2026-11-27.
**Plan**: `aidlc-docs/construction/plans/u3-note-organizer-functional-design-plan.md`
**Builds on**: U1 tables `trips`, `stops`, `notes` (never written by U3) and the U2 view models in `trip_journal/domain/views.py`.

---

## 1. Values

| Name | Values | Source |
|---|---|---|
| `Category` | `food`, `scene`, `logistics`, `feedback`, `other` | FR-3.2, `component-methods.md` C15 |
| `SuggestionStatus` | `pending`, `accepted`, `edited`, `rejected` | Q1 A |
| Decided | `accepted`, `edited` or `rejected` | Q2 A |
| Organized | `accepted` or `edited`. Only these rows become organized note data (FR-3.4). | Q1 A |

## 2. Table `note_suggestions` (new U3 section of `schema.sql`)

The U1 and U2 sections are not edited. The U3 section is added after the line `-- ===== end of U1 section ...`.

| Column | Type | Rule |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | |
| `trip_id` | INTEGER NOT NULL, FK `trips(id)` ON DELETE CASCADE | the delete cascade (DL rules in U2) also removes decisions |
| `note_id` | INTEGER NOT NULL, FK `notes(id)` ON DELETE CASCADE, **UNIQUE** | one row per note (FA-1) |
| `status` | TEXT NOT NULL, CHECK in the four statuses | |
| `s_category` | TEXT NOT NULL | the model's values; kept so Undo can restore them (Q3 A) |
| `s_stop_id` | INTEGER NULL, FK `stops(id)` ON DELETE CASCADE | NULL = "no stop" |
| `s_dish`, `s_tip` | TEXT NULL | |
| `s_rating` | INTEGER NULL, CHECK 1-5 | |
| `f_category`, `f_stop_id`, `f_dish`, `f_rating`, `f_tip` | same types, all NULL | final values; set only for `edited` |
| `prompt_version` | TEXT NOT NULL | `PromptLibrary.version`, for evaluation |
| `model_name` | TEXT NOT NULL | the model that produced it |
| `created_at`, `decided_at` | TEXT (ISO 8601 UTC) | `decided_at` is NULL while pending |

Index: `idx_suggestions_trip (trip_id)`.

**Why one row per note (FA-1)**: under Q2 A a re-run replaces pending rows and skips decided notes, and under Q3 A Undo sets a row back to `pending`. So a note never needs two rows at once. A UNIQUE `note_id` makes "at most one decision per note" a database rule.

**Effective values**: `accepted` uses the `s_*` values; `edited` uses the `f_*` values. `pending` shows `s_*` as a suggestion. `rejected` shows nothing.

## 3. Model output (agent layer, `agent/organizer.py`)

The model sees short labels, never database ids (Q9 A).

| Model | Fields | Notes |
|---|---|---|
| `ReplyItem` | `note: str` (label `n1`…), `category: str`, `stop: str \| None` (label `s1`… or null), `dish: str \| None`, `rating: int \| None`, `tip: str \| None` | parsed one item at a time; extra keys are ignored |
| `OrganizerReply` | `suggestions: list[object]` | the JSON schema sent as `response_format` is built from this model with `ReplyItem` items (Q8 A) |
| `NoteSuggestion` | `note_id: int`, `category: Category`, `suggested_stop_id: int \| None`, `dish: str \| None`, `rating: int \| None` (1-5), `tip: str \| None` | after label mapping and validation (C15, unchanged shape) |
| `DroppedItem` | `note_label: str \| None`, `note_id: int \| None`, `reason: str` | for example `unknown note label 'n14'`, `rating 7 outside 1-5` |
| `OrganizerBatchResult` | `suggestions: list[NoteSuggestion]`, `dropped: list[DroppedItem]`, `not_organized: list[int]` (note ids that got no valid item) | `dropped` was `list[str]` in `component-methods.md` (IC-4) |
| `BatchInput` | `day: str`, `stops: list[StopRow]`, `notes: list[NoteRow]` (at most 10) | built by the service (Q6 A) |

## 4. Service and view models

| Model | Fields | Used by |
|---|---|---|
| `OrganizedFields` | `category`, `stop_id: int \| None`, `dish`, `rating`, `tip`, `edited: bool` | the timeline display (US-05) |
| `SuggestionView` | `suggestion_id`, `note_id`, `note_source_id`, `status`, `category`, `stop_id`, `stop_source_id: str \| None`, `stop_label` (stop name or "No stop"), `dish`, `rating`, `tip` (effective values), `model_values` (the `s_*` set) | review rows, the API, U6 evaluation (compares by `source_id`) |
| `SuggestionEdit` | `category: Category`, `stop_id: int \| None`, `dish: str \| None`, `rating: int \| None`, `tip: str \| None` | the edit form and the API; same field rules as model output (OR-F*) |
| `DayRunResult` | `day`, `notes_sent`, `suggested`, `not_organized: list[NotOrganized]` (note id, local time, first 60 characters of the text, reason), `dropped: list[DroppedItem]`, `failed_batches: int` | the run summary |
| `OrganizerRunSummary` | `trip_id`, `scope_day: str \| None`, `days: list[DayRunResult]`, `total_suggested`, `total_not_organized`, `batches`, `batches_failed`, `skipped_decided: int`, `prompt_version`, `model_name` | the job result and `organize_now` (C05) |
| `OrganizeStart` | `job: JobRef \| None`, `notes_to_send: int`, `batches: int` | `job` is None when nothing is left to organize (FA-2) |

## 5. Changes to U2 view models (`domain/views.py`)

| Model | Change | Reason |
|---|---|---|
| `NoteItem` | add `organized: OrganizedFields \| None = None`, `suggestion: SuggestionView \| None = None` (pending only), `review_status: SuggestionStatus \| None = None` | organized data is per note, not per stop (US-05 Scenario 1 shows the fields "together with the original note text") |
| `StopTimelineItem` | remove the unused `organized: None = None` slot | replaced by the per-note fields (IC-2) |
| `DaySummary` | add `pending_suggestions: int = 0` | the trip overview shows pending counts per day (Q15 A) |
| `PhotoMeta` | no change; the template adds coordinates (TL-5, Q20 A) | |

## 6. Relationships

| From | To | Rule |
|---|---|---|
| `note_suggestions.note_id` | `notes.id` | 0 or 1 suggestion per note |
| `note_suggestions.s_stop_id` / `f_stop_id` | `stops.id` | must be a stop on the note's day (OR-S1) |
| organized stop | where the note is shown | the effective stop of an `accepted` / `edited` row decides placement on the timeline; otherwise the import `notes.stop_id` (Q4 A) |
| `notes.text`, `notes.stop_id` | | never written by U3 (FR-3.4, OR-R1) |
