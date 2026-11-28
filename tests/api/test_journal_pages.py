# ADDED [PROMPT #36]: reading, editor, panel, trace and poll-time journal contracts.
from fastapi.testclient import TestClient

from tests.fixtures.organizer import SAMPLE_DAY, import_sample_trip, wait_job
from trip_journal.agent.llm import FakeLLMClient, LLMReply, ModelStatus
from trip_journal.agent.loop import ToolCallRecord
from trip_journal.agent.tools import ToolError
from trip_journal.api.deps import AppState

HX = {"HX-Request": "true"}


def test_empty_and_disabled_states(organizer_client: TestClient) -> None:
    client = organizer_client
    state: AppState = client.app.state.trip  # type: ignore[attr-defined]
    trip = import_sample_trip(client)
    url = f"/trips/{trip}/days/{SAMPLE_DAY}/journal"
    html = client.get(url).text
    for hook in ("write-journal", "tone-picker", "journal-message", "journal-live"):
        assert f'data-testid="{hook}"' in html
    assert 'aria-live="polite"' in html and 'value="casual" selected' in html
    assert "Not written yet. Choose a tone and press Write journal." in html
    assert "trace-details" not in html
    state.repos.photos.add(trip, "alone", "2026-07-01T09:00:00Z", 0)
    photo_day = url.replace(SAMPLE_DAY, "2026-07-01")
    assert "No records for this day." in client.get(photo_day + "/fragment").text
    assert "disabled>Write journal" in client.get(photo_day).text
    down = ModelStatus(reachable=False, model_installed=False, model_name="fake", base_url="local")
    state.llm_factory = lambda _: FakeLLMClient([], status_value=down)
    unavailable = client.get(url).text
    assert (
        "The local model is not available." in unavailable
        and "disabled>Write journal" in unavailable
    )
    for path in (
        url.replace(SAMPLE_DAY, "bad"),
        url.replace(SAMPLE_DAY, "bad") + "/fragment",
        url + "/paragraphs/summary/edit",
        url + "/paragraphs/missing",
    ):
        assert client.get(path).status_code == 404


def test_written_removed_trace_and_escaping(organizer_client: TestClient) -> None:
    client = organizer_client
    state: AppState = client.app.state.trip  # type: ignore[attr-defined]
    trip = import_sample_trip(client)
    stop = state.repos.stops.list_for_day(trip, SAMPLE_DAY)[0].id
    raw = "<script>private</script>"
    note = state.repos.notes.add(trip, "unsafe", raw, SAMPLE_DAY + "T12:00:00Z", 0)
    trace = [
        ToolCallRecord(step=0, group="prefetch", name="get_stop_notes", arguments={"q": raw}),
        ToolCallRecord(
            step=1,
            group="part 1",
            name="search_notes",
            arguments={},
            error=ToolError(kind="tool_failed", message=raw),
        ),
        ToolCallRecord(step=1, group="summary", name="lookup_place", arguments={}),
    ]
    state.repos.journals.save_generated(
        trip, SAMPLE_DAY, ["summary", f"stop:{stop}"], {}, "detailed", trace, "version", "fake"
    )
    url = f"/trips/{trip}/days/{SAMPLE_DAY}/journal"
    fragment = url + "/paragraphs/summary"
    assert client.put("/api" + fragment, json={"text": f"{raw}. Trail [note:{note}]."}).is_success
    html = client.get(url).text
    assert 'value="detailed" selected' in html and "Regenerate" in html
    for hook in (
        "journal-paragraph-summary",
        f"journal-paragraph-stop-{stop}",
        "edit-summary",
        f"edit-stop-{stop}",
        "unsupported-count",
        f"cite-note-{note}",
        "trace-details",
    ):
        assert f'data-testid="{hook}"' in html
    assert (
        'href="#first-unsupported"' in html
        and '<mark class="unsupported" id="first-unsupported">' in html
    )
    assert (
        'class="visually-hidden">unsupported</span>' in html and "1 unsupported sentences" in html
    )
    assert "edited by you" in html and "Not written yet" in html
    assert 'aria-controls="cite-panel-summary"' in html and 'aria-expanded="false"' in html
    details = html.split('<details id="journal-trace"', 1)[1].split("</details>", 1)[0]
    assert '1 tool call failed; see <a href="#journal-trace">How this was made</a>' in html
    assert "Error: tool_failed: &lt;script&gt;" in details
    for label in (
        "loaded by the app",
        "prefetch",
        "part 1",
        "summary",
        "version",
        "fake",
        "detailed",
    ):
        assert label in details
    panel = client.get(f"/trips/{trip}/citations/note/{note}").text
    assert 'data-testid="cite-panel"' in panel
    assert (
        "Record not found in this trip."
        in client.get(f"/trips/{trip + 1}/citations/note/{note}").text
    )
    assert client.get(f"/trips/{trip}/citations/other/1").status_code == 422
    editor = client.get(fragment + "/edit").text
    assert 'data-testid="autosave-status"' in editor and 'role="status"' in editor
    assert (
        'hx-trigger="input changed delay:1s, blur"' in editor and 'hx-sync="this:replace"' in editor
    )
    for surface in (html, client.get(fragment).text, details, panel, editor):
        assert raw not in surface and "&lt;script&gt;private&lt;/script&gt;" in surface
    saved = client.put("/api" + fragment, headers=HX, data={"text": ""})
    assert 'hx-swap-oob="true"' in saved.text and "Saved" in saved.text
    removed = client.get(fragment).text
    assert (
        'class="removed"' in removed and "Removed by you" in removed and "edit-summary" in removed
    )


