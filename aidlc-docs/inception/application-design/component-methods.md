# Component Methods

The signatures below are Python-style and define **interfaces only**. Model fields are outlined, not complete. Validation rules, the merge algorithm, sentence splitting and the full schema columns are defined later, in Functional Design for each unit.

**Conventions**
- Ids named `*_id: int` are SQLite row ids (design Q8 A). A field named `source_id: str` is the id from the import file.
- `LocalDate` is an ISO date string `YYYY-MM-DD`. Times are UTC ISO-8601 strings plus `utc_offset_minutes: int`.
- `Tone = Literal["casual", "concise", "detailed"]`
- `Slot = Literal["summary"] | int`, meaning the summary paragraph or a `stop_id` (design Q9 A)
- `Owner = Literal["generated", "user"]`
- Service methods raise the domain errors listed at the end. Routers map them to HTTP responses.

---

## Domain (`domain/`)

### C17 Import Schema and Validation (`domain/import_schema.py`)

```python
class TripMeta(BaseModel):          # extra="forbid" on every import model
    trip_id: str
    title: str
    home_timezone: str | None = None

class StopIn(BaseModel):
    id: str
    name: str | None = None          # imported place name, may be missing
    start_utc: datetime
    end_utc: datetime
    utc_offset_minutes: int
    lat: float
    lon: float

class NoteIn(BaseModel):
    id: str
    text: str
    time_utc: datetime
    utc_offset_minutes: int
    stop_id: str | None = None       # reference to StopIn.id

class PhotoIn(BaseModel):
    id: str
    time_utc: datetime
    utc_offset_minutes: int
    lat: float | None = None
    lon: float | None = None
    file_name: str | None = None

class TripFile(BaseModel):
    trip: TripMeta
    stops: list[StopIn]
    notes: list[NoteIn]
    photos: list[PhotoIn] = []
    route_summary: str | None = None

class ImportIssue(BaseModel):
    location: str                    # e.g. "stops[4].end_utc"
    message: str

def parse_trip_file(raw: bytes, max_bytes: int = 20 * 1024 * 1024) -> TripFile:
    """Size check, JSON parse, schema and cross-record checks. Raises ImportValidationError(issues)."""
```

### C18 Day Derivation (`domain/days.py`)

```python
def local_date(time_utc: datetime, utc_offset_minutes: int) -> LocalDate: ...
def group_stops_by_day(stops: Sequence[StopIn]) -> dict[LocalDate, list[StopIn]]:
    """Group by the local date of each stop's start; stops within a day are ordered by start time."""
```

### C19 Citations and Grounding (`domain/grounding.py`)

```python
CitationKind = Literal["stop", "note", "photo"]
NOT_IN_RECORDS = "That is not in your records."

class Citation(NamedTuple):
    kind: CitationKind
    record_id: int

class SentenceCheck(BaseModel):
    sentence: str
    citations: list[Citation]
    supported: bool

def split_sentences(text: str) -> list[str]: ...
def extract_citations(sentence: str) -> list[Citation]: ...
def check_text(text: str, known_ids: set[Citation], allow_not_in_records: bool = False) -> list[SentenceCheck]: ...
def find_unsupported_sentences(text: str, known_ids: set[Citation], allow_not_in_records: bool = False) -> list[str]: ...
```

### C20 Journal Merge (`domain/journal_merge.py`)

```python
class Paragraph(BaseModel):
    slot: Slot
    text: str
    owner: Owner

class MergeResult(BaseModel):
    paragraphs: list[Paragraph]          # in display order: summary, then stops by start time
    replaced_slots: list[Slot]
    nothing_to_regenerate: bool

def merge_journal(existing: Sequence[Paragraph], draft: Mapping[Slot, str], slot_order: Sequence[Slot]) -> MergeResult:
    """User-owned paragraphs are kept exactly as they are; only generated or missing slots take draft text."""

def mark_user_edit(paragraphs: Sequence[Paragraph], slot: Slot, new_text: str) -> list[Paragraph]: ...
```

---

## Agent (`agent/`)

### C10 LLM Client (`agent/llm.py`)

