from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_startup_shutdown_contract_is_reentrant() -> None:
    from tldw_Server_API.app.main import app

    with TestClient(app) as first_client:
        first_response = first_client.get("/health")
        assert first_response.status_code == 200

    with TestClient(app) as second_client:
        second_response = second_client.get("/health")
        assert second_response.status_code == 200


@pytest.mark.integration
def test_lifecycle_hooks_called_in_order() -> None:
    from tldw_Server_API.app.main import app

    if hasattr(app.state, "_tldw_lifecycle_events"):
        delattr(app.state, "_tldw_lifecycle_events")

    with TestClient(app):
        assert getattr(app.state, "_tldw_lifecycle_events", [])[-1:] == ["startup"]

    assert getattr(app.state, "_tldw_lifecycle_events", [])[-2:] == ["startup", "shutdown"]


@pytest.mark.integration
def test_lifespan_exposes_openapi_after_startup(client_user_only) -> None:
    response = client_user_only.get("/openapi.json")
    assert response.status_code == 200
    payload = response.json()
    assert "paths" in payload
