from fastapi.testclient import TestClient


def test_get_and_set_notes_title_settings(client_user_only: TestClient):
    # Admin guard exists; in tests, require_admin is bypassed via fixtures
    r = client_user_only.get("/api/v1/admin/notes/title-settings")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "llm_enabled" in data
    assert data["default_strategy"] in ["heuristic", "llm", "llm_fallback"]

    # Toggle values
    r2 = client_user_only.post(
        "/api/v1/admin/notes/title-settings",
        json={"llm_enabled": True, "default_strategy": "llm_fallback"},
    )
    assert r2.status_code == 200, r2.text
    new = r2.json()
    assert new["llm_enabled"] is True
    assert new["default_strategy"] == "llm_fallback"

    # Invalid strategy
    r3 = client_user_only.post(
        "/api/v1/admin/notes/title-settings",
        json={"default_strategy": "invalid"},
    )
    assert r3.status_code == 400

