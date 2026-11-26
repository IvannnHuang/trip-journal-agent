# ADDED [PROMPT #13]: settings properties P-S1..P-S4 (SE-2, SE-3, SE-7).
# AI-assisted, Claude Opus 5.5.
from __future__ import annotations

import httpx
import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.strategies import allowed_urls, model_names
from trip_journal.data.db import connect, init_schema
from trip_journal.data.repositories import Repositories
from trip_journal.services.errors import SettingsValidationError
from trip_journal.services.settings import (
    SettingsService,
    SettingsUpdate,
    normalize_base_url,
    validate_model,
)


@given(allowed_urls())
def test_p_s1_allowed_urls_normalise_to_v1(url: str) -> None:
    out = normalize_base_url(url)
    assert out.startswith("http://") and out.endswith("/v1")


@given(
    st.sampled_from(["https", "ftp", "file"]),
    st.sampled_from(["example.com", "10.0.0.1", "localhost.evil", "0.0.0.0"]),
)
def test_p_s2_remote_or_non_http_rejected(scheme: str, host: str) -> None:
    for url in (f"{scheme}://localhost:11434/v1", f"http://{host}:11434/v1"):
        with pytest.raises(ValueError):
            normalize_base_url(url)


@given(allowed_urls())
def test_p_s3_normalise_is_idempotent(url: str) -> None:
    once = normalize_base_url(url)
    assert normalize_base_url(once) == once


@given(model_names, allowed_urls(), st.booleans())
def test_p_s4_saved_settings_read_back(name: str, url: str, lookup: bool) -> None:
    conn = connect(":memory:")
    init_schema(conn)
    try:
        repos = Repositories.from_connection(conn)
        service = SettingsService(repos.settings, env={}, http=httpx.AsyncClient())
        try:
            expected = validate_model(name)
        except ValueError:
            with pytest.raises(SettingsValidationError):
                service.update(SettingsUpdate(model_name=name))
            return
        service.update(
            SettingsUpdate(model_name=name, ollama_base_url=url, place_lookup_enabled=lookup)
        )
        fresh = SettingsService(repos.settings, env={}, http=httpx.AsyncClient()).get()
        assert fresh.model_name == expected
        assert fresh.ollama_base_url == normalize_base_url(url)
        assert fresh.place_lookup_enabled is lookup
    finally:
        conn.close()
