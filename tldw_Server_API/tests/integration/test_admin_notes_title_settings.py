from fastapi.testclient import TestClient


def test_get_and_set_notes_title_settings(client_user_only: TestClient):
    # Admin guard exists; in tests, require_admin is bypassed via fixtures
    r = client_user_only.get("/api/v1/admin/notes/title-settings")
    assert r.status_code == 200, r.text  # nosec B101
    data = r.json()
    assert "llm_enabled" in data  # nosec B101
    assert data["default_strategy"] in ["heuristic", "llm", "llm_fallback"]  # nosec B101
    assert data["effective_strategy"] == "heuristic"  # nosec B101
    assert data["effective_strategy"] in data["strategies"]  # nosec B101

    # Toggle values
    r2 = client_user_only.post(
        "/api/v1/admin/notes/title-settings",
        json={"llm_enabled": True, "default_strategy": "llm_fallback"},
    )
    assert r2.status_code == 200, r2.text  # nosec B101
    new = r2.json()
    assert new["llm_enabled"] is True  # nosec B101
    assert new["default_strategy"] == "llm_fallback"  # nosec B101
    assert new["effective_strategy"] == "llm_fallback"  # nosec B101

    # Invalid strategy
    r3 = client_user_only.post(
        "/api/v1/admin/notes/title-settings",
        json={"default_strategy": "invalid"},
    )
    # Pydantic schema Literal enforces valid values -> 422 Unprocessable Entity
    assert r3.status_code == 422, r3.text  # nosec B101
