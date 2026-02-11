"""
Unit tests for MCP secret generation during AuthNZ initialization.
"""

from pathlib import Path

from tldw_Server_API.app.core.AuthNZ.initialize import (
    _detect_env_issues,
    _resolve_env_locations,
    generate_secure_keys,
)


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


def test_detect_env_issues_allows_quickstart_default_single_user_key(monkeypatch):
    monkeypatch.setenv("SINGLE_USER_API_KEY", "THIS-IS-A-SECURE-KEY-123-FAKE-KEY")
    env_values = {
        "SINGLE_USER_API_KEY": "THIS-IS-A-SECURE-KEY-123-FAKE-KEY",
        "MCP_JWT_SECRET": "x" * 32,
        "MCP_API_KEY_SALT": "y" * 32,
    }
    missing_keys, issues = _detect_env_issues("single_user", env_values)

    assert "SINGLE_USER_API_KEY" not in missing_keys
    assert not any("default placeholder" in issue for issue in issues)


def test_resolve_env_locations_prefers_config_files_env_path():
    env_candidates, _template_candidates, cfg_dir = _resolve_env_locations()

    assert env_candidates == [cfg_dir / ".env", cfg_dir / ".ENV"]
    assert cfg_dir.name == "Config_Files"
    assert isinstance(cfg_dir, Path)
