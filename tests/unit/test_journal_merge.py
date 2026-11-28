# ADDED [PROMPT #36]: deterministic regeneration and exact edit semantics.
import pytest

from trip_journal.domain.journal_merge import (
    Paragraph,
    mark_user_edit,
    merge_journal,
    slot_order,
    slot_safe,
    slots_to_write,
)


@pytest.mark.parametrize("users", [0, 1, 2])
def test_regenerate(users: int) -> None:
    assert slot_order([]) == ["summary"]
    assert slot_order([3, 1, 2]) == ["summary", "stop:3", "stop:1", "stop:2"]
    assert slot_safe("stop:3") == "stop-3"
    order = slot_order([3])
    existing = [
        Paragraph(slot=s, text=" old ", owner="user" if i < users else "generated")
        for i, s in enumerate(order)
    ]
    assert slots_to_write(existing, order) == order[users:]
    result = merge_journal(existing, dict.fromkeys(order, "new"), order)
    assert result.paragraphs[:users] == existing[:users]
    assert [p.text for p in result.paragraphs[users:]] == ["new"] * (2 - users)
    assert result.nothing_to_regenerate == (users == 2)
    assert mark_user_edit(existing, "summary", " old ") == existing
    assert mark_user_edit(existing, "summary", "")[0] == Paragraph(
        slot="summary", text="", owner="user"
    )
