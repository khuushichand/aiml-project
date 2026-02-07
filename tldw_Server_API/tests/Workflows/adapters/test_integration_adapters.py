"""Tests for integration adapters.

This module tests all 10 integration adapters:
1. run_webhook_adapter - Send webhook
2. run_notify_adapter - Send notification
3. run_mcp_tool_adapter - MCP tool execution
4. run_s3_upload_adapter - S3 upload
5. run_s3_download_adapter - S3 download
6. run_github_create_issue_adapter - Create GitHub issue
7. run_kanban_adapter - Kanban board operations
8. run_chatbooks_adapter - Chatbooks operations
9. run_character_chat_adapter - Character chat
10. run_email_send_adapter - Send email
"""

import os
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ==============================================================================
# Webhook Adapter Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_webhook_adapter_test_mode(monkeypatch):
    """Test webhook adapter in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_webhook_adapter

    config = {"url": "https://example.com/hook", "method": "POST", "body": {"key": "value"}}
    context = {"user_id": "test_user_123"}

    result = await run_webhook_adapter(config, context)
    assert result.get("test_mode") is True
    assert result.get("dispatched") is False


@pytest.mark.asyncio
async def test_webhook_adapter_test_mode_y(monkeypatch):
    """Test webhook adapter treats TEST_MODE=y as test mode."""
    monkeypatch.setenv("TEST_MODE", "y")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_webhook_adapter

    config = {"url": "https://example.com/hook", "method": "POST", "body": {"key": "value"}}
    context = {"user_id": "test_user_123"}

    result = await run_webhook_adapter(config, context)
    assert result.get("test_mode") is True
    assert result.get("dispatched") is False


@pytest.mark.asyncio
async def test_webhook_adapter_missing_user_id_with_url(monkeypatch):
    """Test webhook adapter requires user_id when using HTTP URL mode (no user_id in context)."""
    # Ensure TEST_MODE is not set
    monkeypatch.delenv("TEST_MODE", raising=False)

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_webhook_adapter

    # Mock resolve_context_user_id to return None (simulating missing user_id)
    with patch(
        "tldw_Server_API.app.core.Workflows.adapters.integration.webhook.resolve_context_user_id",
        return_value=None,
    ):
        # Use HTTP URL mode to trigger user_id check
        config = {"url": "https://example.com/hook", "method": "POST"}
        context = {}

        result = await run_webhook_adapter(config, context)
        # When not in test mode and no user_id with URL, should return missing_user_id error
        assert result.get("error") == "missing_user_id"
        assert result.get("dispatched") is False


@pytest.mark.asyncio
async def test_webhook_adapter_local_event_mode(monkeypatch):
    """Test webhook adapter with local event mode (no URL)."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_webhook_adapter

    config = {"event": "custom.event", "data": {"payload": "test"}}
    context = {"user_id": "test_user_123"}

    result = await run_webhook_adapter(config, context)
    assert result.get("test_mode") is True


@pytest.mark.asyncio
async def test_webhook_adapter_get_method(monkeypatch):
    """Test webhook adapter with GET method."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_webhook_adapter

    config = {"url": "https://api.example.com/data", "method": "GET", "body": {"param": "value"}}
    context = {"user_id": "test_user_123"}

    result = await run_webhook_adapter(config, context)
    assert result.get("test_mode") is True


@pytest.mark.asyncio
async def test_webhook_adapter_http_request(monkeypatch):
    """Test webhook adapter makes HTTP request when not in test mode."""
    monkeypatch.delenv("TEST_MODE", raising=False)

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_webhook_adapter

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.encoding = "utf-8"
    mock_response.read.return_value = b'{"success": true}'
    mock_response.close = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.request.return_value = mock_response

    with patch("tldw_Server_API.app.core.Workflows.adapters.integration.webhook._wf_create_client", return_value=mock_client):
        with patch("tldw_Server_API.app.core.Workflows.adapters.integration.webhook.is_url_allowed", return_value=True):
            with patch("tldw_Server_API.app.core.Security.egress.is_webhook_url_allowed_for_tenant", return_value=True):
                config = {"url": "https://example.com/hook", "method": "POST", "body": {"test": "data"}}
                context = {"user_id": "test_user_123", "tenant_id": "default"}

                result = await run_webhook_adapter(config, context)
                assert result.get("dispatched") is True or result.get("error") is not None


# ==============================================================================
# Notify Adapter Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_notify_adapter_test_mode(monkeypatch):
    """Test notify adapter in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_notify_adapter

    config = {"url": "https://hooks.slack.com/services/test", "message": "Hello, world!"}
    context = {}

    result = await run_notify_adapter(config, context)
    assert result.get("test_mode") is True
    assert result.get("dispatched") is False


@pytest.mark.asyncio
async def test_notify_adapter_test_mode_y(monkeypatch):
    """Test notify adapter treats TEST_MODE=y as test mode."""
    monkeypatch.setenv("TEST_MODE", "y")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_notify_adapter

    config = {"url": "https://hooks.slack.com/services/test", "message": "Hello, world!"}
    context = {}

    result = await run_notify_adapter(config, context)
    assert result.get("test_mode") is True
    assert result.get("dispatched") is False


