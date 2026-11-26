# U1 Foundation - NFR Design Plan

**Stage**: Construction - NFR Design (unit U1 Foundation)
**Inputs**: `aidlc-docs/construction/u1-foundation/nfr-requirements/` (`nfr-requirements.md`, `tech-stack-decisions.md`), `aidlc-docs/construction/u1-foundation/functional-design/` (4 files), `aidlc-docs/inception/application-design/component-methods.md` and `component-dependency.md` (async signatures, `asyncio` job task, httpx async)
**Outputs**: `aidlc-docs/construction/u1-foundation/nfr-design/nfr-design-patterns.md`, `aidlc-docs/construction/u1-foundation/nfr-design/logical-components.md`
**Extensions**: Security Baseline and Resiliency Baseline opted out (skipped). PBT Partial: PBT-08 (reproducibility) and PBT-09 (framework) shape the Hypothesis profile design here; PBT-02/03/07 apply at Code Generation.

## Plan steps

- [x] 1. Analyze the NFR Requirements and Functional Design (Step 1)
- [x] 2. Write this plan with questions (Steps 2-4)
- [x] 3. Collect the owner's answers (interview) and check them for ambiguity (Step 5)
- [x] 4. Write `nfr-design-patterns.md`: timeout patterns (job 300 s, model call 120 s, status 2 s, Nominatim 5 s), Nominatim rate limiter, no-retry failure handling, graceful degradation, logging pattern, Hypothesis profiles (Step 6)
- [x] 5. Write `logical-components.md`: the U1 logical components (timeout policy, job store, rate limiter, place cache, log setup, test profiles) and how they connect (Step 6)
- [x] 6. Present the completion message and wait for approval (Steps 7-8)

## Already fixed by the inputs (no question)

| Item | Fixed value | Source |
|---|---|---|
| Concurrency model | `asyncio` throughout: `async def` services, tools and `LLMClient.chat`; jobs are `asyncio` tasks; httpx async for Ollama status and Nominatim | `component-methods.md`, `component-dependency.md` |
| Job limit | 300 s, fixed in code, `JobRunner(timeout_s=300)` injectable for tests | U1-NFR-P.3, IC-3 |
| Retries | None, for model calls and jobs. This also means the `openai` client is created with `max_retries=0` (its default is 2, which would break U1-NFR-R.5) | U1-NFR-R.5, FD Q26 A |
| Status check | 2 s, no cache | ST-1, ST-2 |
| Logging | stdlib `logging`, console only, `TRIP_JOURNAL_LOG_LEVEL` | U1-NFR-L.1, L.2 |
| Hypothesis profiles | `default` 100, `ci` 500, `print_blob=True`, chosen by `HYPOTHESIS_PROFILE`, in `tests/conftest.py` | U1-NFR-T.3 |

## Categories with no open question

| Category | Why no question | Source |
|---|---|---|
| Scalability patterns | Single user, one running job, 20 finished jobs in memory. No scaling mechanism needed. | U1-NFR-S.1, S.2 |
| Security patterns | Security Baseline opted out; localhost binding, base-URL check, argument validation and delimited tool results already set. | U1-NFR-SP.1 to SP.4 |
| Resilience: retry / circuit breaker | No retry was chosen; a circuit breaker adds nothing because the status check runs before every job (ST-1, ST-7). | U1-NFR-R.5 |
| Logical components: queue, external cache | One job at a time (busy error, not a queue); place cache is the SQLite table already designed (PL-5, PL-6). | JB-1, PL-6 |

## Question 1
How is the 120 s limit on one model call enforced?

A) `asyncio.timeout(120)` around each `LLMClient.chat` call (wall-clock limit on the whole call), plus the same 120 s as the `openai` client timeout as a backstop, and `max_retries=0`

B) Only the `openai` client timeout (120 s, `max_retries=0`); this is an httpx connect/read timeout, so a reply that keeps sending bytes slowly could run longer than 120 s

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
U1 code is async, but `sqlite3` is blocking. How do repository calls (notes search, settings, place cache) run?

A) Call `sqlite3` directly in the event loop. U1 queries are local and take milliseconds; this is the simplest, and a cancelled job stops at the next `await`

B) Run every repository call in a worker thread with `asyncio.to_thread`, so the event loop never blocks (more code; a cancelled job still waits for the running query to end)

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
How does the Nominatim limit (at most 1 request per second, 5 s timeout) work?

A) One process-wide `asyncio.Lock` held from the wait through the end of the request; the next request starts at least 1 s after the previous one started (monotonic clock). The 5 s timeout covers the HTTP request only, not the wait for the lock

B) The same lock, but the 5 s also covers the wait, so a lookup never takes more than 5 s in total (a waiting lookup may give up and return no name)

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
Hypothesis has a per-example time limit (`deadline`, 200 ms by default). Slow laptops can make tests fail only because of time. What should the profiles use?

A) `deadline=None` in both `default` and `ci` (no time limit per example; tests fail only on wrong results)

B) Keep the 200 ms default in `default`; `deadline=None` only in `ci`

C) Keep the 200 ms default in both

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
What format do console log lines use?

A) Plain text, one line per event: `time level logger message`, with fields in the message as `key=value` (for example `job_id=... step=3 duration_s=41.2`); every line written inside a job carries its `job_id` (through a context variable)

B) JSON lines (one JSON object per line), with `job_id` as a field

C) Plain text without a `job_id` on every line (only on job start and end)

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6
How are uvicorn's own log lines (server start, access log) handled?

A) Use the same handler, format and level as the app (one console format); access lines stay on at INFO

B) Same handler and format, but access lines are turned off (fewer lines while polling job status)

C) Leave uvicorn's default logging alone

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Answer analysis

All 6 answers are A (chosen by the owner in the interview, 2026-11-26). No answer is vague or conflicts with another, so no follow-up question is needed. Q2 A (blocking `sqlite3` in the event loop) and Q1 A (`asyncio.timeout`) fit together: a cancel lands at the next `await`, and U1 queries take milliseconds, so a timeout is delayed by at most one query. Q6 A keeps access lines; they contain only method, path and status, and U1 sends no note text in URLs (forms use POST), so U1-NFR-L.2 still holds.
