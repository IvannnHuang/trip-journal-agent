# ADDED [PROMPT #25]: U3 organizer page tests (plan steps 14-15 smoke, step 18 full set: htmx
# swaps, 303 without htmx, edit form 422, job fragment -> summary, aria-labels, escaping, D-10
# placement). AI-assisted, Claude Opus 5.5. FakeLLMClient only, never real Ollama.
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.fixtures import minimal_trip_bytes
from tests.fixtures.organizer import (
    SAMPLE_DAY,
    SAMPLE_DAY_LABELS,
    import_sample_trip,
    make_app_client,
    organizer_item,
    organizer_reply,
    wait_job,
)
from trip_journal.agent.llm import FakeLLMClient, LLMReply, ModelStatus

DAY = SAMPLE_DAY
HX = {"HX-Request": "true"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}


class _Placement(HTMLParser):
    """note id -> the testid of the stop (`stop-<id>`) or `day-other-notes` it is rendered in."""

    def __init__(self) -> None:
        super().__init__()
        self.open: list[tuple[str, str | None]] = []
        self.where: dict[int, str | None] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        testid = a.get("data-testid") or ""
        box = testid if re.fullmatch(r"stop-\d+|day-other-notes", testid) else None
        note = re.fullmatch(r"note-(\d+)", a.get("id") or "")
        if note:
            inside = [b for _, b in self.open if b]
            self.where[int(note.group(1))] = inside[-1] if inside else None
        if tag not in VOID:
            self.open.append((tag, box))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.open) - 1, -1, -1):
            if self.open[i][0] == tag:
                del self.open[i:]
                return


def placement(html: str) -> dict[int, str | None]:
    parser = _Placement()
    parser.feed(html)
    return parser.where


def suggestion_ids(html: str) -> list[int]:
    return [int(m) for m in re.findall(r'data-testid="suggestion-(\d+)-accept"', html)]


def rows_by_note(client: TestClient, trip_id: int) -> dict[str, dict[str, Any]]:
    rows = client.get(f"/api/trips/{trip_id}/days/{DAY}/suggestions").json()
    return {r["note_source_id"]: r for r in rows}


def run_day(client: TestClient, trip_id: int) -> str:
    """Organize the sample day with a plain form post; returns the `?job=` day page html."""
    started = client.post(f"/trips/{trip_id}/days/{DAY}/organize", follow_redirects=False)
    assert started.status_code == 303
    location = started.headers["location"]
    assert location.startswith(f"/trips/{trip_id}/days/{DAY}?job=")
    assert wait_job(client, location.split("=", 1)[1])["state"] == "done"
    page = client.get(location)
    assert page.status_code == 200
    return page.text


@pytest.fixture
def pages(organizer_client: TestClient) -> TestClient:
    return organizer_client


def test_day_page_organize_and_review(pages: TestClient) -> None:
    trip_id = import_sample_trip(pages)
    before = pages.get(f"/trips/{trip_id}/days/{DAY}").text
    assert 'data-testid="organizer-bar"' in before and "Accept all for this day (0)" in before
    html = run_day(pages, trip_id)
    assert 'data-testid="organizer-summary"' in html and "Organized 8 notes" in html
    assert "Suggestion – not saved" in html and "Accept all for this day (8)" in html
    first, second, third = suggestion_ids(html)[:3]

    accepted = pages.post(f"/suggestions/{first}/accept", headers=HX)
    assert accepted.status_code == 200
    assert 'id="day-stops"' in accepted.text and "Accept all for this day (7)" in accepted.text
    assert 'hx-swap-oob="true"' in accepted.text
    assert first not in suggestion_ids(accepted.text)
    assert f'data-testid="suggestion-{first}-undo"' in accepted.text
    again = pages.post(f"/suggestions/{first}/accept", headers=HX)
    assert again.status_code == 409 and again.headers["HX-Retarget"] == "#day-stops"
    assert "This suggestion was already accepted. Undo it first." in again.text

    rejected = pages.post(f"/suggestions/{second}/reject", follow_redirects=False)
    assert rejected.status_code == 303 and rejected.headers["location"].endswith(DAY)

    form = pages.get(f"/suggestions/{third}/edit", headers=HX)
    assert form.status_code == 200 and "Save and accept" in form.text
    bad = pages.post(f"/suggestions/{third}/edit", headers=HX, data={"category": "lunch"})
    assert bad.status_code == 422 and bad.headers["HX-Retarget"].startswith("#note-")
    good = pages.post(
        f"/suggestions/{third}/edit", headers=HX, data={"category": "scene", "rating": "4"}
    )
    assert good.status_code == 200 and "edited" in good.text

    done = pages.post(f"/trips/{trip_id}/days/{DAY}/accept-all", headers=HX)
    assert done.status_code == 200 and "5 suggestions accepted" in done.text
    assert "Accept all for this day (0)" in done.text