```python
class ToolCall(BaseModel):
    id: str
    name: str
    arguments_json: str

class LLMReply(BaseModel):
    content: str | None
    tool_calls: list[ToolCall]

class ModelStatus(BaseModel):
    reachable: bool
    model_installed: bool
    model_name: str
    base_url: str

class LLMClient(Protocol):
    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
                   response_format: dict[str, Any] | None = None) -> LLMReply: ...
    async def status(self) -> ModelStatus: ...

class OllamaClient:                    # implements LLMClient with openai.AsyncOpenAI(base_url=..., api_key="ollama")
    def __init__(self, base_url: str, model: str, timeout_s: float) -> None: ...

class FakeLLMClient:                   # implements LLMClient for tests
    def __init__(self, script: Sequence[LLMReply]) -> None: ...
    calls: list[list[dict[str, Any]]]  # every message list it received
```

### C11 AgentLoop (`agent/loop.py`)

```python
class ToolCallRecord(BaseModel):
    step: int
    name: str
    arguments: dict[str, Any]
    returned_ids: list[Citation]
    error: str | None = None

class AgentResult(BaseModel):
    final_text: str | None
    trace: list[ToolCallRecord]
    stopped_reason: Literal["final_answer", "step_limit"]

ProgressCallback = Callable[[str], None]   # e.g. "calling list_day_stops"

class AgentLoop:
    def __init__(self, llm: LLMClient, registry: ToolRegistry, max_steps: int = 8) -> None: ...
    async def run(self, system_prompt: str, messages: list[dict[str, Any]], context: ToolContext,
                  on_step: ProgressCallback | None = None) -> AgentResult: ...
```

### C12 Tool Registry and Tools (`agent/tools.py`)

```python
@dataclass(frozen=True)
class ToolContext:
    trip_id: int                        # the active trip; never chosen by the model
    repos: Repositories
    places: PlaceLookup

class ToolRegistry:
    def register(self, name: str, args_model: type[BaseModel], fn: ToolFn, description: str) -> None: ...
    def schemas(self) -> list[dict[str, Any]]:          # OpenAI "tools" format, built from args_model
    async def execute(self, call: ToolCall, context: ToolContext) -> ToolOutcome:
        """Validate the arguments, run the tool, and return a delimited JSON result or an error result."""

# Tool argument models and results
class ListDayStopsArgs(BaseModel):  day: LocalDate
class GetStopNotesArgs(BaseModel):  stop_id: int
class FindPhotosArgs(BaseModel):    start_local: datetime; end_local: datetime
class SearchNotesArgs(BaseModel):   query: str = Field(min_length=1, max_length=100); limit: int = Field(default=10, le=20)
class LookupPlaceArgs(BaseModel):   lat: float = Field(ge=-90, le=90); lon: float = Field(ge=-180, le=180)

async def list_day_stops(args: ListDayStopsArgs, ctx: ToolContext) -> list[StopView]: ...
async def get_stop_notes(args: GetStopNotesArgs, ctx: ToolContext) -> list[NoteView]: ...
async def find_photos(args: FindPhotosArgs, ctx: ToolContext) -> list[PhotoView]: ...
async def search_notes(args: SearchNotesArgs, ctx: ToolContext) -> list[NoteHit]: ...
async def lookup_place(args: LookupPlaceArgs, ctx: ToolContext) -> PlaceName: ...

def default_registry() -> ToolRegistry: ...
```

### C13 JournalAgent (`agent/journal.py`)

```python
class JournalDraft(BaseModel):
    slots: dict[Slot, str]              # "summary" plus one entry per stop_id
    trace: list[ToolCallRecord]
    stopped_reason: Literal["final_answer", "step_limit"]

class JournalAgent:
    def __init__(self, loop: AgentLoop, prompts: PromptLibrary) -> None: ...
    async def write_day(self, context: ToolContext, day: LocalDate, tone: Tone,
                        slots_to_write: Sequence[Slot], on_step: ProgressCallback | None = None) -> JournalDraft: ...
```

### C14 ChatAgent (`agent/chat.py`)

