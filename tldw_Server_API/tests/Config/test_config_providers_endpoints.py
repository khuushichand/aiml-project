# test_config_providers_endpoints.py
"""
Tests for GET /config/providers and POST /config/validate-provider endpoints.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tldw_Server_API.app.api.v1.endpoints.config_info import (
    ProviderValidateRequest,
    _check_validate_rate_limit,
    _key_hint,
    _resolve_provider_key,
    _validate_call_log,
    list_configured_providers,
    validate_provider_key,
)


def _make_mock_request(client_host: str = "127.0.0.1") -> MagicMock:
    """Create a mock FastAPI Request with a client IP."""
    req = MagicMock()
    req.client = MagicMock()
    req.client.host = client_host
    return req


# ---------------------------------------------------------------------------
# Unit tests for _key_hint
# ---------------------------------------------------------------------------


class TestKeyHint:
    def test_long_key(self):
        assert _key_hint("sk-1234567890abcdef") == "sk-...cdef"

    def test_short_key(self):
        assert _key_hint("abcd") == "****cd"

    def test_very_short_key(self):
        assert _key_hint("a") == "****"

    def test_exactly_8_chars(self):
        # len <= 8 triggers short path (last 2 chars)
        assert _key_hint("12345678") == "****78"

    def test_9_chars_uses_long_path(self):
        assert _key_hint("123456789") == "123...6789"


# ---------------------------------------------------------------------------
# Unit tests for _resolve_provider_key
# ---------------------------------------------------------------------------


class TestResolveProviderKey:
    def test_returns_env_var_when_set(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")
        result = _resolve_provider_key("openai")
        assert result == "sk-test-key-123"

    def test_returns_none_when_no_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # Patch the function at the module where it's imported from
        _target = "tldw_Server_API.app.api.v1.schemas.chat_request_schemas.get_api_keys"
        with patch(_target, return_value={"openai": ""}):
            result = _resolve_provider_key("openai")
            assert result is None

    def test_ignores_whitespace_only_env_var(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "   ")
        _target = "tldw_Server_API.app.api.v1.schemas.chat_request_schemas.get_api_keys"
        with patch(_target, return_value={"openai": ""}):
            result = _resolve_provider_key("openai")
            assert result is None

    def test_falls_back_to_get_api_keys(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _target = "tldw_Server_API.app.api.v1.schemas.chat_request_schemas.get_api_keys"
        with patch(_target, return_value={"anthropic": "ant-key-from-config"}):
            result = _resolve_provider_key("anthropic")
            assert result == "ant-key-from-config"


# ---------------------------------------------------------------------------
# Tests for GET /config/providers
# ---------------------------------------------------------------------------


class TestListConfiguredProviders:
    @pytest.mark.asyncio
    async def test_returns_provider_list_structure(self, monkeypatch):
        # Clear all provider env vars to get a clean state
        for env_var in [
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
            "COHERE_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY",
        ]:
            monkeypatch.delenv(env_var, raising=False)

        with patch(
            "tldw_Server_API.app.api.v1.schemas.chat_request_schemas.get_api_keys",
            return_value={},
        ):
            response = await list_configured_providers()

        assert hasattr(response, "providers")
        assert hasattr(response, "any_configured")
        assert isinstance(response.providers, list)
        assert len(response.providers) > 0

        # Check structure of first item
        first = response.providers[0]
        assert hasattr(first, "name")
        assert hasattr(first, "configured")
        assert hasattr(first, "requires_api_key")

    @pytest.mark.asyncio
    async def test_detects_configured_provider(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-12345678")
        with patch(
            "tldw_Server_API.app.api.v1.schemas.chat_request_schemas.get_api_keys",
            return_value={"openai": "sk-test-12345678"},
        ):
            response = await list_configured_providers()

        openai_item = next(p for p in response.providers if p.name == "openai")
        assert openai_item.configured is True
        assert openai_item.key_hint is not None
        assert "sk-" in openai_item.key_hint
        assert openai_item.key_source == "env"
        assert response.any_configured is True

    @pytest.mark.asyncio
    async def test_local_providers_always_configured(self, monkeypatch):
        # Local providers don't require API keys
        with patch(
            "tldw_Server_API.app.api.v1.schemas.chat_request_schemas.get_api_keys",
            return_value={},
        ):
            response = await list_configured_providers()

        ollama = next(p for p in response.providers if p.name == "ollama")
        assert ollama.configured is True
        assert ollama.requires_api_key is False
        assert ollama.key_hint is None

    @pytest.mark.asyncio
    async def test_no_cloud_providers_configured(self, monkeypatch):
        # Remove all env vars
        for env_var in [
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
            "COHERE_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY",
            "DEEPSEEK_API_KEY", "HUGGINGFACE_API_KEY", "OPENROUTER_API_KEY",
            "QWEN_API_KEY", "MOONSHOT_API_KEY", "ZAI_API_KEY",
            "NOVITA_API_KEY", "POE_API_KEY", "TOGETHER_API_KEY",
            "AWS_ACCESS_KEY_ID",
        ]:
            monkeypatch.delenv(env_var, raising=False)

        with patch(
            "tldw_Server_API.app.api.v1.schemas.chat_request_schemas.get_api_keys",
            return_value={},
        ):
            response = await list_configured_providers()

        assert response.any_configured is False

    @pytest.mark.asyncio
    async def test_key_hint_does_not_expose_full_key(self, monkeypatch):
        full_key = "sk-very-secret-key-that-should-not-leak"
        monkeypatch.setenv("OPENAI_API_KEY", full_key)

        with patch(
            "tldw_Server_API.app.api.v1.schemas.chat_request_schemas.get_api_keys",
            return_value={"openai": full_key},
        ):
            response = await list_configured_providers()

        openai_item = next(p for p in response.providers if p.name == "openai")
        assert openai_item.key_hint is not None
        # The hint should NOT contain the full key
        assert full_key not in openai_item.key_hint
        # Should contain last 4 chars
        assert full_key[-4:] in openai_item.key_hint


# ---------------------------------------------------------------------------
# Tests for POST /config/validate-provider
# ---------------------------------------------------------------------------


class TestValidateProviderKey:
    @pytest.fixture(autouse=True)
    def _clear_rate_limit_state(self):
        """Reset the in-memory rate limiter between tests."""
        _validate_call_log.clear()
        yield
        _validate_call_log.clear()

    @pytest.mark.asyncio
    async def test_no_key_returns_invalid(self):
        """Omitting api_key should return an error requiring the caller to supply one."""
        body = ProviderValidateRequest(provider="openai")
        request = _make_mock_request()
        response = await validate_provider_key(body, request)

        assert response.valid is False
        assert "api_key is required" in response.error

    @pytest.mark.asyncio
    async def test_unknown_provider_with_key_returns_valid(self):
        """Providers without known validation URLs are assumed valid if key is present."""
        body = ProviderValidateRequest(
            provider="some-unknown-provider",
            api_key="test-key-123",
        )
        request = _make_mock_request()
        response = await validate_provider_key(body, request)
        assert response.valid is True
        assert response.error is None

    @pytest.mark.asyncio
    async def test_successful_validation(self):
        """Mock a successful HTTP validation call."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            body = ProviderValidateRequest(
                provider="openai",
                api_key="sk-valid-key-123",
            )
            request = _make_mock_request()
            response = await validate_provider_key(body, request)

        assert response.valid is True
        assert response.provider == "openai"

    @pytest.mark.asyncio
    async def test_auth_failure_returns_invalid(self):
        """Mock a 401 response."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            body = ProviderValidateRequest(
                provider="openai",
                api_key="sk-invalid-key",
            )
            request = _make_mock_request()
            response = await validate_provider_key(body, request)

        assert response.valid is False
        assert "Authentication failed" in response.error

    @pytest.mark.asyncio
    async def test_rate_limited_treated_as_valid(self):
        """429 means the key is valid but rate-limited."""
        mock_response = MagicMock()
        mock_response.status_code = 429

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            body = ProviderValidateRequest(
                provider="openai",
                api_key="sk-rate-limited-key",
            )
            request = _make_mock_request()
            response = await validate_provider_key(body, request)

        assert response.valid is True

    @pytest.mark.asyncio
    async def test_anthropic_400_treated_as_valid(self):
        """Anthropic returns 400 for malformed requests even when auth succeeds."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"type": "invalid_request_error", "message": "bad request"}
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            body = ProviderValidateRequest(
                provider="anthropic",
                api_key="ant-valid-key",
            )
            request = _make_mock_request()
            response = await validate_provider_key(body, request)

        assert response.valid is True

    @pytest.mark.asyncio
    async def test_google_uses_header_auth_not_query_string(self):
        """Google validation should use x-goog-api-key header, not a query parameter."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            body = ProviderValidateRequest(
                provider="google",
                api_key="google-test-key",
            )
            request = _make_mock_request()
            response = await validate_provider_key(body, request)

        assert response.valid is True
        # Verify the key was passed as a header, NOT in the URL
        call_args = mock_client.get.call_args
        url_used = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        headers_used = call_args[1].get("headers", {}) if call_args[1] else {}
        # Key must NOT appear in the URL query string
        assert "key=" not in url_used
        assert "google-test-key" not in url_used
        # Key must appear in the x-goog-api-key header
        assert headers_used.get("x-goog-api-key") == "google-test-key"

    @pytest.mark.asyncio
    async def test_timeout_handled_gracefully(self):
        """Timeouts should return a clear error."""
        async def _slow_validate(*args, **kwargs):
            await asyncio.sleep(10)
            return MagicMock(status_code=200)

        mock_client = AsyncMock()
        mock_client.get = _slow_validate
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            body = ProviderValidateRequest(
                provider="openai",
                api_key="sk-timeout-key",
            )
            request = _make_mock_request()
            response = await validate_provider_key(body, request)

        assert response.valid is False
        assert "timed out" in response.error.lower()

    @pytest.mark.asyncio
    async def test_no_fallback_to_configured_key(self, monkeypatch):
        """Even when a server key is configured, omitting api_key must fail."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env-123")

        body = ProviderValidateRequest(provider="openai")
        request = _make_mock_request()
        response = await validate_provider_key(body, request)

        # Must NOT fall back to the server's configured key
        assert response.valid is False
        assert "api_key is required" in response.error