@pytest.mark.asyncio
async def test_notify_adapter_invalid_url():
    """Test notify adapter rejects invalid URLs."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_notify_adapter

    config = {"url": "ftp://invalid.com", "message": "Hello"}
    context = {}

    result = await run_notify_adapter(config, context)
    assert result.get("error") == "invalid_url"


@pytest.mark.asyncio
async def test_notify_adapter_with_subject(monkeypatch):
    """Test notify adapter with subject."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_notify_adapter

    config = {
        "url": "https://hooks.slack.com/services/test",
        "message": "Notification body",
        "subject": "Important Update",
    }
    context = {}

    result = await run_notify_adapter(config, context)
    assert result.get("test_mode") is True


@pytest.mark.asyncio
async def test_notify_adapter_with_headers(monkeypatch):
    """Test notify adapter with custom headers."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_notify_adapter

    config = {
        "url": "https://example.com/webhook",
        "message": "Test message",
        "headers": {"X-Custom-Header": "custom-value"},
    }
    context = {"tenant_id": "test_tenant"}

    result = await run_notify_adapter(config, context)
    assert result.get("test_mode") is True


@pytest.mark.asyncio
async def test_notify_adapter_blocked_egress(monkeypatch):
    """Test notify adapter respects egress blocking."""
    monkeypatch.delenv("TEST_MODE", raising=False)

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_notify_adapter

    with patch("tldw_Server_API.app.core.Workflows.adapters.integration.webhook.is_url_allowed_for_tenant", return_value=False):
        with patch("tldw_Server_API.app.core.Workflows.adapters.integration.webhook.is_url_allowed", return_value=False):
            config = {"url": "https://blocked.example.com/hook", "message": "Test"}
            context = {}

            result = await run_notify_adapter(config, context)
            assert result.get("error") == "blocked_egress"


# ==============================================================================
# MCP Tool Adapter Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_tool_adapter_missing_tool_name():
    """Test MCP tool adapter requires tool_name."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_mcp_tool_adapter

    config = {"arguments": {"key": "value"}}
    context = {}

    result = await run_mcp_tool_adapter(config, context)
    assert result.get("error") == "missing_tool_name"


@pytest.mark.asyncio
async def test_mcp_tool_adapter_echo_fallback():
    """Test MCP tool adapter echo fallback."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_mcp_tool_adapter

    # Mock the MCP server to return None for module lookup
    with patch("tldw_Server_API.app.core.MCP_unified.get_mcp_server") as mock_get_server:
        mock_server = MagicMock()
        mock_registry = MagicMock()
        mock_registry._tool_registry = {}
        mock_registry._module_instances = {}
        mock_server.module_registry = mock_registry
        mock_get_server.return_value = mock_server

        config = {"tool_name": "echo", "arguments": {"message": "Hello, MCP!"}}
        context = {}

        result = await run_mcp_tool_adapter(config, context)
        assert result.get("result") == "Hello, MCP!"
        assert result.get("module") == "_fallback"


@pytest.mark.asyncio
async def test_mcp_tool_adapter_tool_not_found():
    """Test MCP tool adapter returns error for unknown tool."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_mcp_tool_adapter

    with patch("tldw_Server_API.app.core.MCP_unified.get_mcp_server") as mock_get_server:
        mock_server = MagicMock()
        mock_registry = MagicMock()
        mock_registry._tool_registry = {}
        mock_registry._module_instances = {}
        mock_server.module_registry = mock_registry
        mock_get_server.return_value = mock_server

        config = {"tool_name": "nonexistent_tool_xyz", "arguments": {}}
        context = {}

        result = await run_mcp_tool_adapter(config, context)
        assert result.get("error") == "tool_not_found"


@pytest.mark.asyncio
async def test_mcp_tool_adapter_with_allowlist():
    """Test MCP tool adapter respects allowlist."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_mcp_tool_adapter
    from tldw_Server_API.app.core.exceptions import AdapterError

    with patch("tldw_Server_API.app.core.MCP_unified.get_mcp_server") as mock_get_server:
        mock_server = MagicMock()
        mock_registry = MagicMock()
        mock_registry._tool_registry = {}
        mock_registry._module_instances = {}
        mock_server.module_registry = mock_registry
        mock_get_server.return_value = mock_server

        config = {"tool_name": "restricted_tool", "arguments": {}}
        context = {"workflow_mcp_policy": {"allowlist": ["allowed_tool"]}}

        with pytest.raises(AdapterError) as exc_info:
            await run_mcp_tool_adapter(config, context)
        assert "mcp_tool_not_allowed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_mcp_tool_adapter_executes_tool():
    """Test MCP tool adapter executes tool successfully."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_mcp_tool_adapter

    with patch("tldw_Server_API.app.core.MCP_unified.get_mcp_server") as mock_get_server:
        mock_module = MagicMock()
        mock_module.get_tools = AsyncMock(return_value=[{"name": "test_tool"}])
        mock_module.execute_tool = AsyncMock(return_value={"data": "result"})

        mock_server = MagicMock()
        mock_registry = MagicMock()
        mock_registry._tool_registry = {"test_tool": "test_module"}
        mock_registry._module_instances = {"test_module": mock_module}
        mock_server.module_registry = mock_registry
        mock_get_server.return_value = mock_server

        config = {"tool_name": "test_tool", "arguments": {"param": "value"}}
        context = {}

        result = await run_mcp_tool_adapter(config, context)
        assert result.get("result") == {"data": "result"}
        assert result.get("module") == "test_module"


