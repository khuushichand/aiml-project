"""
Unit tests for MCP secret generation during AuthNZ initialization.
"""

from tldw_Server_API.app.core.AuthNZ.initialize import _detect_env_issues, generate_secure_keys


def test_detect_env_issues_requires_mcp_secrets(monkeypatch):
    monkeypatch.delenv("MCP_JWT_SECRET", raising=False)
    monkeypatch.delenv("MCP_API_KEY_SALT", raising=False)

    env_values = {"SINGLE_USER_API_KEY": "a" * 32}
    missing_keys, _issues = _detect_env_issues("single_user", env_values)

    assert missing_keys == {"MCP_JWT_SECRET", "MCP_API_KEY_SALT"}


def test_generate_secure_keys_includes_mcp_secrets():
    keys = generate_secure_keys(requested_keys={"MCP_JWT_SECRET", "MCP_API_KEY_SALT"})

    assert all(
        key in keys and len(keys[key]) >= 32
        for key in ("MCP_JWT_SECRET", "MCP_API_KEY_SALT")
    )
