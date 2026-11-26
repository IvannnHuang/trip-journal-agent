# ADDED [PROMPT #13]: settings JSON API tests (US-18, SE-5, ST-1). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import FakeOllama
from trip_journal.config import DEFAULT_MODEL


def test_get_defaults(client: TestClient) -> None:
    body = client.get("/api/settings").json()
    assert body["model_name"] == DEFAULT_MODEL
    assert body["ollama_base_url"].startswith("http://localhost:11434")
    assert body["place_lookup_enabled"] is False


def test_put_saves_and_get_reads_back(client: TestClient) -> None:
    change = {
        "model_name": "llama3.2",
        "ollama_base_url": "http://127.0.0.1:11434/v1",
        "place_lookup_enabled": True,
    }
    assert client.put("/api/settings", json=change).status_code == 200
    assert client.get("/api/settings").json()["model_name"] == "llama3.2"


def test_put_rejects_remote_url_and_saves_nothing(client: TestClient) -> None:
    change = {"model_name": "llama3.2", "ollama_base_url": "http://example.com:11434/v1"}
    reply = client.put("/api/settings", json=change)
    assert reply.status_code == 422
    body = reply.json()
    assert body["code"] == "invalid_settings" and "ollama_base_url" in body["issues"]
    assert client.get("/api/settings").json()["model_name"] == DEFAULT_MODEL


def test_model_status_json_and_html(client: TestClient, ollama: FakeOllama) -> None:
    body = client.get("/api/settings/model-status").json()
    assert body["reachable"] is True and body["model_installed"] is True
    ollama.up = False
    html = client.get("/api/settings/model-status", headers={"HX-Request": "true"})
    assert html.headers["content-type"].startswith("text/html")
    assert 'data-testid="status-panel"' in html.text and "status-warning" in html.text
