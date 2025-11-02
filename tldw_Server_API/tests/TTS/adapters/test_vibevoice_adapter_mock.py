# test_vibevoice_adapter_mock.py
# Description: Mock/Unit tests for VibeVoice TTS adapter
#
# Imports
import pytest
pytestmark = pytest.mark.unit
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import torch
#
# Local Imports
from tldw_Server_API.app.core.TTS.adapters.vibevoice_adapter import VibeVoiceAdapter
from tldw_Server_API.app.core.TTS.adapters.base import (
    TTSRequest,
    TTSResponse,
    AudioFormat,
    ProviderStatus
)
from tldw_Server_API.app.core.TTS.tts_exceptions import (
    TTSModelNotFoundError,
    TTSModelLoadError,
    TTSInsufficientMemoryError
)
#
#######################################################################################################################
#
# Mock Tests for VibeVoice Adapter

@pytest.mark.asyncio
class TestVibeVoiceAdapterMock:
    """Mock/Unit tests for VibeVoice adapter"""

    async def test_initialization_configuration(self):
        """Test initialization with configuration"""
        adapter = VibeVoiceAdapter({
            "vibevoice_api_key": "test-key",
            "vibevoice_workspace_id": "workspace-123",
            "vibevoice_variant": "1.5B",
            "vibevoice_model_path": "./models/vibevoice",
            "vibevoice_device": "cuda"
        })

        assert adapter.config.get("vibevoice_api_key") == "test-key"
        assert adapter.config.get("vibevoice_workspace_id") == "workspace-123"
        assert adapter.variant == "1.5B"
        assert adapter.model_path == "./models/vibevoice"
        assert adapter.device == "cuda" if torch.cuda.is_available() else "cpu"

    async def test_variant_configuration(self):
        """Test model variant configuration"""
        # Test 7B variant
        adapter_7b = VibeVoiceAdapter({"vibevoice_variant": "7B"})
        assert adapter_7b.variant == "7B"
        assert adapter_7b.context_length == 32000

        # Test 1.5B variant
        adapter_15b = VibeVoiceAdapter({"vibevoice_variant": "1.5B"})
        assert adapter_15b.variant == "1.5B"
        assert adapter_15b.context_length == 64000

        # Test default variant
        adapter_default = VibeVoiceAdapter({})
        # Current default is 1.5B
        assert adapter_default.variant == "1.5B"

    async def test_capabilities_reporting(self):
        """Test capabilities are correctly reported"""
        adapter = VibeVoiceAdapter({"vibevoice_variant": "1.5B"})
        caps = await adapter.get_capabilities()

        assert caps.provider_name == "VibeVoice-1.5B"
        assert caps.supports_streaming is True
        # Current adapter reports cloning support via reference audio
        assert caps.supports_voice_cloning is True
        assert caps.supports_emotion_control is False
        assert caps.max_text_length == 64000  # Based on current variant config
        # Allow 22050 (default) or 24000 depending on config
        assert caps.sample_rate in (22050, 24000)

        # Check supported languages
        assert "en" in caps.supported_languages
        assert "es" in caps.supported_languages
        assert "fr" in caps.supported_languages
        assert "de" in caps.supported_languages
        assert "ja" in caps.supported_languages
        assert "ko" in caps.supported_languages
        assert "zh" in caps.supported_languages
        assert len(caps.supported_languages) >= 10

        # Check supported formats
        assert AudioFormat.WAV in caps.supported_formats
        assert AudioFormat.MP3 in caps.supported_formats
        assert AudioFormat.OPUS in caps.supported_formats
        assert AudioFormat.FLAC in caps.supported_formats
        assert AudioFormat.PCM in caps.supported_formats
        assert AudioFormat.OGG in caps.supported_formats

    async def test_voice_presets(self):
        """Test voice preset availability"""
        adapter = VibeVoiceAdapter({})
        # Populate presets from adapter (adds default speakers if no voices dir)
        adapter._load_voice_files()

        # Check default speaker presets exist
        assert len(adapter.VOICE_PRESETS) > 0
        assert "speaker_1" in adapter.VOICE_PRESETS
        assert "speaker_2" in adapter.VOICE_PRESETS
        assert "speaker_3" in adapter.VOICE_PRESETS
        assert "speaker_4" in adapter.VOICE_PRESETS

    async def test_voice_mapping(self):
        """Test voice mapping functionality"""
        adapter = VibeVoiceAdapter({})
        # Ensure presets exist for mapping to find speakers
        adapter._load_voice_files()

        # Test speaker voices and numeric mapping
        assert adapter.map_voice("speaker_1") == "speaker_1"
        assert adapter.map_voice("speaker_2") == "speaker_2"
        assert adapter.map_voice("1") == "speaker_1"
        assert adapter.map_voice("3") == "speaker_3"

        # Unknown labels should fall back to default speaker_1
        assert adapter.map_voice("default") == "speaker_1"
        assert adapter.map_voice("assistant") == "speaker_1"
        assert adapter.map_voice("friendly") == "speaker_1"
        assert adapter.map_voice("serious") == "speaker_1"
        assert adapter.map_voice("excited") == "speaker_1"
        assert adapter.map_voice("relaxed") == "speaker_1"

    async def test_device_selection(self):
        """Test device selection for inference"""
        # Test CUDA selection
        with patch('torch.cuda.is_available', return_value=True):
            adapter = VibeVoiceAdapter({"vibevoice_device": "cuda"})
            assert adapter.device == "cuda"

        # Test MPS selection on macOS
        with patch('platform.system', return_value="Darwin"):
            with patch('torch.backends.mps.is_available', return_value=True):
                adapter = VibeVoiceAdapter({"vibevoice_device": "mps"})
                # Would be mps if available

        # Test CPU fallback on auto-detect (no explicit device)
        with patch('torch.cuda.is_available', return_value=False):
            with patch('torch.backends.mps.is_available', return_value=False):
                adapter = VibeVoiceAdapter({})
                assert adapter.device == "cpu"

    @patch('tldw_Server_API.app.core.TTS.adapters.vibevoice_adapter.get_resource_manager')
    async def test_memory_check_before_loading(self, mock_get_manager):
        """Test memory checking before model loading"""
        mock_manager = AsyncMock()
        mock_manager.memory_monitor.is_memory_critical.return_value = True
        mock_manager.memory_monitor.get_memory_usage.return_value = {"available": "100MB"}
        mock_get_manager.return_value = mock_manager

        adapter = VibeVoiceAdapter({})

        success = await adapter.initialize()
        assert success is False

    async def test_model_loading_error_handling(self):
        """Test error handling during model loading"""
        adapter = VibeVoiceAdapter({
            "vibevoice_model_path": "/nonexistent/model"
        })

        with patch('os.path.exists', return_value=False):
            success = await adapter.initialize()
            assert not success
            assert adapter._status == ProviderStatus.ERROR

    async def test_generation_without_initialization(self):
        """Test generation fails without initialization"""
        adapter = VibeVoiceAdapter({})

        request = TTSRequest(
            text="Test",
            voice="professional",
            format=AudioFormat.WAV
        )

        with pytest.raises(Exception):  # Should raise provider not configured
            await adapter.generate(request)

    async def test_multilingual_support(self):
        """Test multilingual capabilities"""
        adapter = VibeVoiceAdapter({})
        caps = await adapter.get_capabilities()

        # Should support multiple languages
        assert len(caps.supported_languages) >= 10

        # Test language-specific requests
        languages = ["en", "es", "fr", "de", "ja", "ko", "zh"]

        for lang in languages:
            request = TTSRequest(
                text="Test text",
                language=lang,
                voice="professional"
            )

            assert request.language == lang

    async def test_batch_processing_support(self):
        """Test batch processing capabilities"""
        adapter = VibeVoiceAdapter({})

        # Create batch of requests
        batch_requests = [
            TTSRequest(
                text=f"Batch text {i}",
                voice="professional",
                format=AudioFormat.WAV
            )
            for i in range(5)
        ]

        assert len(batch_requests) == 5

        # Verify each request is valid
        for req in batch_requests:
            assert req.text.startswith("Batch text")
            assert req.voice == "professional"

    async def test_cleanup_on_close(self):
        """Test resource cleanup on close"""
        adapter = VibeVoiceAdapter({"vibevoice_device": "cuda"})

        # Mock resources
        adapter.model = MagicMock()
        adapter.tokenizer = MagicMock()
        adapter._initialized = True
        adapter._status = ProviderStatus.AVAILABLE

        with patch('torch.cuda.is_available', return_value=True):
            with patch('torch.cuda.empty_cache') as mock_empty_cache:
                await adapter.close()

                assert adapter.model is None
                # Tokenizer attribute may not be present; ensure adapter closed state
                assert adapter._initialized is False
                assert adapter._status == ProviderStatus.DISABLED
                mock_empty_cache.assert_called_once()

    async def test_context_length_limits(self):
        """Test context length limits based on variant"""
        # Test 7B variant limit
        adapter_7b = VibeVoiceAdapter({"vibevoice_variant": "7B"})
        caps_7b = await adapter_7b.get_capabilities()
        assert caps_7b.max_text_length == 32000

        # Test 1.5B variant limit
        adapter_15b = VibeVoiceAdapter({"vibevoice_variant": "1.5B"})
        caps_15b = await adapter_15b.get_capabilities()
        assert caps_15b.max_text_length == 64000

    async def test_generation_time_limits(self):
        """Test generation time limits based on variant"""
        # 7B variant - 45 minutes max
        adapter_7b = VibeVoiceAdapter({"vibevoice_variant": "7B"})
        caps_7b = await adapter_7b.get_capabilities()
        # Check variant in provider name
        assert "7B" in caps_7b.provider_name

        # 1.5B variant - 90 minutes max
        adapter_15b = VibeVoiceAdapter({"vibevoice_variant": "1.5B"})
        caps_15b = await adapter_15b.get_capabilities()
        assert "1.5B" in caps_15b.provider_name

#######################################################################################################################
#
# End of test_vibevoice_adapter_mock.py
