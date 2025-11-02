# adapter_registry.py
# Description: Registry and factory for TTS adapters
#
import asyncio
import time
import math
from typing import Dict, List, Optional, Type, Any, Set
from enum import Enum
#
# Third-party Imports
from loguru import logger
import importlib
#
# Local Imports
from .adapters.base import TTSAdapter, TTSCapabilities, ProviderStatus, AudioFormat
from .tts_exceptions import (
    TTSProviderNotConfiguredError,
    TTSProviderInitializationError,
    TTSModelNotFoundError
)
from .tts_resource_manager import get_resource_manager
from .tts_config import get_tts_config_manager, TTSConfig
from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat
#
#######################################################################################################################
#
# TTS Adapter Registry and Factory

class TTSProvider(Enum):
    """Enumeration of available TTS providers"""
    OPENAI = "openai"
    KOKORO = "kokoro"
    HIGGS = "higgs"
    DIA = "dia"
    CHATTERBOX = "chatterbox"
    ELEVENLABS = "elevenlabs"
    VIBEVOICE = "vibevoice"
    NEUTTS = "neutts"
    INDEX_TTS = "index_tts"
    # Additional providers
    ALLTALK = "alltalk"  # TODO: Implement AllTalk adapter
    MOCK = "mock"  # Mock provider for testing