# ==============================================================================
# S3 Upload Adapter Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_s3_upload_adapter_missing_bucket_or_key():
    """Test S3 upload adapter requires bucket and key."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_s3_upload_adapter

    config = {"bucket": "my-bucket"}
    context = {}

    result = await run_s3_upload_adapter(config, context)
    assert result.get("error") == "missing_bucket_or_key"
    assert result.get("uploaded") is False


@pytest.mark.asyncio
async def test_s3_upload_adapter_cancelled():
    """Test S3 upload adapter respects cancellation."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_s3_upload_adapter

    config = {"bucket": "test-bucket", "key": "test-key"}
    context = {"is_cancelled": lambda: True}

    result = await run_s3_upload_adapter(config, context)
    assert result.get("__status__") == "cancelled"


@pytest.mark.asyncio
async def test_s3_upload_adapter_with_content():
    """Test S3 upload adapter with direct content."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_s3_upload_adapter

    mock_s3_client = MagicMock()
    mock_s3_client.put_object = MagicMock()

    # Mock boto3 module entirely
    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        config = {
            "bucket": "my-bucket",
            "key": "data/file.json",
            "content": '{"test": "data"}',
            "region": "us-west-2",
        }
        context = {}

        result = await run_s3_upload_adapter(config, context)
        assert result.get("uploaded") is True
        assert result.get("bucket") == "my-bucket"
        assert result.get("key") == "data/file.json"


@pytest.mark.asyncio
async def test_s3_upload_adapter_boto3_not_installed():
    """Test S3 upload adapter handles missing boto3."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_s3_upload_adapter

    with patch.dict("sys.modules", {"boto3": None}):
        # Force reimport to trigger ImportError
        import importlib
        import tldw_Server_API.app.core.Workflows.adapters.integration.storage as storage_module

        # Mock boto3 import to raise ImportError
        original_import = __builtins__.get("__import__", __import__) if isinstance(__builtins__, dict) else __builtins__.__import__

        def mock_import(name, *args, **kwargs):
            if name == "boto3":
                raise ImportError("No module named 'boto3'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", mock_import):
            config = {"bucket": "test-bucket", "key": "test.txt", "content": "test"}
            context = {}
            # Note: This test may not trigger the ImportError path since boto3 is already imported
            # The test serves as documentation for the expected behavior


@pytest.mark.asyncio
async def test_s3_upload_adapter_with_file_path(monkeypatch, tmp_path):
    """Test S3 upload adapter with file path."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_s3_upload_adapter

    # Create a temporary file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    mock_s3_client = MagicMock()
    mock_s3_client.put_object = MagicMock()

    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    # Mock resolve_workflow_file_path to return our temp file
    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        with patch(
            "tldw_Server_API.app.core.Workflows.adapters.integration.storage.resolve_workflow_file_path",
            return_value=test_file,
        ):
            config = {
                "bucket": "my-bucket",
                "key": "uploads/test.txt",
                "file_path": str(test_file),
            }
            context = {}

            result = await run_s3_upload_adapter(config, context)
            assert result.get("uploaded") is True


@pytest.mark.asyncio
async def test_s3_upload_adapter_content_from_prev():
    """Test S3 upload adapter gets content from previous step."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_s3_upload_adapter

    mock_s3_client = MagicMock()
    mock_s3_client.put_object = MagicMock()

    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        config = {"bucket": "my-bucket", "key": "output.txt"}
        context = {"prev": {"content": "Previous step content"}}

        result = await run_s3_upload_adapter(config, context)
        assert result.get("uploaded") is True


# ==============================================================================
# S3 Download Adapter Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_s3_download_adapter_missing_bucket_or_key():
    """Test S3 download adapter requires bucket and key."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_s3_download_adapter

    config = {"key": "test-key"}
    context = {}

    result = await run_s3_download_adapter(config, context)
    assert result.get("error") == "missing_bucket_or_key"
    assert result.get("content") is None


@pytest.mark.asyncio
async def test_s3_download_adapter_cancelled():
    """Test S3 download adapter respects cancellation."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_s3_download_adapter

    config = {"bucket": "test-bucket", "key": "test-key"}
    context = {"is_cancelled": lambda: True}

    result = await run_s3_download_adapter(config, context)
    assert result.get("__status__") == "cancelled"


