# U4 Daily Journal - Domain Entities

> **Summary**: the entities for a day journal: slots, owners and tones, stored paragraphs, the agent draft, the merge result and the view the page shows. Storage is two tables (`journals`, `journal_paragraphs`). Grounding is never stored; it is computed when the view is built. Decisions refer to the plan `aidlc-docs/construction/plans/u4-daily-journal-functional-design-plan.md` (all answers A, 2026-11-27).

## 1. Value types

| Type | Definition | Source |
|---|---|---|
| `Slot` | `str`: `"summary"` or `"stop:<stop_id>"` (SQLite stop id). Parsed and printed only by `domain/journal_merge.py` helpers `stop_slot(stop_id)` and `parse_slot(text)`. | Q2 A |
| `Owner` | `Literal["generated", "user"]` | FR-6.1 |
| `Tone` | `Literal["casual", "concise", "detailed"]`; default `"casual"` for a first draft | FR-4.2, Q13 A |
| `Citation` | existing `domain/grounding.py` `Citation(kind, id)` with kind `stop`, `note`, `photo` | U1 |

## 2. Domain models (`domain/journal_merge.py`, pure)

```python
class Paragraph(BaseModel):
    slot: Slot
    text: str          # stored exactly as written; "" is allowed (generated "Not written yet" or user-removed)
    owner: Owner

class MergeResult(BaseModel):
    paragraphs: list[Paragraph]   # exactly slot_order, in that order
    replaced_slots: list[Slot]    # generated slots that took draft text
    missing_slots: list[Slot]     # requested slots the draft did not fill (kept old text or "")
    nothing_to_regenerate: bool   # every slot in slot_order is user-owned

def slot_order(stop_ids_in_timeline_order: Sequence[int]) -> list[Slot]: ...   # ["summary", "stop:<id>", ...]
def slots_to_write(existing: Sequence[Paragraph], order: Sequence[Slot]) -> list[Slot]: ...  # generated or missing
def merge_journal(existing: Sequence[Paragraph], draft: Mapping[Slot, str], order: Sequence[Slot]) -> MergeResult: ...
def mark_user_edit(paragraphs: Sequence[Paragraph], slot: Slot, new_text: str) -> list[Paragraph]: ...
```

**Valid-input precondition** (Q24 A): every slot in `existing` is in `order`. It holds because a trip's stops do not change after import; `slot_order` gets its own example tests.

## 3. Agent models (`agent/journal.py`)

```python
class JournalDraft(BaseModel):
    slots: dict[Slot, str]                 # parsed, only requested slots with non-empty text
    dropped: list[DroppedHeading]          # duplicate / unknown / user-owned / unparsable headings, for the log
    trace: list[ToolCallRecord]            # existing U1 model (name, arguments, returned_ids, error)
    stopped_reason: Literal["final_answer", "step_limit"]

class DroppedHeading(BaseModel):
    heading: str
    reason: Literal["duplicate", "unknown_slot", "user_owned", "not_requested"]
```

`JournalAgent.write_day(context, day, tone, slots_to_write, user_paragraphs, on_step)` returns a `JournalDraft`. `user_paragraphs: Mapping[Slot, str]` is new (IC-2): read-only context for a regenerate (Q8 A).

## 4. Stored models (`data/repositories.py`, `JournalRepository`)

```python
class StoredJournal(BaseModel):
    trip_id: int
    day: LocalDate
    tone: Tone
    prompt_version: str
    model_name: str
    trace: list[ToolCallRecord]     # last successful generation only (Q17 A)
    generated_at: str               # UTC ISO, last successful generation
    updated_at: str                 # UTC ISO, last write of any kind
    paragraphs: list[Paragraph]     # by position
```

Repository methods (IC-3):