class TTSAdapterRegistry:
    """
    Registry for TTS adapters.
    Manages registration, initialization, and access to TTS providers.
    """

    # Default adapter mappings (lazy, via dotted paths to avoid heavy imports at module import time)
    DEFAULT_ADAPTERS: Dict["TTSProvider", "str|Type[TTSAdapter]"] = {
        TTSProvider.OPENAI: "tldw_Server_API.app.core.TTS.adapters.openai_adapter.OpenAITTSAdapter",
        TTSProvider.KOKORO: "tldw_Server_API.app.core.TTS.adapters.kokoro_adapter.KokoroAdapter",
        TTSProvider.HIGGS: "tldw_Server_API.app.core.TTS.adapters.higgs_adapter.HiggsAdapter",
        TTSProvider.DIA: "tldw_Server_API.app.core.TTS.adapters.dia_adapter.DiaAdapter",
        TTSProvider.CHATTERBOX: "tldw_Server_API.app.core.TTS.adapters.chatterbox_adapter.ChatterboxAdapter",
        TTSProvider.ELEVENLABS: "tldw_Server_API.app.core.TTS.adapters.elevenlabs_adapter.ElevenLabsTTSAdapter",
        TTSProvider.VIBEVOICE: "tldw_Server_API.app.core.TTS.adapters.vibevoice_adapter.VibeVoiceAdapter",
        TTSProvider.NEUTTS: "tldw_Server_API.app.core.TTS.adapters.neutts_adapter.NeuTTSAdapter",
        TTSProvider.INDEX_TTS: "tldw_Server_API.app.core.TTS.adapters.index_tts_adapter.IndexTTS2Adapter",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the registry.

        Args:
            config: Configuration dictionary for all adapters
        """
        # Use unified configuration system
        if config:
            # Override config provided for testing
            self.config_manager = None
            # Ensure config is a dictionary
            if isinstance(config, dict):
                self.tts_config = config
                self.config = config
            else:
                # If config is not a dict (e.g., ConfigParser), convert it
                logger.warning(f"Non-dict config passed to TTSAdapterRegistry: {type(config)}")
                self.tts_config = {}
                self.config = {}
        else:
            self.config_manager = get_tts_config_manager()
            self.tts_config = self.config_manager.get_config()
            # Legacy config support - convert Pydantic model to dict
            self.config = model_dump_compat(self.tts_config)

        self._adapters: Dict[TTSProvider, TTSAdapter] = {}
        # Store either classes or dotted paths; resolve lazily when needed
        self._adapter_specs: Dict[TTSProvider, Any] = self.DEFAULT_ADAPTERS.copy()
        self._init_lock = asyncio.Lock()
        self._initialized_providers: Set[TTSProvider] = set()
        self._failed_providers: Dict[TTSProvider, float] = {}  # Provider -> retry timestamp

        def _extract_retry_seconds(raw_cfg: Any) -> Optional[float]:
            if raw_cfg is None:
                return None
            try:
                return float(raw_cfg)
            except (TypeError, ValueError):
                return None

        retry_seconds: Optional[float] = None
        if isinstance(self.config, dict):
            retry_seconds = _extract_retry_seconds(self.config.get("adapter_failure_retry_seconds"))
            if retry_seconds is None:
                perf_cfg = self.config.get("performance")
                if isinstance(perf_cfg, dict):
                    retry_seconds = _extract_retry_seconds(perf_cfg.get("adapter_failure_retry_seconds"))
        if retry_seconds is None and self.config_manager:
            try:
                perf_cfg = self.config_manager.get_config().performance  # type: ignore[call-arg]
                retry_seconds = _extract_retry_seconds(
                    getattr(perf_cfg, "adapter_failure_retry_seconds", None)
                )
            except Exception:
                pass

        if retry_seconds is not None and retry_seconds <= 0:
            retry_seconds = None

        self._failure_retry_seconds: Optional[float] = retry_seconds

    def register_adapter(self, provider: TTSProvider, adapter: Any):
        """
        Register a custom adapter class for a provider.

        Args:
            provider: The provider enum
            adapter: Adapter class or dotted import path string to register
        """
        self._adapter_specs[provider] = adapter
        try:
            name = adapter.__name__  # type: ignore[attr-defined]
        except Exception:
            name = str(adapter)
        logger.info(f"Registered adapter {name} for provider {provider.value}")

    def _schedule_retry(self, provider: TTSProvider) -> None:
        """Record a failed provider with optional retry backoff."""
        if self._failure_retry_seconds is None:
            self._failed_providers[provider] = math.inf
        else:
            self._failed_providers[provider] = time.time() + self._failure_retry_seconds

    def _resolve_adapter_class(self, spec: Any) -> Type[TTSAdapter]:
        """Resolve an adapter class from a class object or dotted path string."""
        if isinstance(spec, str):
            module_path, _, class_name = spec.rpartition(".")
            if not module_path:
                raise ImportError(f"Invalid adapter spec '{spec}'")
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            return cls
        return spec

    async def get_adapter(self, provider: TTSProvider) -> Optional[TTSAdapter]:
        """
        Get an adapter instance for the specified provider.

        Args:
            provider: The TTS provider

        Returns:
            Initialized adapter instance or None if unavailable

        Raises:
            TTSProviderNotConfiguredError: If provider is not registered
        """
        if provider not in self._adapter_specs:
            error_msg = f"No adapter registered for provider {provider.value}"
            logger.error(error_msg)
            raise TTSProviderNotConfiguredError(
                error_msg,
                provider=provider.value
            )

        retry_after = self._failed_providers.get(provider)
        if retry_after:
            if math.isinf(retry_after):
                logger.debug(f"Skipping {provider.value} - initialization previously failed (retry disabled)")
                return None
            if retry_after > time.time():
                logger.debug(
                    f"Skipping {provider.value} - retry available in {retry_after - time.time():.1f}s"
                )
                return None
            else:
                self._failed_providers.pop(provider, None)

        # Check if adapter already exists
        if provider in self._adapters:
            adapter = self._adapters[provider]
            if adapter.status == ProviderStatus.AVAILABLE:
                return adapter

        # Initialize adapter if needed
        async with self._init_lock:
            retry_after = self._failed_providers.get(provider)
            if retry_after:
                if math.isinf(retry_after):
                    logger.debug(f"Skipping {provider.value} - initialization previously failed (retry disabled)")
                    return None
                if retry_after > time.time():
                    logger.debug(
                        f"Skipping {provider.value} - retry available in {retry_after - time.time():.1f}s"
                    )
                    return None
                else:
                    self._failed_providers.pop(provider, None)

            if provider not in self._adapters:
                success = await self._initialize_adapter(provider)
                if not success:
                    self._schedule_retry(provider)
                    return None

            adapter = self._adapters.get(provider)
            if adapter and adapter.status == ProviderStatus.AVAILABLE:
                self._failed_providers.pop(provider, None)
                return adapter
            else:
                logger.warning(f"Adapter for {provider.value} is not available (status: {adapter.status if adapter else 'None'})")
                return None

    async def _initialize_adapter(self, provider: TTSProvider) -> bool:
        """
        Initialize an adapter for a provider.

        Args:
            provider: The TTS provider

        Returns:
            True if initialization successful

        Raises:
            TTSProviderInitializationError: If initialization fails
        """
        try:
            # Get adapter class (lazily resolve to avoid heavy imports during module import)
            adapter_spec = self._adapter_specs[provider]
            adapter_class = self._resolve_adapter_class(adapter_spec)

            # Get provider-specific config
            provider_config = self._get_provider_config(provider)

            # Check if provider is enabled using unified config
            if self.config_manager:
                if not self.config_manager.is_provider_enabled(provider.value):
                    logger.info(f"Provider {provider.value} is disabled in configuration")
                    return False
            else:
                # Using direct config for testing
                enabled_key = f"{provider.value}_enabled"
                if not self.config.get(enabled_key, True):
                    logger.info(f"Provider {provider.value} is disabled in configuration")
                    return False

            # Get resource manager for monitoring
            resource_manager = await get_resource_manager()

            # Check memory before initializing new adapter
            if resource_manager.memory_monitor.is_memory_critical():
                logger.warning(f"Skipping {provider.value} initialization due to memory constraints")
                return False

            # Create adapter instance
            logger.info(f"Initializing {provider.value} adapter...")
            adapter = adapter_class(config=provider_config)

            # Initialize the adapter
            success = await adapter.ensure_initialized()

            if success:
                self._adapters[provider] = adapter
                self._initialized_providers.add(provider)
                logger.info(f"Successfully initialized {provider.value} adapter")
                return True
            else:
                error_msg = f"Failed to initialize {provider.value} adapter"
                logger.error(error_msg)
                # Don't store failed adapter - it will be retried next time
                return False

        except Exception as e:
            logger.error(f"Error initializing {provider.value} adapter: {e}")
            # Don't store failed adapter - it will be retried next time
            return False

    def _get_provider_config(self, provider: TTSProvider) -> Dict[str, Any]:
        """
        Get configuration for a specific provider.

        Args:
            provider: The TTS provider

        Returns:
            Provider-specific configuration dictionary
        """
        if self.config_manager:
            # Use unified configuration system
            provider_cfg = self.config_manager.get_provider_config(provider.value)

            if provider_cfg:
                # Convert to dict for adapter consumption
                cfg = model_dump_compat(provider_cfg)

                # Duplicate generic keys into provider-prefixed aliases expected by adapters
                p = provider.value
                def alias(src: str, dst: str):
                    if src in cfg and dst not in cfg and cfg[src] is not None:
                        cfg[dst] = cfg[src]

                if p == 'openai':
                    alias('api_key', 'openai_api_key')
                    alias('base_url', 'openai_base_url')
                    alias('model', 'openai_model')
                elif p == 'kokoro':
                    alias('use_onnx', 'kokoro_use_onnx')
                    alias('model_path', 'kokoro_model_path')
                    alias('voices_json', 'kokoro_voices_json')
                    alias('voice_dir', 'kokoro_voice_dir')
                    alias('device', 'kokoro_device')
                elif p == 'higgs':
                    alias('model_path', 'higgs_model_path')
                    alias('tokenizer_path', 'higgs_tokenizer_path')
                    alias('device', 'higgs_device')
                    alias('use_fp16', 'higgs_use_fp16')
                    alias('batch_size', 'higgs_batch_size')
                elif p == 'dia':
                    alias('model_path', 'dia_model_path')
                    alias('device', 'dia_device')
                    alias('use_safetensors', 'dia_use_safetensors')
                    alias('use_bf16', 'dia_use_bf16')
                    alias('sample_rate', 'dia_sample_rate')
                    alias('auto_detect_speakers', 'dia_auto_detect_speakers')
                    alias('max_speakers', 'dia_max_speakers')
                elif p == 'chatterbox':
                    alias('device', 'chatterbox_device')
                    alias('use_multilingual', 'chatterbox_use_multilingual')
                    alias('disable_watermark', 'chatterbox_disable_watermark')
                    # model_path currently unused upstream; keep generic
                elif p == 'elevenlabs':
                    alias('api_key', 'elevenlabs_api_key')
                    alias('base_url', 'elevenlabs_base_url')
                    alias('model', 'elevenlabs_model')
                    alias('stability', 'elevenlabs_stability')
                    alias('similarity_boost', 'elevenlabs_similarity_boost')
                    alias('style', 'elevenlabs_style')
                    alias('speaker_boost', 'elevenlabs_speaker_boost')
                elif p == 'vibevoice':
                    alias('device', 'vibevoice_device')
                    alias('sample_rate', 'vibevoice_sample_rate')
                    alias('variant', 'vibevoice_variant')
                    alias('model_path', 'vibevoice_model_path')
                    alias('model_dir', 'vibevoice_model_dir')
                    alias('cache_dir', 'vibevoice_cache_dir')
                    alias('voices_dir', 'vibevoice_voices_dir')
                    alias('background_music', 'vibevoice_background_music')
                    alias('enable_singing', 'vibevoice_enable_singing')
                    alias('use_quantization', 'vibevoice_use_quantization')
                    alias('auto_cleanup', 'vibevoice_auto_cleanup')
                    alias('auto_download', 'vibevoice_auto_download')
                    alias('enable_sage', 'vibevoice_enable_sage')
                    alias('attention_type', 'vibevoice_attention_type')
                    alias('cfg_scale', 'vibevoice_cfg_scale')
                    alias('diffusion_steps', 'vibevoice_diffusion_steps')
                    alias('temperature', 'vibevoice_temperature')
                    alias('top_p', 'vibevoice_top_p')
                    alias('top_k', 'vibevoice_top_k')
                    alias('stream_chunk_size', 'vibevoice_stream_chunk_size')
                    alias('stream_buffer_size', 'vibevoice_stream_buffer_size')
                elif p == 'neutts':
                    alias('device', 'backbone_device')
                    alias('backbone_repo', 'backbone_repo')
                    alias('codec_repo', 'codec_repo')
                    alias('sample_rate', 'sample_rate')
                elif p == 'index_tts':
                    alias('model_dir', 'index_tts_model_dir')
                    alias('cfg_path', 'index_tts_cfg_path')
                    alias('device', 'index_tts_device')
                    alias('use_fp16', 'index_tts_use_fp16')
                    alias('use_cuda_kernel', 'index_tts_use_cuda_kernel')
                    alias('use_deepspeed', 'index_tts_use_deepspeed')
                    alias('interval_silence', 'index_tts_interval_silence')
                    alias('quick_streaming_tokens', 'index_tts_quick_streaming_tokens')
                    alias('max_text_tokens_per_segment', 'index_tts_max_text_tokens_per_segment')
                    alias('more_segment_before', 'index_tts_more_segment_before')
                    alias('verbose', 'index_tts_verbose')
                    alias('sample_rate', 'sample_rate')

                # Generic target latency for local providers
                if p == 'chatterbox':
                    alias('target_latency_ms', 'chatterbox_target_latency_ms')
                elif p == 'kokoro':
                    alias('target_latency_ms', 'kokoro_target_latency_ms')
                elif p == 'dia':
                    alias('target_latency_ms', 'dia_target_latency_ms')
                elif p == 'higgs':
                    alias('target_latency_ms', 'higgs_target_latency_ms')

                return cfg

        # Fallback to legacy config
        provider_config = self.config.copy()

        # Add provider-specific overrides
        provider_key = f"{provider.value}_config"
        if provider_key in self.config:
            provider_config.update(self.config[provider_key])

        return provider_config

    async def get_all_capabilities(self) -> Dict[TTSProvider, TTSCapabilities]:
        """
        Get capabilities of all available adapters.

        Returns:
            Dictionary mapping providers to their capabilities
        """
        capabilities = {}

        for provider in TTSProvider:
            # Skip providers that are disabled or have failed
            retry_after = self._failed_providers.get(provider)
            if retry_after:
                if math.isinf(retry_after):
                    continue
                if retry_after > time.time():
                    continue
                self._failed_providers.pop(provider, None)

            # Only try to get adapters that are likely to work quickly
            # Skip local model providers in testing unless explicitly enabled
            if provider in [TTSProvider.KOKORO, TTSProvider.HIGGS, TTSProvider.DIA,
                           TTSProvider.CHATTERBOX, TTSProvider.VIBEVOICE]:
                # Check if explicitly enabled in config
                if self.config_manager:
                    if not self.config_manager.is_provider_enabled(provider.value):
                        continue
                else:
                    enabled_key = f"{provider.value}_enabled"
                    if not self.config.get(enabled_key, False):
                        continue

            try:
                # Try to get adapter with a timeout to avoid hanging
                adapter = await asyncio.wait_for(self.get_adapter(provider), timeout=5.0)
                if adapter:
                    caps = adapter.capabilities
                    if caps:
                        capabilities[provider] = caps
            except asyncio.TimeoutError:
                logger.warning(f"Timeout getting capabilities for {provider.value}")
                if self._failure_retry_seconds is not None:
                    self._schedule_retry(provider)
            except Exception as e:
                logger.debug(f"Error getting capabilities for {provider.value}: {e}")
                if self._failure_retry_seconds is not None:
                    self._schedule_retry(provider)

        return capabilities

    async def find_adapter_for_requirements(
        self,
        language: Optional[str] = None,
        format: Optional[AudioFormat] = None,
        supports_streaming: Optional[bool] = None,
        supports_emotion: Optional[bool] = None,
        supports_voice_cloning: Optional[bool] = None,
        supports_multi_speaker: Optional[bool] = None
    ) -> Optional[TTSAdapter]:
        """
        Find an adapter that meets specific requirements.

        Args:
            language: Required language support
            format: Required audio format
            supports_streaming: Requires streaming support
            supports_emotion: Requires emotion control
            supports_voice_cloning: Requires voice cloning
            supports_multi_speaker: Requires multi-speaker support

        Returns:
            First adapter that meets all requirements, or None
        """
        for provider in self._get_provider_priority():
            adapter = await self.get_adapter(provider)
            if not adapter or not adapter.capabilities:
                continue

            caps = adapter.capabilities

            # Check requirements
            if language and language not in caps.supported_languages:
                continue
            if format and format not in caps.supported_formats:
                continue
            if supports_streaming and not caps.supports_streaming:
                continue
            if supports_emotion is not None and caps.supports_emotion_control != supports_emotion:
                continue
            if supports_voice_cloning is not None and caps.supports_voice_cloning != supports_voice_cloning:
                continue
            if supports_multi_speaker is not None and caps.supports_multi_speaker != supports_multi_speaker:
                continue

            return adapter

        return None

    def _get_provider_priority(self) -> List[TTSProvider]:
        """
        Get provider priority order.
        Can be customized via configuration.

        Returns:
            Ordered list of providers to try
        """
        # Use unified configuration priority
        if self.config_manager:
            priority_names = self.config_manager.get_provider_priority()
        else:
            # Use priority from config if available
            priority_names = self.config.get("provider_priority", [])

        priority = []
        for provider_name in priority_names:
            try:
                provider = TTSProvider(provider_name)
                priority.append(provider)
            except ValueError:
                logger.warning(f"Unknown provider in priority list: {provider_name}")

        # Fallback to default if no valid providers
        if not priority:
            priority = [
                TTSProvider.OPENAI,
                TTSProvider.KOKORO,
                TTSProvider.CHATTERBOX,
                TTSProvider.DIA,
                TTSProvider.HIGGS
            ]

        return priority

    async def close_all(self):
        """Close all initialized adapters and clean up resources"""
        logger.info("Closing all TTS adapters...")

        # Get resource manager for cleanup
        try:
            resource_manager = await get_resource_manager()
        except Exception as e:
            logger.warning(f"Could not get resource manager for cleanup: {e}")
            resource_manager = None

        tasks = []
        for provider, adapter in self._adapters.items():
            logger.info(f"Closing {provider.value} adapter...")
            tasks.append(adapter.close())

            # Unregister from resource manager if available
            if resource_manager:
                try:
                    await resource_manager.unregister_model(provider.value)
                except Exception as e:
                    logger.warning(f"Error unregistering {provider.value} from resource manager: {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._adapters.clear()
        self._initialized_providers.clear()

        # Clean up resource manager connections
        if resource_manager:
            try:
                await resource_manager.cleanup_all()
            except Exception as e:
                logger.warning(f"Error during resource manager cleanup: {e}")

        logger.info("All TTS adapters closed")

    def get_status_summary(self) -> Dict[str, Any]:
        """
        Get status summary of all adapters.

        Returns:
            Dictionary with status information
        """
        summary = {
            "total_providers": len(TTSProvider),
            "initialized": len(self._initialized_providers),
            "available": 0,
            "providers": {}
        }

        for provider in TTSProvider:
            adapter = self._adapters.get(provider)
            if adapter:
                status_value = adapter.status.value
                is_available = adapter.status == ProviderStatus.AVAILABLE
                if is_available:
                    summary["available"] += 1
                provider_info = {
                    "status": status_value,
                    "initialized": bool(getattr(adapter, "_initialized", False)),
                    "failed": (
                        provider in self._failed_providers
                        and self._failed_providers[provider] > time.time()
                    ),
                }
                try:
                    if adapter.capabilities:
                        provider_info["supports_streaming"] = adapter.capabilities.supports_streaming
                        provider_info["supported_formats"] = sorted(fmt.value for fmt in adapter.capabilities.supported_formats)
                        provider_info["sample_rate"] = adapter.capabilities.sample_rate
                except Exception:
                    pass
            else:
                status_value = "not_initialized"
                provider_info = {
                    "status": status_value,
                    "initialized": False,
                    "failed": (
                        provider in self._failed_providers
                        and self._failed_providers[provider] > time.time()
                    ),
                }
            summary["providers"][provider.value] = provider_info

        return summary


class TTSAdapterFactory:
    """
    Factory for creating and managing TTS adapters.
    Provides high-level interface for TTS operations.
    """

    MODEL_PROVIDER_MAP: Dict[str, TTSProvider] = {
        # OpenAI models
        "tts-1": TTSProvider.OPENAI,
        "tts-1-hd": TTSProvider.OPENAI,

        # Kokoro models
        "kokoro": TTSProvider.KOKORO,
        "kokoro-v0_19": TTSProvider.KOKORO,
        "kokoro-onnx": TTSProvider.KOKORO,

        # Higgs models
        "higgs": TTSProvider.HIGGS,
        "higgs-v2": TTSProvider.HIGGS,
        "higgs-audio-v2": TTSProvider.HIGGS,

        # ElevenLabs models
        "elevenlabs": TTSProvider.ELEVENLABS,
        "eleven_monolingual_v1": TTSProvider.ELEVENLABS,
        "eleven_multilingual_v1": TTSProvider.ELEVENLABS,
        "eleven_multilingual_v2": TTSProvider.ELEVENLABS,
        "eleven_turbo_v2": TTSProvider.ELEVENLABS,

        # Dia models
        "dia": TTSProvider.DIA,
        "dia-1.6b": TTSProvider.DIA,

        # Chatterbox models
        "chatterbox": TTSProvider.CHATTERBOX,
        "chatterbox-emotion": TTSProvider.CHATTERBOX,

        # VibeVoice models
        "vibevoice": TTSProvider.VIBEVOICE,
        "vibevoice-1.5b": TTSProvider.VIBEVOICE,
        "vibevoice-7b": TTSProvider.VIBEVOICE,
        "microsoft/vibevoice-1.5b": TTSProvider.VIBEVOICE,
        "westzhang/vibevoice-large-pt": TTSProvider.VIBEVOICE,

        # NeuTTS models
        "neutts": TTSProvider.NEUTTS,
        "neutts-air": TTSProvider.NEUTTS,
        "neuphonic/neutts-air": TTSProvider.NEUTTS,
        "neutts-air-q4-gguf": TTSProvider.NEUTTS,
        "neutts-air-q8-gguf": TTSProvider.NEUTTS,
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the factory.

        Args:
            config: Configuration for all adapters
        """
        self.registry = TTSAdapterRegistry(config)

    def get_provider_for_model(self, model: Optional[str]) -> Optional[TTSProvider]:
        """
        Resolve which provider should serve a model name.

        Args:
            model: Model identifier from the request

        Returns:
            Matching TTSProvider enum or None
        """
        if not model:
            return None
        return self.MODEL_PROVIDER_MAP.get(model.lower())

    async def get_adapter_by_model(self, model: str) -> Optional[TTSAdapter]:
        """
        Get adapter based on model name.
        Maps model names to providers.

        Args:
            model: Model name (e.g., "tts-1", "kokoro", "higgs")

        Returns:
            Appropriate adapter or None
        """
        provider = self.get_provider_for_model(model)
        if not provider:
            logger.warning(f"Unknown model: {model}")
            return None

        return await self.registry.get_adapter(provider)

    async def get_best_adapter(self, **requirements) -> Optional[TTSAdapter]:
        """
        Get the best adapter for given requirements.

        Args:
            **requirements: Requirements for the adapter

        Returns:
            Best matching adapter or None
        """
        return await self.registry.find_adapter_for_requirements(**requirements)

    async def close(self):
        """Close all adapters"""
        await self.registry.close_all()

    def get_status(self) -> Dict[str, Any]:
        """Get factory status"""
        return self.registry.get_status_summary()


# Singleton instance management
_factory_instance: Optional[TTSAdapterFactory] = None
_factory_lock = asyncio.Lock()


async def get_tts_factory(config: Optional[Dict[str, Any]] = None) -> TTSAdapterFactory:
    """
    Get or create the TTS adapter factory singleton.

    Args:
        config: Configuration for the factory

    Returns:
        TTSAdapterFactory instance
    """
    global _factory_instance

    if _factory_instance is None:
        async with _factory_lock:
            if _factory_instance is None:
                _factory_instance = TTSAdapterFactory(config)
                logger.info("TTS Adapter Factory initialized")

    return _factory_instance


async def close_tts_factory():
    """Close the TTS factory and all adapters"""
    global _factory_instance

    if _factory_instance:
        await _factory_instance.close()
        _factory_instance = None
        logger.info("TTS Adapter Factory closed")

#
# End of adapter_registry.py
#######################################################################################################################
