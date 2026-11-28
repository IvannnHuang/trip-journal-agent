# ADDED [PROMPT #36]: heading normalization, drop precedence and missing bodies.
import pytest

from trip_journal.agent.journal import parse_journal_output
from trip_journal.services.errors import ModelCallError


def test_sections_and_drop_reasons() -> None:
    text = (
        "<think>## summary\nhidden</think>\nintro\n## Stop : 12\n\n  kept  \n\n"
        "## stop:12\nignored\n## junk\nx\n## summary\nmine\n## stop:2\nother\n## stop:3\n  "
    )
    draft = parse_journal_output(text, ["stop:12", "stop:3"], ["summary"])
    assert draft.slots == {"stop:12": "  kept  "}
    assert [d.reason for d in draft.dropped] == [
        "duplicate",
        "unknown_slot",
        "user_owned",
        "not_requested",
    ]


def test_empty_run_fails() -> None:
    with pytest.raises(ModelCallError, match="did not write"):
        parse_journal_output("## summary\n  ", ["summary"], [])