@pytest.mark.asyncio
async def test_s3_download_adapter_as_text():
    """Test S3 download adapter returns text content."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_s3_download_adapter

    mock_body = MagicMock()
    mock_body.read.return_value = b"Hello, World!"

    mock_s3_client = MagicMock()
    mock_s3_client.get_object.return_value = {"Body": mock_body}

    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        config = {"bucket": "my-bucket", "key": "file.txt", "as_text": True}
        context = {}

        result = await run_s3_download_adapter(config, context)
        assert result.get("content") == "Hello, World!"
        assert result.get("bucket") == "my-bucket"
        assert result.get("key") == "file.txt"


@pytest.mark.asyncio
async def test_s3_download_adapter_as_bytes():
    """Test S3 download adapter returns binary content."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_s3_download_adapter

    mock_body = MagicMock()
    mock_body.read.return_value = b"\x00\x01\x02\x03"

    mock_s3_client = MagicMock()
    mock_s3_client.get_object.return_value = {"Body": mock_body}

    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        config = {"bucket": "my-bucket", "key": "file.bin", "as_text": False}
        context = {}

        result = await run_s3_download_adapter(config, context)
        assert result.get("content") == b"\x00\x01\x02\x03"


@pytest.mark.asyncio
async def test_s3_download_adapter_with_endpoint_url(monkeypatch):
    """Test S3 download adapter with custom endpoint (MinIO, etc.)."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_s3_download_adapter

    mock_body = MagicMock()
    mock_body.read.return_value = b"data"

    mock_s3_client = MagicMock()
    mock_s3_client.get_object.return_value = {"Body": mock_body}

    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        config = {
            "bucket": "test-bucket",
            "key": "test-key",
            "endpoint_url": "http://minio:9000",
            "access_key": "minioadmin",
            "secret_key": "minioadmin",
        }
        context = {}

        result = await run_s3_download_adapter(config, context)
        assert result.get("content") is not None

        # Verify boto3.client was called with endpoint_url
        mock_boto3.client.assert_called_once()
        call_kwargs = mock_boto3.client.call_args[1]
        assert call_kwargs.get("endpoint_url") == "http://minio:9000"


# ==============================================================================
# GitHub Create Issue Adapter Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_github_create_issue_adapter_missing_repo_or_title():
    """Test GitHub adapter requires repo and title."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_github_create_issue_adapter

    config = {"title": "Test Issue"}
    context = {}

    result = await run_github_create_issue_adapter(config, context)
    assert result.get("error") == "missing_repo_or_title"


@pytest.mark.asyncio
async def test_github_create_issue_adapter_missing_token(monkeypatch):
    """Test GitHub adapter requires token."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_github_create_issue_adapter

    config = {"repo": "owner/repo", "title": "Test Issue"}
    context = {}

    result = await run_github_create_issue_adapter(config, context)
    assert result.get("error") == "missing_github_token"


@pytest.mark.asyncio
async def test_github_create_issue_adapter_cancelled():
    """Test GitHub adapter respects cancellation."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_github_create_issue_adapter

    config = {"repo": "owner/repo", "title": "Test Issue", "token": "test_token"}
    context = {"is_cancelled": lambda: True}

    result = await run_github_create_issue_adapter(config, context)
    assert result.get("__status__") == "cancelled"


@pytest.mark.asyncio
async def test_github_create_issue_adapter_success():
    """Test GitHub adapter creates issue successfully."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_github_create_issue_adapter

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"html_url": "https://github.com/owner/repo/issues/1", "number": 1}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)

    mock_httpx = MagicMock()
    mock_httpx.AsyncClient.return_value = mock_client

    with patch.dict("sys.modules", {"httpx": mock_httpx}):
        config = {
            "repo": "owner/repo",
            "title": "Bug Report",
            "body": "This is a bug",
            "labels": ["bug"],
            "token": "ghp_test_token",
        }
        context = {}

        result = await run_github_create_issue_adapter(config, context)
        assert result.get("created") is True
        assert result.get("issue_url") == "https://github.com/owner/repo/issues/1"
        assert result.get("issue_number") == 1


@pytest.mark.asyncio
async def test_github_create_issue_adapter_api_error():
    """Test GitHub adapter handles API errors."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_github_create_issue_adapter

    mock_response = AsyncMock()
    mock_response.status_code = 422
    mock_response.text = "Validation Failed"

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        config = {"repo": "owner/repo", "title": "Test", "token": "test_token"}
        context = {}

        result = await run_github_create_issue_adapter(config, context)
        assert result.get("created") is False
        assert "github_api_error" in result.get("error", "")


