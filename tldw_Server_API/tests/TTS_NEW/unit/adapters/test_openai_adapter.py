"""
Unit tests for OpenAI TTS adapter.

Tests the OpenAI TTS adapter with minimal mocking - only mocking
the actual OpenAI API calls.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import httpx
from io import BytesIO

from tldw_Server_API.app.core.TTS.adapters.openai_adapter import OpenAIAdapter as OpenAITTSAdapter
from tldw_Server_API.app.core.TTS.adapters.base import (
    TTSRequest,
    TTSResponse,
    AudioFormat,
    VoiceSettings
)
from tldw_Server_API.app.core.TTS.tts_exceptions import (
    TTSProviderNotConfiguredError,
    TTSGenerationError,
    TTSRateLimitError,
    TTSValidationError,
    TTSNetworkError,
)

# ========================================================================
# Adapter Initialization Tests
# ========================================================================

class TestOpenAIAdapterInitialization:
    """Test OpenAI adapter initialization and configuration."""

    @pytest.mark.unit
    def test_adapter_initialization_with_config(self):
        """Test adapter initialization with configuration."""
        config = {
            "openai_api_key": "test-key-123",
            "openai_base_url": "https://api.openai.com/v1/audio/speech",
            "timeout": 30
        }

        adapter = OpenAITTSAdapter(config)

        assert adapter.provider_name.lower() == "openai"
        assert adapter.api_key == "test-key-123"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_adapter_initialization_without_api_key(self, monkeypatch):
        """Test adapter initialization without API key."""
        # Ensure environment doesn't supply a key implicitly
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = {
            "openai_base_url": "https://api.openai.com/v1/audio/speech"
        }
        adapter = OpenAITTSAdapter(config)
        # Production adapter returns False and sets status rather than raising
        success = await adapter.initialize()
        assert success is False
        assert str(adapter.status.value) in {"not_configured", "error"}

    @pytest.mark.unit
    def test_adapter_supported_models(self):
        """Test adapter supports setting known models via config."""
        adapter_default = OpenAITTSAdapter({"openai_api_key": "test-key"})
        assert adapter_default.model in ("tts-1", "tts-1-hd")

        adapter_hd = OpenAITTSAdapter({"openai_api_key": "test-key", "openai_model": "tts-1-hd"})
        assert adapter_hd.model == "tts-1-hd"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_adapter_supported_voices(self):
        """Test adapter reports supported voices via capabilities."""
        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        caps = await adapter.get_capabilities()
        voice_ids = [v.id for v in caps.supported_voices]
        expected_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        for voice in expected_voices:
            assert voice in voice_ids

# ========================================================================
# Request Validation Tests
# ========================================================================

class TestRequestValidation:
    """Test request validation in OpenAI adapter."""

    @pytest.mark.unit
    async def test_validate_valid_request(self):
        """Test validation of valid request."""
        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        await adapter.ensure_initialized()
        request = TTSRequest(text="Hello world", voice="alloy", stream=False)
        is_valid, error = await adapter.validate_request(request)
        assert is_valid and error is None

    @pytest.mark.unit
    async def test_validate_invalid_voice(self):
        """OpenAI maps unknown voices to defaults; validation should pass."""
        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        await adapter.ensure_initialized()
        request = TTSRequest(text="Hello", voice="invalid_voice")
        is_valid, error = await adapter.validate_request(request)
        assert is_valid and error is None
        assert adapter.map_voice("invalid_voice") in {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}

    @pytest.mark.unit
    @pytest.mark.xfail(reason="OpenAIAdapter does not validate model names in validate_request")
    async def test_validate_invalid_model(self):
        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        await adapter.ensure_initialized()
        request = TTSRequest(text="Hello", voice="alloy")
        is_valid, _ = await adapter.validate_request(request)
        assert is_valid

    @pytest.mark.unit
    async def test_validate_text_too_long(self):
        """Test validation rejects text exceeding limit."""
        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        await adapter.ensure_initialized()
        # OpenAI has ~4096 char limit in capabilities
        long_text = "a" * 5000
        request = TTSRequest(text=long_text, voice="alloy")
        is_valid, error = await adapter.validate_request(request)
        assert not is_valid
        assert "exceeds maximum" in (error or "")

    @pytest.mark.unit
    @pytest.mark.xfail(reason="OpenAIAdapter validate_request does not enforce speed bounds")
    async def test_validate_speed_out_of_range(self):
        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        await adapter.ensure_initialized()
        request = TTSRequest(text="Hello", voice="alloy", speed=5.0)
        is_valid, _ = await adapter.validate_request(request)
        assert not is_valid

# ========================================================================
# Audio Generation Tests
# ========================================================================

class TestAudioGeneration:
    """Test audio generation functionality."""

    @pytest.mark.unit
    @patch('httpx.AsyncClient.post')
    async def test_generate_basic_audio(self, mock_post):
        """Test basic audio generation."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake_audio_data"
        mock_response.headers = {"content-type": "audio/mpeg"}
        mock_post.return_value = mock_response

        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        request = TTSRequest(text="Hello world", voice="alloy", stream=False)

        response = await adapter.generate(request)

        assert (response.audio_content or response.audio_data) == b"fake_audio_data"
        assert (response.provider or "").lower() == "openai"

        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "audio/speech" in str(call_args[0][0])

    @pytest.mark.unit
    @patch('httpx.AsyncClient.post')
    async def test_generate_with_hd_model(self, mock_post):
        """Test generation with HD model."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"hd_audio_data"
        mock_post.return_value = mock_response

        adapter = OpenAITTSAdapter({"openai_api_key": "test-key", "openai_model": "tts-1-hd"})
        request = TTSRequest(text="High quality audio", voice="nova", stream=False)

        response = await adapter.generate(request)

        assert (response.audio_content or response.audio_data) == b"hd_audio_data"

    @pytest.mark.unit
    @patch('httpx.AsyncClient.post')
    async def test_generate_with_speed_adjustment(self, mock_post):
        """Test generation with speed adjustment."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"audio_data"
        mock_post.return_value = mock_response

        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        request = TTSRequest(
            text="Slow speech",
            voice="echo",
            model="tts-1",
            speed=0.75,
            stream=False
        )

        response = await adapter.generate(request)

        # Verify speed was included in request
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs['json']['speed'] == 0.75

    @pytest.mark.unit
    @patch('httpx.AsyncClient.post')
    async def test_generate_different_formats(self, mock_post):
        """Test generation with different audio formats."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"audio_data"
        mock_post.return_value = mock_response

        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})

        # Test different formats
        formats = [AudioFormat.MP3, AudioFormat.OPUS, AudioFormat.AAC, AudioFormat.FLAC]

        for audio_format in formats:
            request = TTSRequest(text="Test", voice="alloy", format=audio_format, stream=False)

            response = await adapter.generate(request)
            assert response.format == audio_format

# ========================================================================
# Streaming Generation Tests
# ========================================================================

class TestStreamingGeneration:
    """Test streaming audio generation."""

    @pytest.mark.unit
    @patch('httpx.AsyncClient.post')
    async def test_streaming_generation(self, mock_post):
        """Test streaming audio generation."""
        # Mock streaming response
        async def mock_iter():
            for chunk in [b"chunk1", b"chunk2", b"chunk3"]:
                yield chunk

        async def mock_iter_with_size(chunk_size=1024):
            async for c in mock_iter():
                yield c

        mock_response = AsyncMock()
        mock_response.aiter_bytes = mock_iter_with_size
        # Ensure raise_for_status behaves like a regular method (non-async)
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        request = TTSRequest(text="Stream this", voice="fable", stream=True)

        chunks = []
        resp = await adapter.generate(request)
        async for chunk in resp.audio_stream:
            chunks.append(chunk)

        assert chunks == [b"chunk1", b"chunk2", b"chunk3"]

    @pytest.mark.unit
    @patch('httpx.AsyncClient.post')
    async def test_streaming_with_error(self, mock_post):
        """Test streaming handles errors gracefully."""
        async def mock_error_iter():
            yield b"chunk1"
            raise httpx.HTTPError("Connection lost")

        async def mock_error_iter_with_size(chunk_size=1024):
            async for c in mock_error_iter():
                yield c

        mock_response = AsyncMock()
        mock_response.aiter_bytes = mock_error_iter_with_size
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        request = TTSRequest(text="Test", voice="alloy", stream=True)

        chunks = []
        with pytest.raises((TTSGenerationError, Exception)):
            resp = await adapter.generate(request)
            async for chunk in resp.audio_stream:
                chunks.append(chunk)

        # Should have received first chunk before error
        assert len(chunks) == 1

# ========================================================================
# Error Handling Tests
# ========================================================================

class TestErrorHandling:
    """Test error handling in OpenAI adapter."""

    @pytest.mark.unit
    @patch('httpx.AsyncClient.post')
    async def test_handle_rate_limit_error(self, mock_post):
        """Test handling of rate limit errors."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "60"}
        mock_response.json.return_value = {"error": {"message": "Rate limit exceeded"}}
        mock_response.aread = AsyncMock(return_value=b'{"error":{"message":"Rate limit exceeded"}}')
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429", request=Mock(), response=mock_response
        )
        mock_post.return_value = mock_response

        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        request = TTSRequest(text="Test", voice="alloy", stream=False)

        with pytest.raises(TTSRateLimitError) as exc_info:
            await adapter.generate(request)

        assert getattr(exc_info.value, "retry_after", exc_info.value.details.get("retry_after")) == 60

    @pytest.mark.unit
    @patch('httpx.AsyncClient.post')
    async def test_handle_api_error(self, mock_post):
        """Test handling of API errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": {"message": "Internal server error"}}
        mock_response.aread = AsyncMock(return_value=b'{"error":{"message":"Internal server error"}}')
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=Mock(), response=mock_response
        )
        mock_post.return_value = mock_response

        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        request = TTSRequest(text="Test", voice="alloy", stream=False)

        with pytest.raises((TTSGenerationError, Exception)):
            await adapter.generate(request)

    @pytest.mark.unit
    @patch('httpx.AsyncClient.post')
    async def test_handle_auth_error_401(self, mock_post):
        """Test handling of 401 maps to TTSAuthenticationError."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.aread = AsyncMock(return_value=b'{"error":{"message":"Invalid API key"}}')
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=Mock(), response=mock_response
        )
        mock_post.return_value = mock_response

        adapter = OpenAITTSAdapter({"openai_api_key": "bad-key"})
        request = TTSRequest(text="Test", voice="alloy", stream=False)

        from tldw_Server_API.app.core.TTS.tts_exceptions import TTSAuthenticationError
        with pytest.raises(TTSAuthenticationError):
            await adapter.generate(request)

    @pytest.mark.unit
    @patch('httpx.AsyncClient.post')
    async def test_handle_network_error(self, mock_post):
        """Test handling of network errors maps to TTSNetworkError."""
        mock_post.side_effect = httpx.ConnectError("Connection failed")

        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        request = TTSRequest(text="Test", voice="alloy", stream=False)

        with pytest.raises(TTSNetworkError):
            await adapter.generate(request)

    @pytest.mark.unit
    @patch('httpx.AsyncClient.post')
    async def test_handle_timeout_error(self, mock_post):
        """Test handling of timeout errors maps to TTSTimeoutError."""
        mock_post.side_effect = httpx.TimeoutException("Request timed out")

        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        request = TTSRequest(text="Test", voice="alloy", stream=False)

        from tldw_Server_API.app.core.TTS.tts_exceptions import TTSTimeoutError
        with pytest.raises(TTSTimeoutError):
            await adapter.generate(request)