# ---------------------------------------------------------------------------
# Tests for rate limiting on validate-provider
# ---------------------------------------------------------------------------


class TestValidateProviderRateLimit:
    @pytest.fixture(autouse=True)
    def _clear_rate_limit_state(self):
        """Reset the in-memory rate limiter between tests."""
        _validate_call_log.clear()
        yield
        _validate_call_log.clear()

    def test_allows_up_to_limit(self):
        """5 calls from the same IP should succeed."""
        for _ in range(5):
            _check_validate_rate_limit("10.0.0.1")  # should not raise

    def test_rejects_over_limit(self):
        """6th call from the same IP should raise 429."""
        for _ in range(5):
            _check_validate_rate_limit("10.0.0.2")
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _check_validate_rate_limit("10.0.0.2")
        assert exc_info.value.status_code == 429

    def test_different_ips_independent(self):
        """Each IP has its own counter."""
        for _ in range(5):
            _check_validate_rate_limit("10.0.0.3")
        # Different IP should still be allowed
        _check_validate_rate_limit("10.0.0.4")  # should not raise

    @pytest.mark.asyncio
    async def test_endpoint_returns_429_when_rate_limited(self):
        """The endpoint itself should return HTTP 429 when rate-limited."""
        # Exhaust the limit for this IP
        for _ in range(5):
            _check_validate_rate_limit("10.0.0.5")

        body = ProviderValidateRequest(provider="openai", api_key="sk-test")
        request = _make_mock_request(client_host="10.0.0.5")

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await validate_provider_key(body, request)
        assert exc_info.value.status_code == 429