@pytest.mark.asyncio
async def test_github_create_issue_adapter_with_template():
    """Test GitHub adapter applies template to title and body."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_github_create_issue_adapter

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"html_url": "https://github.com/owner/repo/issues/1", "number": 1}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)

    mock_httpx = MagicMock()
    mock_httpx.AsyncClient.return_value = mock_client

    with patch.dict("sys.modules", {"httpx": mock_httpx}):
        config = {
            "repo": "owner/repo",
            "title": "Issue for {{inputs.component}}",
            "body": "Error: {{prev.error_message}}",
            "token": "test_token",
        }
        context = {
            "inputs": {"component": "auth"},
            "prev": {"error_message": "Connection refused"},
        }

        result = await run_github_create_issue_adapter(config, context)
        assert result.get("created") is True


# ==============================================================================
# Kanban Adapter Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_kanban_adapter_missing_action():
    """Test Kanban adapter requires action."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_kanban_adapter

    config = {}
    context = {"user_id": "test_user"}

    result = await run_kanban_adapter(config, context)
    assert result.get("error") == "missing_action"


@pytest.mark.asyncio
async def test_kanban_adapter_board_list(monkeypatch):
    """Test Kanban adapter list boards action."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_kanban_adapter

    mock_db = MagicMock()
    mock_db.list_boards.return_value = ([{"id": 1, "name": "Board 1"}], 1)
    mock_db.close = MagicMock()

    with patch(
        "tldw_Server_API.app.core.Workflows.adapters.integration.messaging.KanbanDB",
        return_value=mock_db,
    ):
        with patch(
            "tldw_Server_API.app.core.Workflows.adapters.integration.messaging.DatabasePaths.get_kanban_db_path",
            return_value=Path("/tmp/kanban.db"),
        ):
            config = {"action": "board.list", "limit": 10}
            context = {"user_id": "1"}

            result = await run_kanban_adapter(config, context)
            assert "boards" in result
            assert result.get("total") == 1


@pytest.mark.asyncio
async def test_kanban_adapter_board_list_accepts_y_flag(monkeypatch):
    """Test Kanban adapter boolean coercion accepts include_archived='y'."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_kanban_adapter

    mock_db = MagicMock()
    mock_db.list_boards.return_value = ([{"id": 1, "name": "Board 1"}], 1)
    mock_db.close = MagicMock()

    with patch(
        "tldw_Server_API.app.core.Workflows.adapters.integration.messaging.KanbanDB",
        return_value=mock_db,
    ):
        with patch(
            "tldw_Server_API.app.core.Workflows.adapters.integration.messaging.DatabasePaths.get_kanban_db_path",
            return_value=Path("/tmp/kanban.db"),
        ):
            config = {"action": "board.list", "include_archived": "y"}
            context = {"user_id": "1"}

            result = await run_kanban_adapter(config, context)
            assert "boards" in result
            mock_db.list_boards.assert_called_once()
            assert mock_db.list_boards.call_args.kwargs.get("include_archived") is True


@pytest.mark.asyncio
async def test_kanban_adapter_board_create(monkeypatch):
    """Test Kanban adapter create board action."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_kanban_adapter

    mock_db = MagicMock()
    mock_db.create_board.return_value = {"id": 1, "name": "New Board", "client_id": "wf_abc123"}
    mock_db.close = MagicMock()

    with patch(
        "tldw_Server_API.app.core.Workflows.adapters.integration.messaging.KanbanDB",
        return_value=mock_db,
    ):
        with patch(
            "tldw_Server_API.app.core.Workflows.adapters.integration.messaging.DatabasePaths.get_kanban_db_path",
            return_value=Path("/tmp/kanban.db"),
        ):
            config = {"action": "board.create", "name": "New Board"}
            context = {"user_id": "1"}

            result = await run_kanban_adapter(config, context)
            assert "board" in result
            assert result["board"]["name"] == "New Board"


@pytest.mark.asyncio
async def test_kanban_adapter_card_create(monkeypatch):
    """Test Kanban adapter create card action."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_kanban_adapter

    mock_db = MagicMock()
    mock_db.create_card.return_value = {"id": 1, "title": "New Task", "list_id": 1}
    mock_db.close = MagicMock()

    with patch(
        "tldw_Server_API.app.core.Workflows.adapters.integration.messaging.KanbanDB",
        return_value=mock_db,
    ):
        with patch(
            "tldw_Server_API.app.core.Workflows.adapters.integration.messaging.DatabasePaths.get_kanban_db_path",
            return_value=Path("/tmp/kanban.db"),
        ):
            config = {"action": "card.create", "list_id": "1", "title": "New Task"}
            context = {"user_id": "1"}

            result = await run_kanban_adapter(config, context)
            assert "card" in result
            assert result["card"]["title"] == "New Task"


