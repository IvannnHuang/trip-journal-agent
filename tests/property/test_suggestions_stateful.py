# ADDED [PROMPT #25]: U3 review state machine P-O4 (plan step 19, OR-ST, PBT-03 stateful).
# AI-assisted, Claude Opus 5.5.
"""Accept / edit / reject / undo / accept all / re-run against a model of OR-ST.

Checks OR-ST1 (one row per note) and that a decided row changes only through Undo (OR-ST2).
FakeLLMClient only (LabellingLLM): no test reaches a real Ollama.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from tests.fixtures.organizer import (
    NEXT_DAY,
    SAMPLE_DAY,
    LabellingLLM,
    import_two_day_trip,
    review_client,
    run_organizer,
)
from trip_journal.domain.organizer import CATEGORIES

DAYS = (SAMPLE_DAY, NEXT_DAY)
DECIDED = ("accepted", "edited", "rejected")
NEXT_STATUS = {"accept": "accepted", "reject": "rejected", "edit": "edited"}
VALUE_KEYS = ("category", "stop_id", "dish", "rating", "tip", "model_values")


def values(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row[k] for k in VALUE_KEYS}


class SuggestionMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.llm = LabellingLLM()
        self._ctx = review_client(self.llm)
        self.client: TestClient = self._ctx.__enter__()
        self.trip_id = import_two_day_trip(self.client)
        self.status: dict[int, str] = {}  # model: suggestion id -> expected status
        self.frozen: dict[int, dict[str, Any]] = {}  # decided rows: values at decision time

    def rows(self) -> dict[int, dict[str, Any]]:
        out: dict[int, dict[str, Any]] = {}
        for day in DAYS:
            reply = self.client.get(f"/api/trips/{self.trip_id}/days/{day}/suggestions")
            assert reply.status_code == 200
            out.update({r["suggestion_id"]: r for r in reply.json()})
        return out

    def pick(self, index: int) -> int | None:
        ids = sorted(self.status)
        return ids[index % len(ids)] if ids else None

    @rule(day=st.one_of(st.none(), st.sampled_from(DAYS)), category=st.sampled_from(CATEGORIES))
    def rerun(self, day: str | None, category: str) -> None:
        self.llm.category = category
        run_organizer(self.client, self.trip_id, day)
        for sid in self.rows():
            self.status.setdefault(sid, "pending")  # new rows start pending

    @rule(index=st.integers(min_value=0, max_value=7), action=st.sampled_from(sorted(NEXT_STATUS)))
    def decide(self, index: int, action: str) -> None:
        sid = self.pick(index)
        if sid is None:
            return
        edit = {"category": "scene", "rating": 4.0, "tip": "  Go early.  "}
        if action == "edit":
            reply = self.client.put(f"/api/suggestions/{sid}", json=edit)
        else:
            reply = self.client.post(f"/api/suggestions/{sid}/{action}")
        if self.status[sid] != "pending":  # only pending can be decided (FA-8)
            assert reply.status_code == 409 and reply.json()["code"] == "suggestion_state"
            return
        assert reply.status_code == 200, reply.text
        row = reply.json()
        assert row["status"] == NEXT_STATUS[action]
        if action == "edit":  # PBT-02: the saved edit reads back cleaned (OR-F2, OR-F3)
            assert (row["category"], row["rating"], row["tip"]) == ("scene", 4, "Go early.")
        else:
            assert {k: row[k] for k in VALUE_KEYS[:5]} == row["model_values"]
        self.status[sid] = row["status"]
        self.frozen[sid] = values(row)

    @rule(index=st.integers(min_value=0, max_value=7))
    def undo(self, index: int) -> None:
        sid = self.pick(index)
        if sid is None:
            return
        reply = self.client.post(f"/api/suggestions/{sid}/undo")
        if self.status[sid] not in DECIDED:
            assert reply.status_code == 409 and reply.json()["code"] == "suggestion_state"
            return
        assert reply.status_code == 200 and reply.json()["status"] == "pending"
        row = reply.json()
        assert {k: row[k] for k in VALUE_KEYS[:5]} == row["model_values"]  # model values back
        self.status[sid] = "pending"
        del self.frozen[sid]

    @rule(day=st.sampled_from(DAYS))
    def accept_all(self, day: str) -> None:
        rows = self.rows()
        pending = [
            s for s, r in rows.items() if r["local_date"] == day and self.status[s] == "pending"
        ]
        url = f"/api/trips/{self.trip_id}/days/{day}/suggestions/accept-all"
        reply = self.client.post(url)
        assert reply.status_code == 200 and reply.json() == {"accepted": len(pending)}
        after = self.rows()
        for sid in pending:
            self.status[sid] = "accepted"
            self.frozen[sid] = values(after[sid])

    @invariant()
    def matches_model(self) -> None:
        rows = self.rows()
        assert {s: r["status"] for s, r in rows.items()} == self.status
        notes = [r["note_id"] for r in rows.values()]
        assert len(notes) == len(set(notes))  # OR-ST1
        for sid, frozen in self.frozen.items():  # OR-ST2: decided rows change only via Undo
            assert values(rows[sid]) == frozen

    def teardown(self) -> None:
        self._ctx.__exit__(None, None, None)


# inherits the loaded profile (conftest: default / ci), only the step count is set (NFR-T.3)
SuggestionMachine.TestCase.settings = settings(stateful_step_count=30)
TestSuggestionMachine = SuggestionMachine.TestCase
