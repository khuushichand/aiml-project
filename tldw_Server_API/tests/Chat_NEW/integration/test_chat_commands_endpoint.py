import pytest


@pytest.mark.integration
def test_list_chat_commands_basic(test_client, auth_headers, monkeypatch):
    # Ensure commands are enabled for this test
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "true")
    r = test_client.get("/api/v1/chat/commands", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert "commands" in data
    names = {c.get("name") for c in data["commands"]}
    # Built-ins should be present
    assert "time" in names
    assert "weather" in names
    # Ensure permission metadata present
    by_name = {c.get("name"): c for c in data["commands"]}
    assert "required_permission" in by_name["time"]
    assert by_name["time"]["required_permission"] in (None, "chat.commands.time")


@pytest.mark.integration
def test_list_chat_commands_rbac_filtering(test_client, auth_headers, monkeypatch):
    # Enable commands and permission enforcement; when permission checks fail,
    # commands requiring a permission should be filtered out.
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "true")
    monkeypatch.setenv("CHAT_COMMANDS_REQUIRE_PERMISSIONS", "true")
    # Force RBAC to deny permissions for this test to exercise filtering
    from tldw_Server_API.app.api.v1.endpoints import chat as chat_mod

    monkeypatch.setattr(chat_mod, "user_has_permission", lambda user_id, perm: False, raising=True)

    r = test_client.get("/api/v1/chat/commands", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "commands" in data
    names = {c.get("name") for c in data["commands"]}
    # Built-in commands that require permissions should be filtered out
    assert "time" not in names