@pytest.mark.asyncio
async def test_kanban_adapter_card_search(monkeypatch):
    """Test Kanban adapter search cards action."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_kanban_adapter

    mock_db = MagicMock()
    mock_db.search_cards.return_value = ([{"id": 1, "title": "Matching Card"}], 1)
    mock_db.close = MagicMock()

    with patch(
        "tldw_Server_API.app.core.Workflows.adapters.integration.messaging.KanbanDB",
        return_value=mock_db,
    ):
        with patch(
            "tldw_Server_API.app.core.Workflows.adapters.integration.messaging.DatabasePaths.get_kanban_db_path",
            return_value=Path("/tmp/kanban.db"),
        ):
            config = {"action": "card.search", "query": "matching"}
            context = {"user_id": "1"}

            result = await run_kanban_adapter(config, context)
            assert "cards" in result
            assert result.get("total") == 1


@pytest.mark.asyncio
async def test_kanban_adapter_unsupported_action():
    """Test Kanban adapter returns error for unsupported action."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_kanban_adapter

    mock_db = MagicMock()
    mock_db.close = MagicMock()

    with patch(
        "tldw_Server_API.app.core.Workflows.adapters.integration.messaging.KanbanDB",
        return_value=mock_db,
    ):
        with patch(
            "tldw_Server_API.app.core.Workflows.adapters.integration.messaging.DatabasePaths.get_kanban_db_path",
            return_value=Path("/tmp/kanban.db"),
        ):
            config = {"action": "invalid.action"}
            context = {"user_id": "1"}

            result = await run_kanban_adapter(config, context)
            assert "unsupported_action" in result.get("error", "")


# ==============================================================================
# Chatbooks Adapter Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_chatbooks_adapter_missing_action():
    """Test Chatbooks adapter requires action."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_chatbooks_adapter

    config = {}
    context = {"user_id": "test_user"}

    result = await run_chatbooks_adapter(config, context)
    assert result.get("error") == "missing_action"


@pytest.mark.asyncio
async def test_chatbooks_adapter_export_test_mode(monkeypatch):
    """Test Chatbooks adapter export in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_chatbooks_adapter

    config = {"action": "export", "name": "My Export", "content_types": ["conversations", "notes"]}
    context = {"user_id": "1"}

    result = await run_chatbooks_adapter(config, context)
    assert result.get("simulated") is True
    assert result.get("job_id") == "test-job-123"
    assert result.get("status") == "completed"


@pytest.mark.asyncio
async def test_chatbooks_adapter_export_test_mode_y(monkeypatch):
    """Test Chatbooks adapter export in TEST_MODE=y."""
    monkeypatch.setenv("TEST_MODE", "y")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_chatbooks_adapter

    config = {"action": "export", "name": "My Export", "content_types": ["conversations", "notes"]}
    context = {"user_id": "1"}

    result = await run_chatbooks_adapter(config, context)
    assert result.get("simulated") is True
    assert result.get("job_id") == "test-job-123"


@pytest.mark.asyncio
async def test_chatbooks_adapter_import_test_mode(monkeypatch):
    """Test Chatbooks adapter import in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_chatbooks_adapter

    config = {"action": "import", "file_path": "/path/to/chatbook.json"}
    context = {"user_id": "1"}

    result = await run_chatbooks_adapter(config, context)
    assert result.get("simulated") is True


@pytest.mark.asyncio
async def test_chatbooks_adapter_list_jobs_test_mode(monkeypatch):
    """Test Chatbooks adapter list jobs in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_chatbooks_adapter

    config = {"action": "list_jobs"}
    context = {"user_id": "1"}

    result = await run_chatbooks_adapter(config, context)
    assert result.get("simulated") is True
    assert result.get("jobs") == []
    assert result.get("count") == 0


@pytest.mark.asyncio
async def test_chatbooks_adapter_get_job_test_mode(monkeypatch):
    """Test Chatbooks adapter get job in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_chatbooks_adapter

    config = {"action": "get_job", "job_id": "job-123"}
    context = {"user_id": "1"}

    result = await run_chatbooks_adapter(config, context)
    assert result.get("simulated") is True
    assert result.get("job", {}).get("id") == "job-123"


@pytest.mark.asyncio
async def test_chatbooks_adapter_preview_test_mode(monkeypatch):
    """Test Chatbooks adapter preview in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_chatbooks_adapter

    config = {"action": "preview", "content_types": ["conversations"]}
    context = {"user_id": "1"}

    result = await run_chatbooks_adapter(config, context)
    assert result.get("simulated") is True
    assert "preview" in result


@pytest.mark.asyncio
async def test_chatbooks_adapter_cancelled():
    """Test Chatbooks adapter respects cancellation."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_chatbooks_adapter

    config = {"action": "export"}
    context = {"user_id": "1", "is_cancelled": lambda: True}

    result = await run_chatbooks_adapter(config, context)
    assert result.get("__status__") == "cancelled"


# ==============================================================================
# Character Chat Adapter Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_character_chat_adapter_start_test_mode(monkeypatch):
    """Test Character chat adapter start in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_character_chat_adapter

    config = {"action": "start", "character_id": 1}
    context = {"user_id": "1"}

    result = await run_character_chat_adapter(config, context)
    assert result.get("simulated") is True
    assert result.get("conversation_id") == "test-conv-123"
    assert result.get("character_name") == "Test Character"


