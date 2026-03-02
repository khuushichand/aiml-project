from __future__ import annotations

import pytest


@pytest.mark.unit
def test_router_contract_includes_key_paths() -> None:
    from tldw_Server_API.app.main import app

    paths = {route.path for route in app.routes}
    expected_paths = {
        "/health",
        "/openapi.json",
        "/api/v1/chat/completions",
        "/api/v1/rag/search",
    }
    missing_paths = sorted(expected_paths - paths)
    assert not missing_paths, f"Missing expected paths: {missing_paths}"
    assert any(path.startswith("/api/v1/media/process") for path in paths), (
        "Expected at least one media process route under /api/v1/media/process*"
    )


@pytest.mark.integration
def test_openapi_contains_core_tags(client_user_only) -> None:
    response = client_user_only.get("/openapi.json")
    assert response.status_code == 200

    payload = response.json()
    tags = {tag["name"] for tag in payload.get("tags", [])}
    expected_tags = {"chat", "audio", "media", "rag-unified"}
    missing_tags = sorted(expected_tags - tags)
    assert not missing_tags, f"Missing expected tags: {missing_tags}"