def test_undo_brings_the_suggestion_back(pages: TestClient) -> None:
    trip_id = import_sample_trip(pages)
    sid = suggestion_ids(run_day(pages, trip_id))[0]
    pages.post(f"/suggestions/{sid}/reject", headers=HX)
    undone = pages.post(f"/suggestions/{sid}/undo", headers=HX)
    assert undone.status_code == 200 and sid in suggestion_ids(undone.text)
    assert "Accept all for this day (8)" in undone.text
    plain = pages.post(f"/suggestions/{sid}/undo", follow_redirects=False)  # already pending
    assert plain.status_code == 409


def test_edit_form_errors_are_tied_to_fields(pages: TestClient) -> None:
    trip_id = import_sample_trip(pages)
    sid = suggestion_ids(run_day(pages, trip_id))[0]
    bad = pages.post(
        f"/suggestions/{sid}/edit",
        headers=HX,
        data={"category": "food", "rating": "9", "dish": "d" * 81},
    )
    assert bad.status_code == 422
    for field in ("rating", "dish"):
        assert f'id="edit-{sid}-{field}-error"' in bad.text
        tag = re.search(rf'<[^>]*id="edit-{sid}-{field}"[^>]*>', bad.text)
        assert tag is not None and 'aria-invalid="true"' in tag.group(0)
        assert f'aria-describedby="edit-{sid}-{field}-error"' in tag.group(0)
    category = re.search(rf'<[^>]*id="edit-{sid}-category"[^>]*>', bad.text)
    assert category is not None and "aria-invalid" not in category.group(0)
    assert "d" * 81 in bad.text  # the typed value comes back, nothing is lost
    plain = pages.post(f"/suggestions/{sid}/edit", data={"category": "nope"})
    assert plain.status_code == 422 and f'data-testid="edit-{sid}"' in plain.text
    assert rows_by_note(pages, trip_id)["n1"]["status"] == "pending"  # nothing saved


def test_cancel_and_edit_rules(pages: TestClient) -> None:
    trip_id = import_sample_trip(pages)
    sid = suggestion_ids(run_day(pages, trip_id))[0]
    pages.get(f"/suggestions/{sid}/edit", headers=HX)
    cancel = pages.get(f"/suggestions/{sid}/row", headers=HX)
    assert cancel.status_code == 200 and f'data-testid="suggestion-{sid}-accept"' in cancel.text
    assert f'data-testid="edit-{sid}"' not in cancel.text
    assert pages.get(f"/suggestions/{sid}/row", follow_redirects=False).status_code == 303
    pages.post(f"/suggestions/{sid}/accept", headers=HX)
    closed = pages.get(f"/suggestions/{sid}/edit", headers=HX)  # only pending rows can be edited
    assert closed.status_code == 409 and closed.headers["HX-Retarget"] == "#day-stops"


def test_plain_posts_redirect_with_a_message(pages: TestClient) -> None:
    trip_id = import_sample_trip(pages)
    run_day(pages, trip_id)
    accepted = pages.post(f"/trips/{trip_id}/days/{DAY}/accept-all", follow_redirects=False)
    assert accepted.status_code == 303
    assert accepted.headers["location"].endswith(f"{DAY}?accepted=8")
    assert "8 suggestions accepted" in pages.get(accepted.headers["location"]).text
    nothing = pages.post(f"/trips/{trip_id}/days/{DAY}/organize", follow_redirects=False)
    assert nothing.status_code == 303 and nothing.headers["location"].endswith("?nothing=1")
    page = pages.get(nothing.headers["location"]).text
    assert "Nothing to organize: every note already has a decision." in page
    whole = pages.post(f"/trips/{trip_id}/organize", follow_redirects=False)
    assert whole.headers["location"] == f"/trips/{trip_id}?nothing=1"


def test_job_fragment_turns_into_the_summary(http: httpx.AsyncClient) -> None:
    items = [organizer_item(label) for label in SAMPLE_DAY_LABELS[:7]]
    items.append(organizer_item("n8", category="drink"))
    llm = FakeLLMClient([LLMReply(content=json.dumps({"suggestions": items}))])
    for client in make_app_client(http, llm):
        trip_id = import_sample_trip(client)
        started = client.post(f"/trips/{trip_id}/days/{DAY}/organize", headers=HX)
        assert started.status_code == 200
        job_id = re.search(r"/jobs/([\w-]+)/fragment", started.text)
        assert job_id is not None
        wait_job(client, job_id.group(1))
        summary = client.get(f"/jobs/{job_id.group(1)}/fragment", headers=HX).text
        assert "Organized 7 notes" in summary
        assert f'data-testid="organizer-not-organized-{DAY}"' in summary
        assert "category &#39;drink&#39; not allowed" in summary
        link = re.search(r'href="([^"]+)" data-testid="organizer-show-results"', summary)
        assert link is not None and link.group(1) == f"/trips/{trip_id}/days/{DAY}"