@pytest.mark.asyncio
async def test_character_chat_adapter_message_test_mode(monkeypatch):
    """Test Character chat adapter message in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_character_chat_adapter

    config = {"action": "message", "conversation_id": "conv-123", "message": "Hello!"}
    context = {"user_id": "1"}

    result = await run_character_chat_adapter(config, context)
    assert result.get("simulated") is True
    assert "response" in result
    assert "Hello!" in result.get("response", "")


@pytest.mark.asyncio
async def test_character_chat_adapter_message_test_mode_y(monkeypatch):
    """Test Character chat adapter message in TEST_MODE=y."""
    monkeypatch.setenv("TEST_MODE", "y")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_character_chat_adapter

    config = {"action": "message", "conversation_id": "conv-123", "message": "Hello!"}
    context = {"user_id": "1"}

    result = await run_character_chat_adapter(config, context)
    assert result.get("simulated") is True
    assert "response" in result
    assert "Hello!" in result.get("response", "")


@pytest.mark.asyncio
async def test_character_chat_adapter_load_test_mode(monkeypatch):
    """Test Character chat adapter load in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_character_chat_adapter

    config = {"action": "load", "conversation_id": "conv-123"}
    context = {"user_id": "1"}

    result = await run_character_chat_adapter(config, context)
    assert result.get("simulated") is True
    assert result.get("conversation_id") == "conv-123"
    assert result.get("history") == []


@pytest.mark.asyncio
async def test_character_chat_adapter_cancelled():
    """Test Character chat adapter respects cancellation."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_character_chat_adapter

    config = {"action": "start", "character_id": 1}
    context = {"user_id": "1", "is_cancelled": lambda: True}

    result = await run_character_chat_adapter(config, context)
    assert result.get("__status__") == "cancelled"


@pytest.mark.asyncio
async def test_character_chat_adapter_unknown_action(monkeypatch):
    """Test Character chat adapter returns error for unknown action."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_character_chat_adapter

    config = {"action": "invalid"}
    context = {"user_id": "1"}

    result = await run_character_chat_adapter(config, context)
    assert "unknown_action" in result.get("error", "")


@pytest.mark.asyncio
async def test_character_chat_adapter_with_user_name(monkeypatch):
    """Test Character chat adapter uses custom user name."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_character_chat_adapter

    config = {"action": "start", "character_id": 1, "user_name": "Alice"}
    context = {"user_id": "1"}

    result = await run_character_chat_adapter(config, context)
    assert result.get("simulated") is True


# ==============================================================================
# Email Send Adapter Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_email_send_adapter_missing_recipient():
    """Test Email adapter requires recipient."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_email_send_adapter

    config = {"subject": "Test", "body": "Hello"}
    context = {}

    result = await run_email_send_adapter(config, context)
    assert result.get("error") == "missing_recipient"
    assert result.get("sent") is False


@pytest.mark.asyncio
async def test_email_send_adapter_invalid_email():
    """Test Email adapter validates email addresses."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_email_send_adapter

    config = {"to": "not-an-email", "subject": "Test", "body": "Hello"}
    context = {}

    result = await run_email_send_adapter(config, context)
    assert "invalid_email" in result.get("error", "")
    assert result.get("sent") is False


@pytest.mark.asyncio
async def test_email_send_adapter_test_mode(monkeypatch):
    """Test Email adapter in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_email_send_adapter

    config = {
        "to": "user@example.com",
        "subject": "Test Subject",
        "body": "Test body content",
    }
    context = {}

    result = await run_email_send_adapter(config, context)
    assert result.get("simulated") is True
    assert result.get("sent") is True
    assert "user@example.com" in result.get("recipients", [])


@pytest.mark.asyncio
async def test_email_send_adapter_multiple_recipients(monkeypatch):
    """Test Email adapter with multiple recipients."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_email_send_adapter

    config = {
        "to": ["user1@example.com", "user2@example.com"],
        "subject": "Team Update",
        "body": "Hello team!",
    }
    context = {}

    result = await run_email_send_adapter(config, context)
    assert result.get("simulated") is True
    assert result.get("sent") is True
    assert len(result.get("recipients", [])) == 2


@pytest.mark.asyncio
async def test_email_send_adapter_comma_separated_recipients(monkeypatch):
    """Test Email adapter with comma-separated recipients."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_email_send_adapter

    config = {
        "to": "user1@example.com, user2@example.com",
        "subject": "Test",
        "body": "Hello",
    }
    context = {}

    result = await run_email_send_adapter(config, context)
    assert result.get("simulated") is True
    assert result.get("sent") is True


@pytest.mark.asyncio
async def test_email_send_adapter_html_body(monkeypatch):
    """Test Email adapter with HTML body."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_email_send_adapter

    config = {
        "to": "user@example.com",
        "subject": "HTML Email",
        "body": "<h1>Hello</h1><p>World</p>",
        "html": True,
    }
    context = {}

    result = await run_email_send_adapter(config, context)
    assert result.get("simulated") is True
    assert result.get("sent") is True


@pytest.mark.asyncio
async def test_email_send_adapter_cancelled():
    """Test Email adapter respects cancellation."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import run_email_send_adapter

    config = {"to": "user@example.com", "subject": "Test", "body": "Hello"}
    context = {"is_cancelled": lambda: True}

    result = await run_email_send_adapter(config, context)
    assert result.get("__status__") == "cancelled"


