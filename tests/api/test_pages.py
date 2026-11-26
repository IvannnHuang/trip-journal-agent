# ADDED [PROMPT #13]: Settings page tests (US-18, US-19, ST-4, ST-5). AI-assisted, Claude Opus 5.5.
from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import FakeOllama


def test_root_redirects_to_settings(client: TestClient) -> None:
    reply = client.get("/", follow_redirects=False)
    assert reply.status_code == 307 and reply.headers["location"] == "/settings"


def test_settings_page_ok(client: TestClient) -> None:
    html = client.get("/settings").text
    assert 'data-testid="settings-form"' in html and 'data-testid="status-panel"' in html
    assert 'data-testid="model-banner"' not in html
    assert 'value="qwen3:8b"' in html


def test_banner_when_ollama_down(client: TestClient, ollama: FakeOllama) -> None:
    ollama.up = False
    html = client.get("/settings").text
    assert 'data-code="ollama_unreachable"' in html


def test_banner_when_model_missing(client: TestClient, ollama: FakeOllama) -> None:
    ollama.models = ["llama3.2:latest"]
    html = client.get("/settings").text
    assert 'data-code="model_missing"' in html and "ollama pull qwen3:8b" in html
    # US-18: saving a name that is not installed still saves, with a pull hint
    form = {"model_name": "mistral", "ollama_base_url": "http://localhost:11434/v1"}
    html = client.post("/settings", data=form).text
    assert 'data-testid="settings-saved"' in html
    assert 'data-testid="settings-model-missing"' in html and "ollama pull mistral" in html


def test_post_saves(client: TestClient) -> None:
    form = {
        "model_name": "llama3.2",
        "ollama_base_url": "http://localhost:11434/v1",
        "place_lookup_enabled": "on",
    }
    html = client.post("/settings", data=form).text
    assert 'data-testid="settings-saved"' in html
    saved = client.get("/api/settings").json()
    assert saved["model_name"] == "llama3.2" and saved["place_lookup_enabled"] is True
    # unchecked box sends nothing and turns the setting off
    client.post("/settings", data={k: v for k, v in form.items() if k != "place_lookup_enabled"})
    assert client.get("/api/settings").json()["place_lookup_enabled"] is False


def test_post_invalid_keeps_typed_values(client: TestClient) -> None:
    form = {"model_name": "llama3.2", "ollama_base_url": "https://evil.example/v1"}
    html = client.post("/settings", data=form).text
    assert 'data-testid="settings-invalid"' in html and "https://evil.example/v1" in html
    assert 'data-testid="settings-saved"' not in html
    assert client.get("/api/settings").json()["model_name"] == "qwen3:8b"


def test_static_htmx_served(client: TestClient) -> None:
    reply = client.get("/static/htmx.min.js")
    assert reply.status_code == 200 and "htmx" in reply.text[:2000]