```python
class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatAnswer(BaseModel):
    text: str
    trace: list[ToolCallRecord]
    stopped_reason: Literal["final_answer", "step_limit"]

class ChatAgent:
    def __init__(self, loop: AgentLoop, prompts: PromptLibrary, max_history_turns: int = 10) -> None: ...
    async def answer(self, context: ToolContext, history: Sequence[ChatTurn], question: str,
                     on_step: ProgressCallback | None = None) -> ChatAnswer: ...
```

### C15 NoteOrganizer (`agent/organizer.py`)

```python
Category = Literal["food", "scene", "logistics", "feedback", "other"]

class NoteSuggestion(BaseModel):
    note_id: int
    category: Category
    suggested_stop_id: int | None
    dish: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    tip: str | None = None

class OrganizerBatchResult(BaseModel):
    suggestions: list[NoteSuggestion]
    dropped: list[str]                  # reasons suggestions were rejected by validation

class NoteOrganizer:
    def __init__(self, llm: LLMClient, prompts: PromptLibrary) -> None: ...
    async def organize_batch(self, stops: Sequence[StopView], notes: Sequence[NoteView]) -> OrganizerBatchResult: ...
```

### C16 Prompt Library (`agent/prompts/__init__.py`)

```python
class PromptLibrary:
    def __init__(self, directory: Path) -> None: ...
    def get(self, name: Literal["journal", "chat", "organizer"], tone: Tone | None = None) -> str: ...
    @property
    def version(self) -> str: ...      # recorded with saved traces and evaluation runs
```

---

## Services (`services/`)

### C03 ImportService

```python
class TripSummary(BaseModel):
    trip_id: int; source_id: str; title: str
    days: list[DaySummary]              # local_date, stop_count, note_count, photo_count

class ImportService:
    def import_trip(self, raw: bytes, filename: str) -> TripSummary:
        """Raises ImportValidationError, TripAlreadyExistsError."""
```

### C04 TripService

```python
class TripService:
    def list_trips(self) -> list[TripSummary]: ...
    def get_active_trip_id(self) -> int | None: ...
    def set_active_trip(self, trip_id: int) -> None: ...
    def get_day(self, trip_id: int, day: LocalDate) -> DayView: ...   # stops, notes, organized fields, photos, prev/next day
    def delete_trip(self, trip_id: int) -> None: ...                    # cascades to journals and suggestions
```

### C05 OrganizerService

```python
class OrganizerService:
    def start(self, trip_id: int, day: LocalDate | None) -> JobRef: ...            # None = whole trip
    async def organize_now(self, trip_id: int, day: LocalDate | None,
                           on_step: ProgressCallback | None = None) -> OrganizerRunSummary: ...  # used by the job and by the evaluation script
    def list_suggestions(self, trip_id: int, day: LocalDate) -> list[SuggestionView]: ...
    def accept(self, suggestion_id: int) -> None: ...
    def edit_and_accept(self, suggestion_id: int, edit: SuggestionEdit) -> None: ...
    def reject(self, suggestion_id: int) -> None: ...
    def accept_all_pending(self, trip_id: int, day: LocalDate) -> int: ...          # number accepted
```

### C06 JournalService

```python
class JournalView(BaseModel):
    trip_id: int; day: LocalDate; tone: Tone | None
    paragraphs: list[ParagraphView]     # slot, text, owner, sentence checks
    unsupported_count: int
    trace: list[ToolCallRecord]
    message: str | None                 # e.g. "Nothing to regenerate: every paragraph is yours."

class JournalService:
    def start_generation(self, trip_id: int, day: LocalDate, tone: Tone) -> JobRef: ...   # first run or regenerate
    def get_journal(self, trip_id: int, day: LocalDate) -> JournalView | None: ...
    def edit_paragraph(self, trip_id: int, day: LocalDate, slot: Slot, text: str) -> JournalView: ...
    async def generate_now(self, trip_id: int, day: LocalDate, tone: Tone,
                           on_step: ProgressCallback | None = None) -> JournalView: ...  # used by the job and by the evaluation script
```

### C07 ChatService

```python
class AnswerView(BaseModel):
    text: str
    sentences: list[SentenceCheck]
    trace: list[ToolCallRecord]

class ChatService:
    def start_question(self, trip_id: int, history: list[ChatTurn], question: str) -> JobRef: ...
    async def answer_now(self, trip_id: int, history: list[ChatTurn], question: str,
                         on_step: ProgressCallback | None = None) -> AnswerView: ...
```

