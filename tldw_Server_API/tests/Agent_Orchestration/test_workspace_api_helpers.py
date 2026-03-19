"""Tests for workspace API helper functions and MCP resolver fallback."""
from __future__ import annotations

import tempfile
from unittest.mock import patch

import pytest

from tldw_Server_API.app.core.DB_Management.Orchestration_DB import OrchestrationDB
from tldw_Server_API.app.services.mcp_hub_workspace_root_resolver import (
    McpHubWorkspaceRootResolver,
)


# ---------------------------------------------------------------------------
# _validate_workspace_root tests
# ---------------------------------------------------------------------------


class TestValidateWorkspaceRoot:
    def test_valid_absolute_path(self):
        from tldw_Server_API.app.api.v1.endpoints.agent_orchestration import _validate_workspace_root
        result = _validate_workspace_root("/tmp")
        assert result == "/private/tmp" or result == "/tmp"  # macOS resolves /tmp

    def test_expands_user_home(self):
        from tldw_Server_API.app.api.v1.endpoints.agent_orchestration import _validate_workspace_root
        result = _validate_workspace_root("~/")
        # Should be an absolute path, not start with ~
        assert not result.startswith("~")
        assert result.startswith("/")

    def test_resolves_relative_components(self):
        from tldw_Server_API.app.api.v1.endpoints.agent_orchestration import _validate_workspace_root
        result = _validate_workspace_root("/tmp/../tmp")
        # Should resolve to /tmp (or /private/tmp on macOS)
        assert ".." not in result

    def test_allowed_base_paths_enforcement(self):
        """When allowed_base_paths is configured, paths outside it should be rejected."""
        from fastapi import HTTPException

        def mock_config(section, key, default=""):
            if section == "ACP-WORKSPACE" and key == "allowed_base_paths":
                return "/allowed/path,/another/allowed"
            return default

        with patch(
            "tldw_Server_API.app.core.config.get_config_value",
            side_effect=mock_config,
        ):
            from tldw_Server_API.app.api.v1.endpoints.agent_orchestration import _validate_workspace_root
            with pytest.raises(HTTPException) as exc_info:
                _validate_workspace_root("/not/allowed/path")
            assert exc_info.value.status_code == 403

    def test_empty_allowed_base_paths_allows_all(self):
        """Empty allowed_base_paths should allow any path."""
        def mock_config(section, key, default=""):
            if section == "ACP-WORKSPACE" and key == "allowed_base_paths":
                return ""
            return default

        with patch(
            "tldw_Server_API.app.core.config.get_config_value",
            side_effect=mock_config,
        ):
            from tldw_Server_API.app.api.v1.endpoints.agent_orchestration import _validate_workspace_root
            # Should not raise
            result = _validate_workspace_root("/tmp")
            assert result.startswith("/")


# ---------------------------------------------------------------------------
# _user_id_int fix tests
# ---------------------------------------------------------------------------


class TestUserIdInt:
    def test_numeric_id_int_attr(self):
        """User with id_int attribute should return it directly."""
        from tldw_Server_API.app.api.v1.endpoints.agent_orchestration import _user_id_int

        class MockUser:
            id_int = 42
            id = "42"

        assert _user_id_int(MockUser()) == 42

    def test_string_numeric_id(self):
        """User with string numeric ID but no id_int should convert."""
        from tldw_Server_API.app.api.v1.endpoints.agent_orchestration import _user_id_int

        class MockUser:
            id_int = None
            id = "123"

        assert _user_id_int(MockUser()) == 123

    def test_non_numeric_id_raises_400(self):
        """User with non-numeric ID should raise HTTPException 400."""
        from fastapi import HTTPException
        from tldw_Server_API.app.api.v1.endpoints.agent_orchestration import _user_id_int

        class MockUser:
            id_int = None
            id = "not-a-number"

        with pytest.raises(HTTPException) as exc_info:
            _user_id_int(MockUser())
        assert exc_info.value.status_code == 400

    def test_no_infinite_recursion(self):
        """Verify the _user_id_int fix doesn't recurse infinitely."""
        from fastapi import HTTPException
        from tldw_Server_API.app.api.v1.endpoints.agent_orchestration import _user_id_int

        class MockUser:
            id_int = None
            id = None  # Will fail int() conversion

        # Should raise HTTPException, not RecursionError
        with pytest.raises(HTTPException):
            _user_id_int(MockUser())


# ---------------------------------------------------------------------------
# MCP resolver acp_workspace fallback
# ---------------------------------------------------------------------------


class TestMcpResolverAcpFallback:
    def test_resolve_acp_workspace_valid(self):
        """_resolve_acp_workspace should return root_path for valid workspace."""
        with tempfile.TemporaryDirectory() as tmp:
            db = OrchestrationDB(user_id=1, db_dir=tmp)
            ws = db.create_workspace(name="WS1", root_path="/test/path")

            # Patch get_orchestration_db where it's imported inside _resolve_acp_workspace
            with patch(
                "tldw_Server_API.app.core.Agent_Orchestration.orchestration_service.get_orchestration_db",
                return_value=db,
            ):
                result = McpHubWorkspaceRootResolver._resolve_acp_workspace("1", str(ws.id))
            assert result == "/test/path"
            db.close()

    def test_resolve_acp_workspace_not_found(self):
        """_resolve_acp_workspace should return None for nonexistent workspace."""
        with tempfile.TemporaryDirectory() as tmp:
            db = OrchestrationDB(user_id=1, db_dir=tmp)
            db._ensure_schema()
            with patch(
                "tldw_Server_API.app.core.Agent_Orchestration.orchestration_service.get_orchestration_db",
                return_value=db,
            ):
                result = McpHubWorkspaceRootResolver._resolve_acp_workspace("1", "99999")
            assert result is None
            db.close()

    def test_resolve_acp_workspace_non_numeric(self):
        """Non-numeric user/workspace IDs should return None."""
        result = McpHubWorkspaceRootResolver._resolve_acp_workspace("abc", "def")
        assert result is None

    def test_resolve_acp_workspace_empty(self):
        """Empty IDs should return None."""
        result = McpHubWorkspaceRootResolver._resolve_acp_workspace("", "")
        assert result is None
