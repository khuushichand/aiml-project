import configparser
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import pytest


def _api_key() -> str:
    return os.environ.get("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")


def _auth_headers() -> dict:
    return {"X-API-KEY": _api_key()}


def _require_ok(resp, label: str) -> None:
    if not resp.ok:
        raise AssertionError(f"{label} failed: status={resp.status} body={resp.text()}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _searx_url() -> str:
    config_path = _repo_root() / "tldw_Server_API/Config_Files/config.txt"
    parser = configparser.ConfigParser()
    parser.read(config_path)
    return parser.get("Search-Engines", "search_engine_searx_api", fallback="").strip()


def _is_local_url(raw: str) -> bool:
    try:
        parsed = urlparse(raw)
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


@pytest.mark.e2e
def test_research_websearch_local_workflow(page, server_url):
    searx_url = _searx_url()
    if not _is_local_url(searx_url):
        pytest.skip("Local Searx URL not configured; update Search-Engines.search_engine_searx_api to localhost to enable.")

    headers = _auth_headers()
    suffix = uuid4().hex[:8]
    query = f"e2e local websearch {suffix}"

    search_resp = page.request.post(
        "/api/v1/research/websearch",
        headers=headers,
        json={
            "query": query,
            "engine": "searx",
            "result_count": 3,
            "aggregate": False,
        },
    )
    _require_ok(search_resp, "websearch (local)")
    search_payload = search_resp.json()
    assert "web_search_results_dict" in search_payload

    note_resp = page.request.post(
        "/api/v1/notes/",
        headers=headers,
        json={
            "title": f"Websearch local {suffix}",
            "content": f"Query: {query}",
            "keywords": ["websearch", "local", suffix],
        },
    )
    _require_ok(note_resp, "store websearch note (local)")
    note_payload = note_resp.json()
    note_id = note_payload["id"]
    version = note_payload["version"]

    search_notes = page.request.get(
        "/api/v1/notes/search",
        headers=headers,
        params={"query": query},
    )
    _require_ok(search_notes, "search stored note (local)")

    delete_resp = page.request.delete(
        f"/api/v1/notes/{note_id}",
        headers={**headers, "expected-version": str(version)},
    )
    assert delete_resp.status == 204


@pytest.mark.e2e
def test_research_websearch_external_workflow(page, server_url):
    if os.getenv("TLDW_E2E_EXTERNAL_WEBSEARCH", "").lower() not in {"1", "true", "yes", "y", "on"}:
        pytest.skip("External websearch disabled; set TLDW_E2E_EXTERNAL_WEBSEARCH=1 to enable.")
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set; skipping websearch aggregate flow.")

    headers = _auth_headers()
    suffix = uuid4().hex[:8]
    query = f"example domain overview {suffix}"

    search_resp = page.request.post(
        "/api/v1/research/websearch",
        headers=headers,
        json={
            "query": query,
            "engine": "duckduckgo",
            "result_count": 3,
            "aggregate": True,
            "relevance_analysis_llm": "openai",
            "final_answer_llm": "openai",
        },
    )
    _require_ok(search_resp, "websearch (external)")
    search_payload = search_resp.json()
    assert "web_search_results_dict" in search_payload

    final_answer = search_payload.get("final_answer") or {}
    answer_text = final_answer.get("text") or f"Query: {query}"

    note_resp = page.request.post(
        "/api/v1/notes/",
        headers=headers,
        json={
            "title": f"Websearch external {suffix}",
            "content": answer_text,
            "keywords": ["websearch", "external", suffix],
        },
    )
    _require_ok(note_resp, "store websearch note (external)")
    note_payload = note_resp.json()
    note_id = note_payload["id"]
    version = note_payload["version"]

    search_notes = page.request.get(
        "/api/v1/notes/search",
        headers=headers,
        params={"query": suffix},
    )
    _require_ok(search_notes, "search stored note (external)")

    delete_resp = page.request.delete(
        f"/api/v1/notes/{note_id}",
        headers={**headers, "expected-version": str(version)},
    )
    assert delete_resp.status == 204