def test_notes_sit_under_their_effective_stop(http: httpx.AsyncClient) -> None:
    # D-10 / OR-S2: pending and rejected rows keep the import stop; accepted and edited rows use
    # their own stop, and "no stop" moves the note to Other notes. notes.stop_id never changes.
    items = [organizer_item(label) for label in SAMPLE_DAY_LABELS]
    items[3] = organizer_item("n4", stop="s3")  # label n4 = note n6 (11:45, no import stop)
    llm = FakeLLMClient([LLMReply(content=json.dumps({"suggestions": items}))])
    for client in make_app_client(http, llm):
        trip_id = import_sample_trip(client)
        run_day(client, trip_id)
        rows = rows_by_note(client, trip_id)
        note = {k: r["note_id"] for k, r in rows.items()}
        stops = [
            s["stop_id"] for s in client.get(f"/api/trips/{trip_id}/days/{DAY}").json()["stops"]
        ]
        s1, s2, s3 = (f"stop-{sid}" for sid in stops[:3])
        app: Any = client.app
        before = {n.id: n.stop_id for n in app.state.trip.repos.notes.list_for_trip(trip_id)}

        where = placement(client.get(f"/trips/{trip_id}/days/{DAY}").text)
        assert (where[note["n1"]], where[note["n6"]]) == (s1, "day-other-notes")

        client.post(f"/suggestions/{rows['n6']['suggestion_id']}/accept")
        client.post(f"/suggestions/{rows['n1']['suggestion_id']}/accept")
        client.post(f"/suggestions/{rows['n2']['suggestion_id']}/reject")
        client.post(
            f"/suggestions/{rows['n3']['suggestion_id']}/edit",
            data={"category": "scene", "stop_id": str(stops[0])},
        )
        where = placement(client.get(f"/trips/{trip_id}/days/{DAY}").text)
        assert where[note["n6"]] == s3
        assert where[note["n1"]] == "day-other-notes"
        assert where[note["n2"]] == s1
        assert where[note["n3"]] == s1 and s2 not in where.values()

        client.post(f"/suggestions/{rows['n1']['suggestion_id']}/undo")
        assert placement(client.get(f"/trips/{trip_id}/days/{DAY}").text)[note["n1"]] == s1
        after = {n.id: n.stop_id for n in app.state.trip.repos.notes.list_for_trip(trip_id)}
        assert after == before


def test_note_text_is_escaped_and_aria_labels_name_the_time(http: httpx.AsyncClient) -> None:
    data = json.loads(minimal_trip_bytes())
    data["notes"][0]["text"] = "<script>alert(1)</script> & tea"
    llm = FakeLLMClient([organizer_reply(*SAMPLE_DAY_LABELS, tip="<b>go</b>")])
    for client in make_app_client(http, llm):
        trip = client.post("/api/trips", files={"file": ("t.json", json.dumps(data).encode())})
        html = run_day(client, trip.json()["trip_id"])
        assert "<script>alert(1)</script>" not in html and "<b>go</b>" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; tea" in html
        sid = suggestion_ids(html)[0]  # the first note, 08:30 UTC = 09:30 local
        for action in ("Accept", "Edit", "Reject"):
            assert f'aria-label="{action} suggestion for note at 09:30"' in html
        accepted = client.post(f"/suggestions/{sid}/accept", headers=HX).text
        assert 'aria-label="Undo decision for note at 09:30"' in accepted


def test_busy_and_not_ready_on_the_page(http: httpx.AsyncClient) -> None:
    slow = FakeLLMClient([organizer_reply(*SAMPLE_DAY_LABELS)], delay_s=0.5)
    for client in make_app_client(http, slow):
        trip_id = import_sample_trip(client)
        first = client.post(f"/trips/{trip_id}/days/{DAY}/organize", headers=HX)
        assert first.status_code == 200
        busy = client.post(f"/trips/{trip_id}/days/{DAY}/organize", headers=HX)
        assert busy.status_code == 429 and "Another request is still running." in busy.text
        job_id = re.search(r"/jobs/([\w-]+)/fragment", first.text)
        assert job_id is not None
        wait_job(client, job_id.group(1))
    down = ModelStatus(
        reachable=False, model_installed=False, model_name="m", base_url="http://localhost:9/v1"
    )
    for client in make_app_client(http, FakeLLMClient([], status_value=down)):
        trip_id = import_sample_trip(client)
        page = client.post(f"/trips/{trip_id}/days/{DAY}/organize")
        assert page.status_code == 503 and "http://localhost:9/v1" in page.text
        assert 'data-testid="organizer-bar"' in page.text  # the full day page, not a blank one


def test_overview_shows_review_count_and_trip_organize(pages: TestClient) -> None:
    trip_id = import_sample_trip(pages)
    run_day(pages, trip_id)
    overview = pages.get(f"/trips/{trip_id}")
    assert "Organize the whole trip" in overview.text
    assert "8 to review" in overview.text
    pages.post(f"/trips/{trip_id}/days/{DAY}/accept-all")
    again = pages.post(f"/trips/{trip_id}/organize", headers=HX)
    assert again.status_code == 200 and "Nothing to organize" in again.text


def test_unknown_suggestion_is_404(pages: TestClient) -> None:
    for path in ("accept", "reject", "undo", "edit"):
        assert pages.post(f"/suggestions/9999/{path}").status_code == 404
    assert pages.get("/suggestions/9999/edit", headers=HX).status_code == 404
    assert pages.get("/suggestions/9999/row").status_code == 404
