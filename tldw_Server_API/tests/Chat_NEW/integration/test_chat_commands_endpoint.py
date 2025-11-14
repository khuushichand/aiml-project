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
    # Enable commands and permission enforcement; in single-user mode, filtering should not hide commands
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "true")
    monkeypatch.setenv("CHAT_COMMANDS_REQUIRE_PERMISSIONS", "true")
    r = test_client.get("/api/v1/chat/commands", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "commands" in data
    # Still include commands in single-user test environment
    names = {c.get("name") for c in data["commands"]}
    assert "time" in names