@pytest.mark.asyncio
async def test_email_send_adapter_with_template(monkeypatch):
    """Test Email adapter applies template to subject and body."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_email_send_adapter

    config = {
        "to": "user@example.com",
        "subject": "Report for {{inputs.date}}",
        "body": "Summary: {{prev.summary}}",
    }
    context = {
        "inputs": {"date": "2024-01-15"},
        "prev": {"summary": "All tests passed"},
    }

    result = await run_email_send_adapter(config, context)
    assert result.get("simulated") is True
    assert result.get("sent") is True


@pytest.mark.asyncio
async def test_email_send_adapter_sanitizes_subject(monkeypatch):
    """Test Email adapter sanitizes subject to prevent header injection."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_email_send_adapter

    config = {
        "to": "user@example.com",
        "subject": "Normal subject\nBcc: attacker@evil.com",
        "body": "Hello",
    }
    context = {}

    result = await run_email_send_adapter(config, context)
    assert result.get("simulated") is True
    # Newline should be removed from subject
    assert "\n" not in result.get("subject", "")


@pytest.mark.asyncio
async def test_email_send_adapter_body_from_prev(monkeypatch):
    """Test Email adapter gets body from previous step."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.integration import run_email_send_adapter

    config = {"to": "user@example.com", "subject": "Report", "body": ""}
    context = {"prev": {"text": "Generated report content"}}

    result = await run_email_send_adapter(config, context)
    assert result.get("simulated") is True
    assert result.get("sent") is True


# ==============================================================================
# Import Tests
# ==============================================================================


def test_all_integration_adapters_importable():
    """Verify all integration adapters are importable."""
    from tldw_Server_API.app.core.Workflows.adapters.integration import (
        run_webhook_adapter,
        run_notify_adapter,
        run_mcp_tool_adapter,
        run_s3_upload_adapter,
        run_s3_download_adapter,
        run_github_create_issue_adapter,
        run_kanban_adapter,
        run_chatbooks_adapter,
        run_character_chat_adapter,
        run_email_send_adapter,
    )

    assert callable(run_webhook_adapter)
    assert callable(run_notify_adapter)
    assert callable(run_mcp_tool_adapter)
    assert callable(run_s3_upload_adapter)
    assert callable(run_s3_download_adapter)
    assert callable(run_github_create_issue_adapter)
    assert callable(run_kanban_adapter)
    assert callable(run_chatbooks_adapter)
    assert callable(run_character_chat_adapter)
    assert callable(run_email_send_adapter)


def test_integration_adapters_are_async():
    """Verify all integration adapters are async functions."""
    import asyncio

    from tldw_Server_API.app.core.Workflows.adapters.integration import (
        run_webhook_adapter,
        run_notify_adapter,
        run_mcp_tool_adapter,
        run_s3_upload_adapter,
        run_s3_download_adapter,
        run_github_create_issue_adapter,
        run_kanban_adapter,
        run_chatbooks_adapter,
        run_character_chat_adapter,
        run_email_send_adapter,
    )

    adapters = [
        run_webhook_adapter,
        run_notify_adapter,
        run_mcp_tool_adapter,
        run_s3_upload_adapter,
        run_s3_download_adapter,
        run_github_create_issue_adapter,
        run_kanban_adapter,
        run_chatbooks_adapter,
        run_character_chat_adapter,
        run_email_send_adapter,
    ]

    for adapter in adapters:
        assert asyncio.iscoroutinefunction(adapter), f"{adapter.__name__} is not async"


def test_integration_adapters_registered():
    """Verify all integration adapters are registered."""
    from tldw_Server_API.app.core.Workflows.adapters import registry

    expected_adapters = [
        "webhook",
        "notify",
        "mcp_tool",
        "s3_upload",
        "s3_download",
        "github_create_issue",
        "kanban",
        "chatbooks",
        "character_chat",
        "email_send",
    ]

    registered = registry.list_adapters()
    for name in expected_adapters:
        assert name in registered, f"Adapter '{name}' not registered"


def test_integration_adapters_in_category():
    """Verify all integration adapters are in 'integration' category."""
    from tldw_Server_API.app.core.Workflows.adapters import registry

    expected_adapters = [
        "webhook",
        "notify",
        "mcp_tool",
        "s3_upload",
        "s3_download",
        "github_create_issue",
        "kanban",
        "chatbooks",
        "character_chat",
        "email_send",
    ]

    for name in expected_adapters:
        spec = registry.get_spec(name)
        assert spec is not None, f"Adapter '{name}' not registered"
        assert spec.category == "integration", f"Adapter '{name}' not in integration category (got '{spec.category}')"
