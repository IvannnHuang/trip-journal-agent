# ADDED [PROMPT #13]: background job runner (C09, LC-2, JB-1..JB-8, NP-1, NP-2).
# AI-assisted, Claude Opus 5.5.
"""In-memory jobs: one running at a time, a 5-minute deadline, the last 20 finished kept."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel

from trip_journal.agent.loop import ToolCallRecord
from trip_journal.config import JOB_TIMEOUT_S, MAX_FINISHED_JOBS
from trip_journal.logs import current_job_id, kv
from trip_journal.services.errors import (
    JobTimeoutError,
    ModelBusyError,
    NotFoundError,
    UserFacingError,
    to_user_facing,
)

log = logging.getLogger(__name__)

JobState = Literal["running", "done", "failed"]


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class JobStatus(BaseModel):
    job_id: str
    kind: str
    state: JobState = "running"
    step: str = "starting"
    result: dict[str, Any] | None = None
    error: UserFacingError | None = None
    trace: list[ToolCallRecord] = []
    started_at: str
    finished_at: str | None = None


class JobRef(BaseModel):
    job_id: str
    kind: str


class JobProgress:
    """Given to a job's work function. Callable with a string, like a ProgressCallback."""

    def __init__(self, status: JobStatus) -> None:
        self._status = status

    def step(self, message: str) -> None:
        self._status.step = message[:200]

    def __call__(self, message: str) -> None:
        self.step(message)

    def tool_call(self, record: ToolCallRecord) -> None:
        self._status.trace.append(record)  # JB-8: records hold ids only


JobWork = Callable[[JobProgress], Awaitable[BaseModel]]


class JobRunner:
    def __init__(
        self, max_finished: int = MAX_FINISHED_JOBS, timeout_s: float = JOB_TIMEOUT_S
    ) -> None:
        self.max_finished = max_finished
        self.timeout_s = timeout_s
        self._jobs: dict[str, JobStatus] = {}  # insertion order = start order
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def running(self) -> JobStatus | None:
        return next((j for j in self._jobs.values() if j.state == "running"), None)

    def start(self, kind: str, work: JobWork) -> JobRef:
        """JB-1, JB-2. Must be called from inside the event loop."""
        if self.running is not None:
            raise ModelBusyError("a job is running")
        status = JobStatus(job_id=uuid.uuid4().hex, kind=kind, started_at=_now())
        self._jobs[status.job_id] = status
        task = asyncio.create_task(self._run(status, work), name=f"job-{status.job_id}")
        self._tasks[status.job_id] = task
        job_id = status.job_id
        task.add_done_callback(lambda _t: self._tasks.pop(job_id, None))
        return JobRef(job_id=status.job_id, kind=kind)

    def status(self, job_id: str) -> JobStatus:
        """JB-7."""
        job = self._jobs.get(job_id)
        if job is None:
            raise NotFoundError("job not found")
        return job

    async def wait(self, job_id: str) -> JobStatus:
        """Test helper: wait until the job's task ends."""
        task = self._tasks.get(job_id)
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        return self.status(job_id)

    async def _run(self, status: JobStatus, work: JobWork) -> None:
        current_job_id.set(status.job_id)  # LC-8: this task's context only
        log.info(kv("job.start", kind=status.kind))
        progress = JobProgress(status)
        try:
            async with asyncio.timeout(self.timeout_s):  # JB-3
                result = await work(progress)
        except TimeoutError:
            self._fail(status, JobTimeoutError("job timeout"))
        except asyncio.CancelledError:
            self._fail(status, JobTimeoutError("job cancelled"))
            raise
        except Exception as exc:
            self._fail(status, exc)
        else:
            status.result = result.model_dump(mode="json")
            status.state = "done"
            status.finished_at = _now()
            log.info(kv("job.done", kind=status.kind, tool_calls=len(status.trace)))
        finally:
            self._prune()

    def _fail(self, status: JobStatus, exc: BaseException) -> None:
        """JB-4: store the mapped error with the trace so far."""
        error = to_user_facing(exc)
        if not error.trace:
            error.trace = list(status.trace)
        status.error = error
        status.state = "failed"
        status.finished_at = _now()
        if error.code == "internal_error":
            log.error(kv("job.failed", kind=status.kind, code=error.code), exc_info=exc)
        else:
            log.warning(kv("job.failed", kind=status.kind, code=error.code))

    def _prune(self) -> None:
        """JB-5: keep the newest finished jobs; never drop a running one."""
        finished = [j.job_id for j in self._jobs.values() if j.state != "running"]
        for job_id in finished[: max(0, len(finished) - self.max_finished)]:
            del self._jobs[job_id]
