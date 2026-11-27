# ADDED [PROMPT #17]: trip and day pages (frontend-components 2.1-2.5, D-2, AT-1..AT-4,
# DL-1). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import json
import re  # ADDED [PROMPT #25]
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from tests.fixtures import minimal_trip_bytes
from tests.fixtures.organizer import two_day_trip_bytes  # ADDED [PROMPT #25]
from trip_journal.services.jobs import JobRunner

HTMX = {"HX-Request": "true"}


def import_sample(client: TestClient) -> int:
    reply = client.post("/api/trips", files={"file": ("t.json", minimal_trip_bytes())})
    value: int = reply.json()["trip_id"]
    return value


def invalid_bytes() -> bytes:
    data = json.loads(minimal_trip_bytes())
    data["stops"][3]["end_utc"] = "2026-05-02T22:00:00Z"
    return json.dumps(data).encode()


def test_empty_trip_list(client: TestClient) -> None:
    html = client.get("/trips").text
    assert 'data-testid="trips-empty"' in html and 'data-testid="import-form"' in html
    assert 'data-testid="nav-active-trip-none"' in html


def test_import_redirects_to_overview(client: TestClient) -> None:
    reply = client.post(
        "/trips/import", files={"file": ("t.json", minimal_trip_bytes())}, follow_redirects=False
    )
    assert reply.status_code == 303
    target = reply.headers["location"]
    html = client.get(target).text
    assert 'data-testid="overview-title"' in html and "A day in Lisbon" in html
    assert 'data-testid="overview-day-2026-05-02"' in html
    assert 'data-testid="nav-active-trip-link"' in html


def test_import_with_htmx_uses_hx_redirect(client: TestClient) -> None:
    reply = client.post(
        "/trips/import", files={"file": ("t.json", minimal_trip_bytes())}, headers=HTMX
    )
    assert reply.status_code == 200 and reply.headers["HX-Redirect"].startswith("/trips/")


def test_invalid_import_shows_issues(client: TestClient) -> None:
    reply = client.post("/trips/import", files={"file": ("t.json", invalid_bytes())})
    assert reply.status_code == 422
    assert 'data-testid="import-issues"' in reply.text and "stops[3].end_utc" in reply.text
    assert 'data-testid="trips-empty"' in reply.text  # nothing was stored
    fragment = client.post(
        "/trips/import", files={"file": ("t.json", invalid_bytes())}, headers=HTMX
    )
    assert fragment.status_code == 422
    assert "<html" not in fragment.text and 'data-testid="import-issues-list"' in fragment.text


def test_issue_list_shows_more(client: TestClient) -> None:
    data = json.loads(minimal_trip_bytes())
    for i in range(55):
        data["notes"].append(
            {
                "id": f"x{i}",
                "text": "t",
                "time_utc": "2026-05-02T10:00:00Z",
                "utc_offset_minutes": 7,
            }
        )
    reply = client.post("/trips/import", files={"file": ("t.json", json.dumps(data).encode())})
    assert 'data-testid="import-issues-more"' in reply.text


def test_duplicate_import_links_to_existing(client: TestClient) -> None:
    trip_id = import_sample(client)
    reply = client.post("/trips/import", files={"file": ("t.json", minimal_trip_bytes())})
    assert reply.status_code == 409
    assert 'data-testid="import-exists"' in reply.text
    assert f"/trips/{trip_id}/delete" in reply.text


class _SwapHandlerFinder(HTMLParser):
    """Collect hx-target values and the ids of elements that carry hx-on::before-swap."""

    def __init__(self) -> None:
        super().__init__()
        self.targets: set[str] = set()
        self.handler_ids: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = dict(attrs)
        if found.get("hx-target"):
            self.targets.add(found["hx-target"] or "")
        if "hx-on::before-swap" in found:
            self.handler_ids.append(found.get("id"))


def _swap_handlers(html: str) -> _SwapHandlerFinder:
    finder = _SwapHandlerFinder()
    finder.feed(html)
    return finder


def test_import_swap_handler_sits_on_target(client: TestClient) -> None:
    # ADDED [PROMPT #20]: F-1 regression. htmx 2 fires beforeSwap on the hx-target, so the
    # 422/409 handler must sit on #import-panel itself, also in the swapped-in fragment.
    trip_id = import_sample(client)
    assert trip_id
    pages = [
        client.get("/trips").text,
        client.post(
            "/trips/import", files={"file": ("t.json", invalid_bytes())}, headers=HTMX
        ).text,
        client.post(
            "/trips/import", files={"file": ("t.json", minimal_trip_bytes())}, headers=HTMX
        ).text,
    ]
    for html in pages:
        found = _swap_handlers(html)
        assert found.targets == {"#import-panel"}
        assert found.handler_ids == ["import-panel"]