### C08 SettingsService

```python
class Settings(BaseModel):
    model_name: str = "qwen3:8b"
    ollama_base_url: str = "http://localhost:11434/v1"
    place_lookup_enabled: bool = False

class SettingsService:
    def get(self) -> Settings: ...                    # SQLite value > environment variable > default
    def update(self, change: SettingsUpdate) -> Settings: ...
    async def model_status(self) -> ModelStatus: ...
```

### C09 JobRunner

```python
JobState = Literal["running", "done", "failed"]

class JobRef(BaseModel):
    job_id: str

class JobStatus(BaseModel):
    job_id: str; kind: Literal["organize", "journal", "chat"]
    state: JobState
    step: str | None                     # latest progress message
    result: dict[str, Any] | None        # JournalView, AnswerView or organizer summary when done
    error: UserFacingError | None

class JobRunner:
    def start(self, kind: str, work: Callable[[ProgressCallback], Awaitable[BaseModel]]) -> JobRef:
        """Raises ModelBusyError if a job is already running."""
    def status(self, job_id: str) -> JobStatus: ...
```

---

## Data and External

### C21 Database

```python
def connect(path: Path) -> sqlite3.Connection: ...      # foreign_keys=ON, row_factory
def init_schema(conn: sqlite3.Connection) -> None: ...   # runs schema.sql (tables + FTS5)
@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]: ...
```

### C22 Repositories (main methods)

```python
class TripRepository:       def add(self, meta) -> int; def get_by_source_id(self, source_id: str) -> TripRow | None; def list(self); def delete(self, trip_id: int)
                            def known_citation_ids(self, trip_id: int) -> set[Citation]   # every stop, note and photo id in the trip, for grounding
class StopRepository:       def add_many(self, trip_id, stops) -> dict[str, int]; def list_for_day(self, trip_id, day) -> list[StopRow]; def get(self, trip_id, stop_id)
class NoteRepository:       def add_many(...); def list_for_stop(self, trip_id, stop_id); def list_for_day(self, trip_id, day); def search(self, trip_id, query, limit) -> list[NoteHit]
class PhotoRepository:      def add_many(...); def count_for_stop(...); def find_between(self, trip_id, start_local, end_local)
class SuggestionRepository: def replace_pending(self, trip_id, suggestions); def list_for_day(...); def set_status(self, suggestion_id, status, edit=None)
class JournalRepository:    def get(self, trip_id, day) -> StoredJournal | None; def save(self, trip_id, day, paragraphs, tone, trace, prompt_version)
class SettingsRepository:   def get_all(self) -> dict[str, str]; def set(self, key: str, value: str)
class PlaceCacheRepository: def get(self, lat_key: str, lon_key: str) -> str | None; def put(self, lat_key, lon_key, name)
```

### C23 PlaceLookup

```python
class PlaceName(BaseModel):
    name: str | None
    source: Literal["import", "cache", "nominatim", "none"]

class PlaceLookup:
    def __init__(self, is_enabled: Callable[[], bool], cache: PlaceCacheRepository, http: httpx.AsyncClient,
                 min_interval_s: float = 1.0, user_agent: str = "TripJournalAgent/0.1 (course project)") -> None: ...
    async def lookup(self, lat: float, lon: float, imported_name: str | None) -> PlaceName: ...
```

---

## Errors (`services/errors.py`)

| Error | Raised by | HTTP (API) | Page behavior |
|---|---|---|---|
| `ImportValidationError(issues)` | ImportService | 422 | List of issues, each naming field and record |
| `TripAlreadyExistsError(source_id)` | ImportService | 409 | "Delete the existing trip first" |
| `NotFoundError` | all services | 404 | Not-found message |
| `ModelUnavailableError(status)` | services before starting a job | 503 | How to start Ollama or pull the model (US-19) |
| `ModelBusyError` | JobRunner | 429 | "The model is busy, try again in a moment" |
| `AgentStepLimitError(trace)` | JournalService, ChatService when `stopped_reason == "step_limit"` | Job `failed` | "The agent could not finish", with the trace (US-20) |
