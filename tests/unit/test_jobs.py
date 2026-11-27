# ADDED [PROMPT #13]: job runner tests (JB-1..JB-8). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from trip_journal.agent.loop import ToolCallRecord
from trip_journal.services.errors import ModelBusyError, ModelCallError, NotFoundError
from trip_journal.services.jobs import JobProgress, JobRunner


class Out(BaseModel):
    text: str


async def test_done_job_keeps_result_and_trace() -> None:
    runner = JobRunner()

    async def work(progress: JobProgress) -> Out:
        progress("thinking")
        progress.tool_call(ToolCallRecord(step=1, name="list_day_stops", arguments={}))
        return Out(text="hi")

    ref = runner.start("journal", work)
    assert len(ref.job_id) == 32
    status = await runner.wait(ref.job_id)
    assert status.state == "done" and status.result == {"text": "hi"}
    assert status.step == "thinking" and [r.name for r in status.trace] == ["list_day_stops"]
    assert status.finished_at is not None


async def test_one_running_job_at_a_time() -> None:
    runner = JobRunner()
    gate = asyncio.Event()

    async def work(progress: JobProgress) -> Out:
        await gate.wait()
        return Out(text="x")

    ref = runner.start("a", work)
    with pytest.raises(ModelBusyError):
        runner.start("b", work)
    gate.set()
    await runner.wait(ref.job_id)
    runner.start("c", work)  # free again


async def test_failure_keeps_trace() -> None:
    runner = JobRunner()

    async def work(progress: JobProgress) -> Out:
        progress.tool_call(ToolCallRecord(step=1, name="search_notes", arguments={"query": "x"}))
        raise ModelCallError("error")

    status = await runner.wait(runner.start("a", work).job_id)
    assert status.state == "failed" and status.error is not None
    assert status.error.code == "model_error"
    assert [r.name for r in status.error.trace] == ["search_notes"]


async def test_timeout() -> None:
    runner = JobRunner(timeout_s=0.01)

    async def work(progress: JobProgress) -> Out:
        await asyncio.sleep(5)
        return Out(text="late")

    status = await runner.wait(runner.start("a", work).job_id)
    assert status.error is not None and status.error.code == "job_timeout"


async def test_unexpected_error_hides_details() -> None:
    runner = JobRunner()

    async def work(progress: JobProgress) -> Out:
        raise RuntimeError("private note text")

    status = await runner.wait(runner.start("a", work).job_id)
    assert status.error is not None and status.error.code == "internal_error"
    assert "private" not in status.error.message


async def test_keeps_only_newest_finished_jobs() -> None:
    runner = JobRunner(max_finished=2)

    async def work(progress: JobProgress) -> Out:
        return Out(text="x")

    ids = []
    for _ in range(4):
        ref = runner.start("a", work)
        await runner.wait(ref.job_id)
        ids.append(ref.job_id)
    with pytest.raises(NotFoundError):
        runner.status(ids[0])
    assert runner.status(ids[3]).state == "done"


def test_unknown_job() -> None:
    with pytest.raises(NotFoundError):
        JobRunner().status("nope")


# ADDED [PROMPT #17]: CI-3, a cancelled job is reported as job_cancelled (D-11).
async def test_cancel_is_reported_as_job_cancelled() -> None:
    runner = JobRunner()
    started = asyncio.Event()

    async def work(progress: JobProgress) -> Out:
        started.set()
        await asyncio.sleep(5)
        return Out(text="never")

    ref = runner.start("a", work)
    await started.wait()
    runner._tasks[ref.job_id].cancel()
    status = await runner.wait(ref.job_id)
    assert status.state == "failed" and status.error is not None
    assert status.error.code == "job_cancelled"
    assert runner.running is None


# ADDED [PROMPT #25]: U3 per-job limit (IC-1). None keeps the runner default.
async def test_per_job_timeout_overrides_the_default() -> None:
    runner = JobRunner(timeout_s=5)

    async def work(progress: JobProgress) -> Out:
        await asyncio.sleep(1)
        return Out(text="late")

    status = await runner.wait(runner.start("a", work, timeout_s=0.01).job_id)
    assert status.error is not None and status.error.code == "job_timeout"
    assert "over 1 minute" in status.error.message


async def test_longer_per_job_timeout_lets_the_job_finish() -> None:
    runner = JobRunner(timeout_s=0.01)

    async def work(progress: JobProgress) -> Out:
        await asyncio.sleep(0.05)
        return Out(text="done")

    status = await runner.wait(runner.start("a", work, timeout_s=5).job_id)
    assert status.error is None and status.state == "done"