def test_finished_poll_reads_post_job_edit(organizer_client: TestClient) -> None:
    client = organizer_client
    state: AppState = client.app.state.trip  # type: ignore[attr-defined]
    trip = import_sample_trip(client)
    url = f"/api/trips/{trip}/days/{SAMPLE_DAY}/journal"
    state.journal.llm_factory = lambda _: FakeLLMClient(
        [LLMReply(content="## summary\nOriginal snapshot")]
    )
    job = client.post(url, json={"tone": "casual"}).json()["job_id"]
    assert wait_job(client, job)["state"] == "done"
    assert client.put(
        url + "/paragraphs/summary", json={"text": "Saved after completion"}
    ).is_success
    html = client.get(f"/jobs/{job}/fragment", headers=HX).text
    assert (
        "Draft ready" in html
        and "Saved after completion" in html
        and "Original snapshot" not in html
    )
    assert "did not write" in html


# ADDED [PROMPT #36]: review fix, running and failed journal job fragments (step 19 gaps).
def test_running_journal_job_shows_first_phase() -> None:
    from trip_journal.pages.render import templates
    from trip_journal.services.jobs import JobStatus

    job = JobStatus(job_id="j1", kind="journal", started_at="2026-11-28T00:00:00Z")
    html = templates.get_template("_partials/job_progress.html").render(
        job=job, view=None, retry_url=None
    )
    assert "Loading the day&#39;s records" in html and 'data-state="running"' in html


def test_failed_journal_job_keeps_trace(organizer_client: TestClient) -> None:
    client = organizer_client
    state: AppState = client.app.state.trip  # type: ignore[attr-defined]
    trip = import_sample_trip(client)
    url = f"/api/trips/{trip}/days/{SAMPLE_DAY}/journal"
    state.journal.llm_factory = lambda _: FakeLLMClient(
        [LLMReply(content="no headings <script>x</script>")]
    )
    job = client.post(url, json={"tone": "casual"}).json()["job_id"]
    assert wait_job(client, job)["state"] == "failed"
    html = client.get(f"/jobs/{job}/fragment", headers=HX).text
    assert 'data-state="failed"' in html and "prefetch" in html
    assert "<script>x</script>" not in html
    assert state.repos.journals.get(trip, SAMPLE_DAY) is None
