# ADDED [PROMPT #13]: advisory stateful test P-J1 for the job runner (JB-1, JB-2, JB-5).
# AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import asyncio

from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
from pydantic import BaseModel

from trip_journal.services.errors import ModelBusyError
from trip_journal.services.jobs import JobProgress, JobRunner

MAX_FINISHED = 5


class Out(BaseModel):
    ok: bool


class JobMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.loop = asyncio.new_event_loop()
        self.runner = JobRunner(max_finished=MAX_FINISHED)
        self.gate: asyncio.Event | None = None
        self.current: str | None = None
        self.seen: list[str] = []

    def _start(self, fail: bool) -> str:
        gate = asyncio.Event()

        async def work(progress: JobProgress) -> Out:
            await gate.wait()
            if fail:
                raise RuntimeError("boom")
            return Out(ok=True)

        async def go() -> str:
            return self.runner.start("demo", work).job_id

        job_id = self.loop.run_until_complete(go())
        self.gate = gate
        return job_id

    @rule(fail=st.booleans())
    def start(self, fail: bool) -> None:
        if self.current is None:
            self.current = self._start(fail)
            self.seen.append(self.current)
        else:
            try:
                self._start(fail)
            except ModelBusyError:
                return
            raise AssertionError("a second job started while one was running")

    @rule()
    def finish(self) -> None:
        if self.current is None or self.gate is None:
            return
        self.gate.set()
        status = self.loop.run_until_complete(self.runner.wait(self.current))
        assert status.state in ("done", "failed")
        self.current = None

    @invariant()
    def at_most_one_running(self) -> None:
        jobs = list(self.runner._jobs.values())
        assert sum(j.state == "running" for j in jobs) <= 1
        assert sum(j.state != "running" for j in jobs) <= MAX_FINISHED
        assert len({j.job_id for j in jobs}) == len(jobs)
        assert len(set(self.seen)) == len(self.seen)

    def teardown(self) -> None:
        if self.gate is not None:
            self.gate.set()
        if self.current is not None:
            self.loop.run_until_complete(self.runner.wait(self.current))
        self.loop.close()


TestJobMachine = JobMachine.TestCase