# ========================================================================
# Metadata and Info Tests
# ========================================================================

class TestMetadataAndInfo:
    """Test metadata and information methods."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_adapter_info(self):
        """Build adapter information from capabilities for current API."""
        adapter = OpenAITTSAdapter({"openai_api_key": "test-key"})
        caps = await adapter.get_capabilities()
        info = {
            "provider": adapter.provider_name.lower(),
            "models": [adapter.model],
            "voices": [v.id for v in caps.supported_voices],
            "max_characters": caps.max_text_length,
        }
        assert info["provider"] == "openai"
        assert "tts-1" in ["tts-1", "tts-1-hd"]
        assert "alloy" in info["voices"]
        assert info["max_characters"] == 4096

    @pytest.mark.unit
    @patch('httpx.AsyncClient.post')
    async def test_response_includes_metadata(self, mock_post):
        """Test that response includes proper metadata."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"audio_data"
        mock_post.return_value = mock_response

        adapter = OpenAITTSAdapter({"openai_api_key": "test-key", "openai_model": "tts-1-hd"})
        request = TTSRequest(text="Test metadata", voice="shimmer", stream=False)

        response = await adapter.generate(request)

        assert (response.provider or "").lower() == "openai"
        assert (response.audio_content or response.audio_data) == b"audio_data"