def test_list_shows_active_and_activate(client: TestClient) -> None:
    first = import_sample(client)
    data = json.loads(minimal_trip_bytes())
    data["trip"]["trip_id"] = "second"
    data["trip"]["title"] = "Second"
    second = client.post(
        "/api/trips", files={"file": ("t.json", json.dumps(data).encode())}
    ).json()["trip_id"]
    html = client.get("/trips").text
    assert f'data-testid="trips-active-{second}"' in html
    assert f'data-testid="trips-activate-{first}"' in html
    reply = client.post(f"/trips/{first}/activate", follow_redirects=False)
    assert reply.status_code == 303
    assert f'data-testid="trips-active-{first}"' in client.get("/trips").text


def test_day_page(client: TestClient) -> None:
    trip_id = import_sample(client)
    html = client.get(f"/trips/{trip_id}/days/2026-05-02").text
    assert 'data-testid="day-heading"' in html and "Day 1 - Sat 2 May 2026" in html
    assert 'data-testid="day-other-photos"' in html and "IMG_0006.jpg" in html
    assert 'data-testid="day-other-notes"' in html
    assert "+1 day" in html
    assert 'data-testid="day-prev"' in html and 'data-testid="day-next"' in html


@pytest.mark.parametrize(
    ("path", "code"),
    [
        ("/trips/999", "trip_not_found"),
        ("/trips/999/days/2026-05-02", "trip_not_found"),
        ("/trips/{id}/days/2026-05-03", "day_not_found"),
        ("/trips/{id}/days/2026-02-30", "day_not_found"),
        ("/trips/999/days/nope", "trip_not_found"),
        ("/trips/999/delete", "trip_not_found"),
    ],
)
def test_not_found_pages(client: TestClient, path: str, code: str) -> None:
    trip_id = import_sample(client)
    reply = client.get(path.replace("{id}", str(trip_id)))
    assert reply.status_code == 404
    assert f'data-code="{code}"' in reply.text and 'data-testid="notfound-trips-link"' in reply.text


def test_activate_unknown_is_404(client: TestClient) -> None:
    assert client.post("/trips/999/activate").status_code == 404


def test_delete_flow(client: TestClient) -> None:
    trip_id = import_sample(client)
    confirm = client.get(f"/trips/{trip_id}/delete")
    assert confirm.status_code == 200 and 'data-testid="delete-confirm-text"' in confirm.text
    assert client.get(f"/trips/{trip_id}").status_code == 200  # DL-1: GET did not delete
    reply = client.post(f"/trips/{trip_id}/delete", follow_redirects=False)
    assert reply.status_code == 303 and reply.headers["location"] == "/trips?deleted=1"
    html = client.get("/trips?deleted=1").text
    assert 'data-testid="trips-deleted"' in html and "Trip deleted." in html
    assert client.post(f"/trips/{trip_id}/delete").status_code == 404


def test_delete_refused_while_job_runs(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    trip_id = import_sample(client)
    monkeypatch.setattr(JobRunner, "running", property(lambda _self: object()))
    confirm = client.get(f"/trips/{trip_id}/delete")
    assert confirm.status_code == 409 and 'data-testid="delete-error"' in confirm.text
    post = client.post(f"/trips/{trip_id}/delete")
    assert post.status_code == 409
    monkeypatch.undo()
    assert client.get(f"/trips/{trip_id}").status_code == 200


# ADDED [PROMPT #25]: U3 T-O10, CI-1 photo line and CI-2 day count (plan step 18).
def _photo_line(html: str, photo: str) -> str:
    match = re.search(rf'data-testid="photo-{photo}">(.*?)</li>', html, re.S)
    assert match is not None, photo
    return " ".join(re.sub(r"<[^>]+>", " ", match.group(1)).split())


def test_photo_line_shows_coordinates_or_no_location(client: TestClient) -> None:
    trip_id = import_sample(client)
    html = client.get(f"/trips/{trip_id}/days/2026-05-02").text
    assert _photo_line(html, "3") == "10:45 · 38.7118, -9.1301 · IMG_0003.jpg"
    assert _photo_line(html, "8") == "15:45 · no location · IMG_0008.jpg"


def test_trip_list_counts_days_in_words(client: TestClient) -> None:
    sample = import_sample(client)
    two = client.post("/api/trips", files={"file": ("t.json", two_day_trip_bytes())})
    assert two.status_code == 201, two.text
    days = {t["trip_id"]: len(t["days"]) for t in client.get("/api/trips").json()}
    assert days == {sample: 1, two.json()["trip_id"]: 2}
    html = " ".join(client.get("/trips").text.split())
    assert "1 day · 4 stops" in html
    assert "2 days · 4 stops" in html