| Method | Behavior |
|---|---|
| `get(trip_id, day) -> StoredJournal \| None` | One read of both tables |
| `save_generated(trip_id, day, order, draft, tone, trace, prompt_version, model_name) -> MergeResult` | One `BEGIN IMMEDIATE` transaction: re-read owners, `merge_journal`, insert missing rows, `UPDATE ... WHERE owner = 'generated'` for replaced rows, upsert the `journals` row (BL-4, JR-S1) |
| `save_user_edit(trip_id, day, slot, text) -> Paragraph` | One transaction: if the text differs exactly from the stored text, set `text` and `owner = 'user'` together; otherwise no write (JR-O2) |
| `exists(trip_id, day) -> bool` | For the timeline badge |

## 5. Tables (U4 section of `schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS journals (
    trip_id        INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    day            TEXT    NOT NULL,              -- local date YYYY-MM-DD
    tone           TEXT    NOT NULL CHECK (tone IN ('casual', 'concise', 'detailed')),
    prompt_version TEXT    NOT NULL,
    model_name     TEXT    NOT NULL,
    trace_json     TEXT    NOT NULL,
    generated_at   TEXT    NOT NULL,
    updated_at     TEXT    NOT NULL,
    PRIMARY KEY (trip_id, day)
);

CREATE TABLE IF NOT EXISTS journal_paragraphs (
    trip_id  INTEGER NOT NULL,
    day      TEXT    NOT NULL,
    slot     TEXT    NOT NULL,                   -- 'summary' or 'stop:<id>'
    position INTEGER NOT NULL,
    text     TEXT    NOT NULL,
    owner    TEXT    NOT NULL CHECK (owner IN ('generated', 'user')),
    PRIMARY KEY (trip_id, day, slot),
    FOREIGN KEY (trip_id, day) REFERENCES journals(trip_id, day) ON DELETE CASCADE
);
```

No version history (FR-6.3): one row per slot, overwritten in place.

## 6. View models (`domain/views.py` / `services/journal.py`)

```python
class SentenceView(BaseModel):
    text_html: str             # escaped text, citations replaced by citation buttons
    supported: bool

class ParagraphView(BaseModel):
    slot: Slot
    heading: str               # "Day summary" or the stop name and local time
    owner: Owner
    text: str                  # raw, for the editor
    sentences: list[SentenceView]
    state: Literal["written", "not_written", "removed"]   # "" generated -> not_written; "" user -> removed

class JournalView(BaseModel):
    trip_id: int
    day: LocalDate
    tone: Tone | None
    paragraphs: list[ParagraphView]
    unsupported_count: int
    trace: list[ToolCallRecord]
    model_name: str | None
    prompt_version: str | None
    generated_at: str | None
    message: str | None        # e.g. "The agent did not write 2 paragraphs; regenerate to try again."

class CitationTarget(BaseModel):
    kind: CitationKind
    id: int
    found: bool
    title: str                 # note: stop name; stop: stop name; photo: file name
    time_label: str            # local time or time range
    body: str | None           # note text, or "N notes" for a stop
```

`JournalView.tone` is `None` and `paragraphs` empty when no journal exists yet.

## 7. Interface changes against `component-methods.md` and U1-U3 code

| Id | Change | Why |
|---|---|---|
| IC-1 | `MergeResult` gains `missing_slots`; module gains `slot_order`, `slots_to_write`, `stop_slot`, `parse_slot` | Q2 A, Q9 A |
| IC-2 | `JournalAgent.write_day` gains `user_paragraphs`; `JournalDraft` gains `dropped` | Q8 A, Q9 A |
| IC-3 | `JournalRepository.save(...)` is split into `save_generated` and `save_user_edit`, both atomic | Q11 A |
| IC-4 | `JournalView` gains `model_name`, `prompt_version`, `generated_at`; `ParagraphView` gains `heading`, `state`, `sentences` | Q4 A, Q17 A |
| IC-5 | New `JournalService.get_citation(trip_id, kind, id) -> CitationTarget` | Q16 A |
| IC-6 | Tone prompts are fragments `journal_tone_<tone>.md` composed by JournalAgent with `journal.md`; `PromptLibrary` itself is unchanged | Q13 A |
| IC-7 | `JournalService.start_generation` returns `JobRef \| NothingToRegenerate` (no job when every slot is user-owned) | Q12 A |
