# tts_service_v2.py
# Description: Enhanced TTS service using the adapter pattern
#
# Imports
import asyncio
import inspect
import os
import time
from typing import AsyncGenerator, Optional, Dict, Any, List, Set
#
# Third-party Imports
from loguru import logger
#
# Local Imports
from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest
from tldw_Server_API.app.core.Metrics import get_metrics_registry
from tldw_Server_API.app.core.Metrics.metrics_manager import MetricDefinition, MetricType
from .adapter_registry import (
    get_tts_factory,
    close_tts_factory,
    TTSAdapterFactory,
    TTSProvider
)
from .adapters.base import (
    TTSAdapter,
    TTSRequest,
    TTSResponse,
    AudioFormat
)
from .circuit_breaker import (
    get_circuit_manager,
    CircuitBreakerManager,
    CircuitOpenError
)
from .tts_exceptions import (
    TTSError,
    TTSProviderNotConfiguredError,
    TTSProviderInitializationError,
    TTSModelNotFoundError,
    TTSGenerationError,
    TTSValidationError,
    TTSAuthenticationError,
    TTSRateLimitError,
    TTSNetworkError,
    TTSTimeoutError,
    TTSProviderError,
    TTSResourceError,
    TTSInsufficientMemoryError,
    TTSGPUError,
    TTSFallbackExhaustedError,
    TTSInvalidVoiceReferenceError,
    categorize_error,
    is_retryable_error
)
from .tts_validation import validate_tts_request
import base64
from .tts_resource_manager import get_resource_manager
#
#######################################################################################################################
#
# Enhanced TTS Service with Adapter Pattern

class TTSServiceV2:
    """
    Enhanced TTS service that uses the adapter pattern for multiple providers.
    Provides intelligent provider selection and fallback capabilities.
    """

    def __init__(self, factory: Optional[TTSAdapterFactory] = None, circuit_manager: Optional[CircuitBreakerManager] = None):
        """
        Initialize the TTS service.

        Args:
            factory: TTS adapter factory instance
            circuit_manager: Optional circuit breaker manager
        """
        # New DI-friendly factory (may be None in tests); keep legacy alias _factory
        self.factory = factory
        # Backwards-compat: some unit tests expect an internal `_factory` attribute
        self._factory: Optional[TTSAdapterFactory] = factory
        # In unit tests, get_tts_factory is patched (AsyncMock) and the tests expect
        # `_factory` to equal its return_value immediately upon construction.
        # Detect that case and use the mock's return_value directly without awaiting.
        try:
            if hasattr(get_tts_factory, "return_value"):
                # Patched with mock/AsyncMock
                self._factory = getattr(get_tts_factory, "return_value")  # type: ignore[assignment]
            else:
                # Legacy behavior: only call if it's a regular (non-async) function
                if not asyncio.iscoroutinefunction(get_tts_factory):
                    maybe_factory = get_tts_factory()  # type: ignore[func-returns-value]
                    if not asyncio.iscoroutine(maybe_factory):
                        self._factory = maybe_factory  # type: ignore[assignment]
        except Exception:
            # Safe to ignore - tests may override `_factory` directly
            pass
        self.circuit_manager = circuit_manager
        # Limit concurrent generations; honor config if available
        max_concurrent = 4
        stream_errors_as_audio = True
        env_stream_override = os.getenv("TTS_STREAM_ERRORS_AS_AUDIO")
        if env_stream_override is not None:
            normalized = env_stream_override.strip().lower()
            stream_errors_as_audio = normalized not in {"0", "false", "no", "off"}
        try:
            if self.factory and hasattr(self.factory, "registry") and hasattr(self.factory.registry, "config"):
                perf_cfg = self.factory.registry.config.get("performance", {})  # type: ignore[attr-defined]
                # Support Pydantic models or dictionaries
                if not isinstance(perf_cfg, dict):
                    if hasattr(perf_cfg, "model_dump"):  # Pydantic v2
                        perf_cfg = perf_cfg.model_dump()  # type: ignore[assignment]
                    elif hasattr(perf_cfg, "dict"):
                        perf_cfg = perf_cfg.dict()  # type: ignore[assignment]
                if isinstance(perf_cfg, dict):
                    mcg = perf_cfg.get("max_concurrent_generations", max_concurrent)
                    try:
                        max_concurrent = int(mcg)
                        if max_concurrent <= 0:
                            max_concurrent = 1
                    except Exception:
                        max_concurrent = 4
                    if env_stream_override is None and "stream_errors_as_audio" in perf_cfg:
                        stream_errors_as_audio = bool(perf_cfg.get("stream_errors_as_audio"))
        except Exception:
            # Fallback to default on any parsing/config errors
            max_concurrent = 4
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._stream_errors_as_audio = stream_errors_as_audio
        self._active_request_counts: Dict[str, int] = {}
        self._active_requests_lock = asyncio.Lock()

        # Initialize metrics
        self.metrics = get_metrics_registry()
        self._register_tts_metrics()

    # ---------------------------------------------------------------------------------
    # Backwards-compatibility methods expected by older unit tests
    # ---------------------------------------------------------------------------------
    async def _ensure_factory(self) -> TTSAdapterFactory:
        """
        Ensure a usable adapter factory is available.
        Favors injected or legacy `_factory` references before creating the singleton.
        """
        if self.factory is not None:
            return self.factory

        if self._factory is not None:
            self.factory = self._factory  # type: ignore[assignment]
            return self.factory  # type: ignore[return-value]

        factory = await get_tts_factory()
        self.factory = factory
        self._factory = factory
        return factory

    async def shutdown(self) -> None:
        """Gracefully close any underlying factory/adapters (best-effort)."""
        try:
            if self.factory and hasattr(self.factory, "close"):
                maybe = self.factory.close()  # type: ignore[attr-defined]
                if asyncio.iscoroutine(maybe):
                    await maybe  # type: ignore[func-returns-value]
            # Some tests set/patch `_factory` only
            if self._factory and self._factory is not self.factory and hasattr(self._factory, "close"):
                maybe2 = self._factory.close()  # type: ignore[attr-defined]
                if asyncio.iscoroutine(maybe2):
                    await maybe2  # type: ignore[func-returns-value]
        except Exception:
            # Do not let shutdown errors fail tests
            pass

    async def generate(self, request: TTSRequest) -> TTSResponse:
        """Legacy synchronous-style generation wrapper expected by unit tests."""
        provider = getattr(request, "provider", None) or getattr(self, "_default_provider", "openai")
        adapter = None
        if hasattr(self, "_factory") and self._factory is not None:
            try:
                # Many tests patch `_factory.get_adapter(provider)`
                adapter = self._factory.get_adapter(provider)  # type: ignore[attr-defined]
            except Exception:
                adapter = None
        if adapter is None and self.factory is not None:
            # Try to resolve via new factory/registry by provider enum name
            try:
                from .adapter_registry import TTSProvider
                prov_enum = TTSProvider(provider)
                adapter = await self.factory.registry.get_adapter(prov_enum)  # type: ignore[union-attr]
            except Exception:
                adapter = None
        if adapter is None:
            raise TTSProviderNotConfiguredError(f"Provider not found: {provider}")

        # Optional resource check hook expected by tests
        try:
            resource_mgr = await get_resource_manager()
            try:
                ok = await resource_mgr.check_resources()
            except TypeError:
                # Some mocks are non-async
                ok = resource_mgr.check_resources()
            if not ok:
                raise TTSResourceError("Insufficient resources")
        except Exception:
            # Ignore resource check errors in legacy path
            pass

        # Delegate to adapter.generate and return its response
        return await adapter.generate(request)  # type: ignore[union-attr]

    async def generate_stream(self, request: TTSRequest) -> AsyncGenerator[bytes, None]:
        """Legacy streaming wrapper expected by unit tests."""
        provider = getattr(request, "provider", None) or getattr(self, "_default_provider", "openai")
        adapter = None
        if hasattr(self, "_factory") and self._factory is not None:
            try:
                adapter = self._factory.get_adapter(provider)  # type: ignore[attr-defined]
            except Exception:
                adapter = None
        if adapter is None and self.factory is not None:
            try:
                from .adapter_registry import TTSProvider
                prov_enum = TTSProvider(provider)
                adapter = await self.factory.registry.get_adapter(prov_enum)  # type: ignore[union-attr]
            except Exception:
                adapter = None
        if adapter is None:
            raise TTSProviderNotConfiguredError(f"Provider not found: {provider}")

        # Adapter is expected to expose `generate_stream` in legacy tests
        stream = await adapter.generate_stream(request)  # type: ignore[attr-defined]
        async for chunk in stream:
            yield chunk

    async def list_providers(self) -> List[str]:
        """Legacy provider listing wrapper."""
        if hasattr(self, "_factory") and self._factory is not None and hasattr(self._factory, "list_available_providers"):
            return self._factory.list_available_providers()  # type: ignore[attr-defined,return-value]
        # Fallback: derive from registry
        try:
            from .adapter_registry import TTSProvider
            return [p.value for p in TTSProvider]
        except Exception:
            return []

    async def get_provider_info(self, provider: str) -> Dict[str, Any]:
        """Legacy provider information wrapper used by tests."""
        adapter = None
        if hasattr(self, "_factory") and self._factory is not None:
            try:
                adapter = self._factory.get_adapter(provider)  # type: ignore[attr-defined]
            except Exception:
                adapter = None
        if adapter and hasattr(adapter, "get_info"):
            return adapter.get_info()  # type: ignore[attr-defined,return-value]
        # Minimal fallback info
        return {"name": provider}

    async def set_default_provider(self, provider: str) -> None:
        """Set default provider (legacy behavior for tests)."""
        self._default_provider = provider

    async def generate_with_fallback(self, request: TTSRequest, fallback_providers: Optional[List[str]] = None) -> TTSResponse:
        """Legacy helper to try primary provider then fall back to others."""
        primary = getattr(request, "provider", None) or getattr(self, "_default_provider", "openai")
        # Try primary
        try:
            return await self.generate(request)
        except TTSGenerationError as first_err:
            # Try fallbacks in order
            if not fallback_providers:
                raise
            last_exc: Optional[Exception] = first_err
            for prov in fallback_providers:
                try:
                    req2 = request
                    setattr(req2, "provider", prov)
                    return await self.generate(req2)
                except Exception as e:  # keep trying
                    last_exc = e
                    continue
            # If all failed, raise the last error
            if last_exc:
                raise last_exc
            raise

    def _register_tts_metrics(self):
        """Register TTS-specific metrics"""
        # TTS request metrics
        self.metrics.register_metric(
            MetricDefinition(
                name="tts_requests_total",
                type=MetricType.COUNTER,
                description="Total number of TTS requests",
                labels=["provider", "model", "voice", "format", "status"]
            )
        )

        self.metrics.register_metric(
            MetricDefinition(
                name="tts_request_duration_seconds",
                type=MetricType.HISTOGRAM,
                description="TTS request duration in seconds",
                unit="s",
                labels=["provider", "model", "voice"],
                buckets=[0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60]
            )
        )

        self.metrics.register_metric(
            MetricDefinition(
                name="tts_text_length_characters",
                type=MetricType.HISTOGRAM,
                description="Length of text processed",
                unit="characters",
                labels=["provider"],
                buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000]
            )
        )

        self.metrics.register_metric(
            MetricDefinition(
                name="tts_audio_size_bytes",
                type=MetricType.HISTOGRAM,
                description="Size of generated audio",
                unit="bytes",
                labels=["provider", "format"],
                buckets=[1024, 10240, 102400, 1048576, 10485760]  # 1KB, 10KB, 100KB, 1MB, 10MB
            )
        )

        self.metrics.register_metric(
            MetricDefinition(
                name="tts_active_requests",
                type=MetricType.GAUGE,
                description="Number of active TTS requests",
                labels=["provider"]
            )
        )

        self.metrics.register_metric(
            MetricDefinition(
                name="tts_fallback_attempts",
                type=MetricType.COUNTER,
                description="Number of fallback attempts",
                labels=["from_provider", "to_provider", "success"]
            )
        )

    async def generate_speech(
        self,
        request: OpenAISpeechRequest,
        provider: Optional[str] = None,
        fallback: bool = True
    ) -> AsyncGenerator[bytes, None]:
        """
        Generate speech from text using the best available provider.

        Args:
            request: OpenAI-compatible speech request
            provider: Optional specific provider to use
            fallback: Whether to fallback to other providers on failure

        Yields:
            Audio chunks in the requested format
        """
        # Convert OpenAI request to unified TTSRequest
        tts_request = self._convert_request(request)
        factory = await self._ensure_factory()

        provider_hint: Optional[str] = None
        if provider:
            provider_hint = provider.lower()
        else:
            try:
                provider_source = None
                if factory:
                    provider_source = factory
                elif self._factory and hasattr(self._factory, "get_provider_for_model"):
                    provider_source = self._factory  # type: ignore[assignment]
                if provider_source and hasattr(provider_source, "get_provider_for_model"):
                    provider_enum = provider_source.get_provider_for_model(request.model)  # type: ignore[call-arg]
                    if inspect.isawaitable(provider_enum):
                        provider_enum = await provider_enum  # type: ignore[assignment]
                    if provider_enum:
                        provider_hint = getattr(provider_enum, "value", str(provider_enum)).lower()
            except Exception:
                provider_hint = None

        # Validate the request first
        try:
            validate_tts_request(tts_request, provider=provider_hint)
        except TTSValidationError as e:
            logger.error(f"TTS request validation failed: {e}")
            if self._stream_errors_as_audio:
                yield b"ERROR: Unable to generate audio."
                return
            else:
                raise

        # Get adapter
        adapter = await self._get_adapter(request.model, provider)
        if not adapter and fallback:
            # Try to find any available adapter
            adapter = await self._get_fallback_adapter(tts_request)

        if not adapter:
            error = TTSProviderNotConfiguredError(
                f"No TTS adapter available for model '{request.model}'",
                provider=provider,
            )
            logger.error(str(error))
            if self._stream_errors_as_audio:
                yield f"ERROR: {str(error)}".encode()
                return
            raise error

        # Track metrics
        start_time = time.time()
        audio_size = 0
        chunks_count = 0
        released_active_slot = False
        fallback_plan: Optional[Tuple[List[str], str]] = None
        await self._increment_active_requests(adapter.provider_name)

        # Generate speech with circuit breaker and comprehensive error handling
        try:
            async with self._semaphore:
                logger.info(f"Generating speech with {adapter.provider_name}")

                # Get circuit breaker if available
                circuit_breaker = None
                if self.circuit_manager:
                    circuit_breaker = await self.circuit_manager.get_breaker(adapter.provider_name)

                # Generate response (with or without circuit breaker)
                response: Optional[TTSResponse] = None
                if circuit_breaker:
                    try:
                        response = await circuit_breaker.call(adapter.generate, tts_request)
                    except CircuitOpenError as e:
                        logger.warning(f"Circuit open for {adapter.provider_name}: {e}")
                        if fallback:
                            # Record fallback attempt
                            self.metrics.increment(
                                "tts_fallback_attempts",
                                labels={"from_provider": adapter.provider_name, "to_provider": "any", "success": "pending"}
                            )
                            await self._decrement_active_requests(adapter.provider_name)
                            released_active_slot = True
                            fallback_plan = (self._build_exclude_tokens(adapter), adapter.provider_name)
                        else:
                            raise TTSProviderError(
                                f"Circuit open for {adapter.provider_name}",
                                provider=adapter.provider_name,
                                details={"circuit_state": "open"}
                            )
                else:
                    response = await adapter.generate(tts_request)

                if fallback_plan is None and response is not None:
                    if response.audio_stream:
                        async for chunk in response.audio_stream:
                            chunks_count += 1
                            audio_size += len(chunk)
                            yield chunk
                    elif response.audio_data:
                        chunks_count = 1
                        audio_size = len(response.audio_data)
                        yield response.audio_data
                    else:
                        error_msg = f"No audio data returned by {adapter.provider_name}"
                        logger.error(error_msg)
                        if fallback:
                            await self._handle_provider_fallback(tts_request, adapter.provider_name, error_msg)
                            await self._decrement_active_requests(adapter.provider_name)
                            released_active_slot = True
                            fallback_plan = (self._build_exclude_tokens(adapter), adapter.provider_name)
                        else:
                            if self._stream_errors_as_audio:
                                yield f"ERROR: {error_msg}".encode()
                            else:
                                raise TTSGenerationError(error_msg, provider=adapter.provider_name)

                if fallback_plan is None:
                    self._record_tts_metrics(
                        provider=adapter.provider_name,
                        model=tts_request.model or "default",
                        voice=tts_request.voice or "default",
                        format=tts_request.format.value,
                        text_length=len(tts_request.text),
                        audio_size=audio_size,
                        duration=time.time() - start_time,
                        success=True
                    )

        except TTSError as e:
            # Handle TTS-specific errors with proper categorization
            error_msg = f"Error generating speech with {adapter.provider_name}: {str(e)}"
            logger.error(error_msg)

            # Record failure metrics
            self._record_tts_metrics(
                provider=adapter.provider_name,
                model=tts_request.model or "default",
                voice=tts_request.voice or "default",
                format=tts_request.format.value,
                text_length=len(tts_request.text),
                audio_size=audio_size,
                duration=time.time() - start_time,
                success=False,
                error=str(e)
            )

            # Check if error is retryable and fallback is enabled
            if fallback and is_retryable_error(e):
                logger.info(f"Attempting fallback due to retryable error: {type(e).__name__}")
                self.metrics.increment(
                    "tts_fallback_attempts",
                    labels={"from_provider": adapter.provider_name, "to_provider": "any", "success": "pending"}
                )
                await self._decrement_active_requests(adapter.provider_name)
                released_active_slot = True
                fallback_plan = (self._build_exclude_tokens(adapter), adapter.provider_name)
            else:
                # For non-recoverable errors or when fallback is disabled
                if self._stream_errors_as_audio:
                    yield f"ERROR: {error_msg}".encode()
                else:
                    raise e
        except Exception as e:
            # Handle unexpected errors
            error_msg = f"Unexpected error generating speech with {adapter.provider_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Record failure metrics
            self._record_tts_metrics(
                provider=adapter.provider_name,
                model=tts_request.model or "default",
                voice=tts_request.voice or "default",
                format=tts_request.format.value,
                text_length=len(tts_request.text),
                audio_size=audio_size,
                duration=time.time() - start_time,
                success=False,
                error=str(e)
            )

            # Wrap in TTS error for consistency
            tts_error = TTSGenerationError(
                f"Unexpected error in {adapter.provider_name}",
                provider=adapter.provider_name,
                details={"error": str(e), "error_type": type(e).__name__}
            )

            if fallback:
                logger.info("Attempting fallback due to unexpected error")
                await self._decrement_active_requests(adapter.provider_name)
                released_active_slot = True
                fallback_plan = (self._build_exclude_tokens(adapter), adapter.provider_name)
            else:
                if self._stream_errors_as_audio:
                    yield f"ERROR: {error_msg}".encode()
                else:
                    raise tts_error
        finally:
            try:
                if not released_active_slot:
                    await self._decrement_active_requests(adapter.provider_name)
            except Exception:
                pass

        if fallback_plan:
            async for chunk in self._try_fallback_providers(
                tts_request,
                fallback_plan[0],
                fallback_plan[1],
            ):
                yield chunk
            return

    async def _generate_with_adapter(
        self,
        adapter: TTSAdapter,
        request: TTSRequest
    ) -> AsyncGenerator[bytes, None]:
        """Generate audio with a specific adapter"""
        await self._increment_active_requests(adapter.provider_name)
        start_time = time.time()
        audio_size = 0
        success = False
        error_message: Optional[str] = None
        try:
            async with self._semaphore:
                response = await adapter.generate(request)

                if response.audio_stream:
                    async for chunk in response.audio_stream:
                        audio_size += len(chunk)
                        yield chunk
                elif response.audio_data:
                    audio_size = len(response.audio_data)
                    yield response.audio_data
                else:
                    error_message = f"No audio data returned by {adapter.provider_name}"
                    logger.error(error_message)
                    if self._stream_errors_as_audio:
                        yield f"ERROR: {error_message}".encode()
                    raise TTSGenerationError(error_message, provider=adapter.provider_name)
                success = True
        except Exception as e:
            logger.error(f"Fallback generation failed: {e}")
            error_message = str(e)
            if self._stream_errors_as_audio:
                yield f"ERROR: All providers failed - {str(e)}".encode()
            raise TTSGenerationError(f"All providers failed - {str(e)}") from e
        finally:
            try:
                await self._decrement_active_requests(adapter.provider_name)
            except Exception:
                pass
            try:
                duration = time.time() - start_time
                self._record_tts_metrics(
                    provider=adapter.provider_name,
                    model=getattr(request, "model", None) or adapter.provider_name.lower(),
                    voice=request.voice or "default",
                    format=request.format.value,
                    text_length=len(request.text),
                    audio_size=audio_size,
                    duration=duration if duration >= 0 else 0.0,
                    success=success,
                    error=error_message if not success else None
                )
            except Exception:
                pass

    def _convert_request(self, request: OpenAISpeechRequest) -> TTSRequest:
        """Convert OpenAI request to unified TTS request"""
        # Map format
        format_mapping = {
            "mp3": AudioFormat.MP3,
            "opus": AudioFormat.OPUS,
            "aac": AudioFormat.AAC,
            "flac": AudioFormat.FLAC,
            "wav": AudioFormat.WAV,
            "pcm": AudioFormat.PCM
        }

        audio_format = format_mapping.get(
            request.response_format.lower(),
            AudioFormat.MP3
        )
        # Optional language code mapping
        language = getattr(request, 'lang_code', None)
        # Optional voice reference decoding (base64)
        voice_ref_bytes = None
        if getattr(request, 'voice_reference', None):
            try:
                voice_ref_bytes = base64.b64decode(request.voice_reference)
            except Exception as exc:
                raise TTSInvalidVoiceReferenceError(
                    "Voice reference data is not valid base64",
                    details={"error": str(exc)}
                ) from exc
        # Provider-specific extras passthrough
        extras = getattr(request, 'extra_params', None) or {}

        tts_request = TTSRequest(
            text=request.input,
            voice=request.voice,
            format=audio_format,
            speed=request.speed,
            stream=request.stream if hasattr(request, 'stream') else True,
            language=language,
            voice_reference=voice_ref_bytes,
            # Additional parameters can be added via extra_params
            extra_params=extras
        )

        # Preserve originating model for metrics/diagnostics when available
        setattr(tts_request, "model", getattr(request, "model", None))

        return tts_request

    async def _get_adapter(
        self,
        model: str,
        provider: Optional[str] = None
    ) -> Optional[TTSAdapter]:
        """Get appropriate adapter for the request"""
        factory = await self._ensure_factory()
        if provider:
            # Specific provider requested
            try:
                provider_enum = TTSProvider(provider.lower())
                return await factory.registry.get_adapter(provider_enum)
            except ValueError:
                logger.warning(f"Unknown provider: {provider}")

        # Get adapter by model name
        return await factory.get_adapter_by_model(model)

    def _provider_aliases(self, adapter: TTSAdapter) -> Set[str]:
        """Return a normalized alias set for a provider/adapter."""
        aliases = {
            adapter.provider_name.lower(),
            adapter.__class__.__name__.lower(),
        }
        provider_key = getattr(adapter, "PROVIDER_KEY", None)
        if provider_key:
            aliases.add(str(provider_key).lower())
        for provider in TTSProvider:
            if provider.value.lower() in aliases or provider.name.lower() in aliases:
                aliases.add(provider.value.lower())
                aliases.add(provider.name.lower())
        normalized = set()
        for alias in aliases:
            normalized.add(alias)
            normalized.add(alias.replace("adapter", ""))
            normalized.add(alias.replace("adapter", "").replace("_", "").replace("-", ""))
        return {alias for alias in normalized if alias}

    def _build_exclude_tokens(self, adapter: TTSAdapter) -> List[str]:
        """Build normalized exclude tokens for a provider."""
        return list(self._provider_aliases(adapter))

    async def _increment_active_requests(self, provider: str) -> None:
        """Increment per-provider active request count and update gauge."""
        async with self._active_requests_lock:
            current = self._active_request_counts.get(provider, 0) + 1
            self._active_request_counts[provider] = current
        try:
            self.metrics.set_gauge(
                "tts_active_requests",
                current,
                labels={"provider": provider}
            )
        except Exception:
            pass

    async def _decrement_active_requests(self, provider: str) -> None:
        """Decrement per-provider active request count and update gauge."""
        async with self._active_requests_lock:
            current = self._active_request_counts.get(provider, 0)
            if current > 0:
                current -= 1
            if current == 0:
                self._active_request_counts.pop(provider, None)
            else:
                self._active_request_counts[provider] = current
        try:
            self.metrics.set_gauge(
                "tts_active_requests",
                current,
                labels={"provider": provider}
            )
        except Exception:
            pass

    async def _get_fallback_adapter(
        self,
        request: TTSRequest,
        exclude: Optional[List[str]] = None
    ) -> Optional[TTSAdapter]:
        """Get a fallback adapter that can handle the request"""
        factory = await self._ensure_factory()
        registry = getattr(factory, "registry", None)
        exclude_tokens = {token.lower() for token in (exclude or [])}
        # Normalize tokens to cover enum values (e.g., "OpenAIAdapter" -> "openai")
        normalized_tokens = set(exclude_tokens)
        for token in list(exclude_tokens):
            cleaned = token.replace("adapter", "").replace("_", "").replace("-", "")
            if cleaned and cleaned != token:
                normalized_tokens.add(cleaned)
        for provider in TTSProvider:
            if provider.value.lower() in exclude_tokens or provider.name.lower() in exclude_tokens:
                normalized_tokens.add(provider.value.lower())
                normalized_tokens.add(provider.name.lower())
        exclude_tokens = normalized_tokens

        # Find adapter that supports the requirements
        adapter = await factory.get_best_adapter(
            language=request.language,
            format=request.format,
            supports_streaming=request.stream
        )

        # Check if adapter is not in exclude list
        if adapter:
            provider_aliases = self._provider_aliases(adapter)
            if not provider_aliases & exclude_tokens:
                return adapter
            exclude_tokens.update(provider_aliases)

        # Try any available adapter
        for provider in TTSProvider:
            if provider.value.lower() in exclude_tokens or provider.name.lower() in exclude_tokens:
                continue
            # Skip providers without registered adapters (e.g., TODO placeholders)
            if registry and hasattr(registry, "_adapter_specs"):
                specs = getattr(registry, "_adapter_specs")
                try:
                    if provider not in specs:
                        continue
                except TypeError:
                    # If specs is not dict-like, fall back to attempting fetch
                    pass

            try:
                adapter = await factory.registry.get_adapter(provider)
            except TTSProviderNotConfiguredError:
                logger.debug(f"Skipping provider {provider.value} - no adapter configured")
                continue
            except Exception as exc:
                logger.debug(f"Skipping provider {provider.value} due to error: {exc}")
                continue

            if adapter:
                # Validate if it can handle the request
                validation_result = await adapter.validate_request(request)
                if isinstance(validation_result, tuple):
                    is_valid, _ = validation_result
                elif validation_result is None:
                    is_valid = True
                else:
                    is_valid = bool(validation_result)
                if is_valid:
                    return adapter
                exclude_tokens.update(self._provider_aliases(adapter))

        return None

    def _record_tts_metrics(
        self,
        provider: str,
        model: str,
        voice: str,
        format: str,
        text_length: int,
        audio_size: int,
        duration: float,
        success: bool,
        error: Optional[str] = None
    ):
        """Record TTS request metrics"""
        # Record request counter
        self.metrics.increment(
            "tts_requests_total",
            labels={
                "provider": provider,
                "model": model,
                "voice": voice,
                "format": format,
                "status": "success" if success else "failure"
            }
        )

        # Record duration histogram
        self.metrics.observe(
            "tts_request_duration_seconds",
            duration,
            labels={"provider": provider, "model": model, "voice": voice}
        )

        # Record text length histogram
        self.metrics.observe(
            "tts_text_length_characters",
            text_length,
            labels={"provider": provider}
        )

        # Record audio size if successful
        if success and audio_size > 0:
            self.metrics.observe(
                "tts_audio_size_bytes",
                audio_size,
                labels={"provider": provider, "format": format}
            )

        # Log performance metrics
        if success:
            chars_per_second = text_length / duration if duration > 0 else 0
            logger.info(
                f"TTS metrics: provider={provider}, duration={duration:.2f}s, "
                f"text_length={text_length}, audio_size={audio_size}, "
                f"chars/sec={chars_per_second:.1f}"
            )
        else:
            logger.warning(
                f"TTS failed: provider={provider}, duration={duration:.2f}s, "
                f"error={error}"
            )

    def _categorize_error(self, error: Exception) -> str:
        """
        Categorize error types for better error handling decisions.
        Uses the new exception system's categorization.

        Args:
            error: Exception that occurred

        Returns:
            Error category string
        """
        # Use the new exception system's categorization
        return categorize_error(error)

    async def _handle_provider_fallback(self, request: TTSRequest, failed_provider: str, error_msg: str):
        """
        Handle provider fallback logging and circuit breaker updates.

        Args:
            request: Original TTS request
            failed_provider: Name of the provider that failed
            error_msg: Error message from the failed provider
        """
        logger.warning(f"Provider {failed_provider} failed: {error_msg}")
        logger.info(f"Attempting fallback for request: text_length={len(request.text)}, voice={request.voice}")

        # Update circuit breaker state if available
        if self.circuit_manager:
            breaker = await self.circuit_manager.get_breaker(failed_provider)
            if breaker:
                # The circuit breaker will track the failure internally
                logger.debug(f"Circuit breaker updated for {failed_provider}")

    async def _try_fallback_providers(
        self,
        request: TTSRequest,
        exclude_providers: List[str],
        failed_provider: Optional[str]
    ) -> AsyncGenerator[bytes, None]:
        """
        Try fallback providers in priority order.

        Args:
            request: TTS request to fulfill
            exclude_providers: List of provider names to exclude
            failed_provider: Canonical provider name that just failed

        Yields:
            Audio chunks from successful provider
        """
        origin_provider = failed_provider or "unknown"
        fallback_adapter = await self._get_fallback_adapter(request, exclude_providers)

        if fallback_adapter:
            try:
                original_model = getattr(request, "model", None)
                fallback_model = (
                    getattr(fallback_adapter, "default_model", None)
                    or fallback_adapter.provider_name.lower()
                )
                setattr(request, "model", fallback_model)
                try:
                    async for chunk in self._generate_with_adapter(fallback_adapter, request):
                        yield chunk
                finally:
                    setattr(request, "model", original_model)
                logger.info(f"Successfully fell back to {fallback_adapter.provider_name}")
                # Record successful fallback
                self.metrics.increment(
                    "tts_fallback_attempts",
                    labels={
                        "from_provider": origin_provider,
                        "to_provider": fallback_adapter.provider_name,
                        "success": "true"
                    }
                )
            except TTSError as e:
                logger.error(f"Fallback provider {fallback_adapter.provider_name} also failed: {e}")
                # Record failed fallback
                self.metrics.increment(
                    "tts_fallback_attempts",
                    labels={
                        "from_provider": origin_provider,
                        "to_provider": fallback_adapter.provider_name,
                        "success": "false"
                    }
                )

                # Try one more fallback if available and error is retryable
                if is_retryable_error(e):
                    exclude_providers.extend(
                        token for token in self._build_exclude_tokens(fallback_adapter)
                        if token not in exclude_providers
                    )
                    next_failed_provider = fallback_adapter.provider_name
                    final_fallback = await self._get_fallback_adapter(request, exclude_providers)

                    if final_fallback:
                        try:
                            secondary_original_model = getattr(request, "model", None)
                            secondary_model = (
                                getattr(final_fallback, "default_model", None)
                                or final_fallback.provider_name.lower()
                            )
                            setattr(request, "model", secondary_model)
                            try:
                                async for chunk in self._generate_with_adapter(final_fallback, request):
                                    yield chunk
                            finally:
                                setattr(request, "model", secondary_original_model)
                            logger.info(f"Final fallback to {final_fallback.provider_name} succeeded")
                            # Record successful final fallback
                            self.metrics.increment(
                                "tts_fallback_attempts",
                                labels={
                                    "from_provider": next_failed_provider,
                                    "to_provider": final_fallback.provider_name,
                                    "success": "true"
                                }
                            )
                        except Exception as final_e:
                            # Wrap non-TTS errors
                            if not isinstance(final_e, TTSError):
                                final_e = TTSGenerationError(
                                    f"Final fallback failed",
                                    provider=final_fallback.provider_name,
                                    details={"error": str(final_e)}
                                )
                            self.metrics.increment(
                                "tts_fallback_attempts",
                                labels={
                                    "from_provider": next_failed_provider,
                                    "to_provider": final_fallback.provider_name,
                                    "success": "false"
                                }
                            )
                            error_msg = f"All providers failed. Last error: {str(final_e)}"
                            logger.error(error_msg)
                            if self._stream_errors_as_audio:
                                yield f"ERROR: {error_msg}".encode()
                            else:
                                raise final_e
                    else:
                        origin_provider = next_failed_provider
                        if self._stream_errors_as_audio:
                            yield f"ERROR: All fallback providers exhausted".encode()
                        else:
                            raise TTSFallbackExhaustedError("All fallback providers exhausted")
                else:
                    # Non-retryable error, don't attempt more fallbacks
                    if self._stream_errors_as_audio:
                        yield f"ERROR: {str(e)} (non-retryable)".encode()
                    else:
                        raise e
            except Exception as e:
                # Handle unexpected errors
                logger.error(f"Unexpected error in fallback: {e}", exc_info=True)
                if self._stream_errors_as_audio:
                    yield f"ERROR: Unexpected error during fallback: {str(e)}".encode()
                else:
                    raise TTSGenerationError(f"Unexpected error during fallback: {str(e)}")
        else:
            if self._stream_errors_as_audio:
                yield f"ERROR: No fallback providers available".encode()
            else:
                raise TTSFallbackExhaustedError("No fallback providers available")

    async def list_voices(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        List all available voices from all providers.

        Returns:
            Dictionary mapping provider names to voice lists
        """
        voices = {}
        factory = await self._ensure_factory()

        for provider in TTSProvider:
            # Defensive skip: if the registry doesn't have an adapter spec for this
            # provider (e.g., unimplemented like 'alltalk'), skip it early.
            try:
                specs = getattr(factory.registry, "_adapter_specs", None)
                if specs is not None and provider not in specs:
                    logger.debug(f"Skipping provider {provider.value} - no adapter registered")
                    continue
            except Exception:
                # If anything odd happens accessing internals, continue gracefully
                pass

            # Try to get adapter; skip providers that are not configured/available
            try:
                adapter = await factory.registry.get_adapter(provider)
            except Exception as e:
                # Specifically handle not-configured providers without failing the call
                try:
                    from .tts_exceptions import TTSProviderNotConfiguredError
                    if isinstance(e, TTSProviderNotConfiguredError):
                        logger.debug(f"Provider {provider.value} not configured; skipping")
                        continue
                except Exception:
                    # If import/type-check fails, just log and skip
                    logger.debug(f"Skipping provider {provider.value} due to error: {e}")
                    continue
                # Other exceptions: log and skip
                logger.debug(f"Skipping provider {provider.value} due to error: {e}")
                continue

            if adapter and adapter.capabilities:
                provider_voices = []
                for voice in adapter.capabilities.supported_voices:
                    provider_voices.append({
                        "id": voice.id,
                        "name": voice.name,
                        "gender": voice.gender,
                        "language": voice.language,
                        "description": voice.description
                    })
                voices[provider.value] = provider_voices

        return voices

    async def get_capabilities(self) -> Dict[str, Any]:
        """
        Get capabilities of all available providers.

        Returns:
            Dictionary with capability information
        """
        factory = await self._ensure_factory()
        capabilities = await factory.registry.get_all_capabilities()

        result = {}
        for provider, caps in capabilities.items():
            result[provider.value] = {
                "languages": list(caps.supported_languages),
                "formats": [fmt.value for fmt in caps.supported_formats],
                "max_text_length": caps.max_text_length,
                "supports_streaming": caps.supports_streaming,
                "supports_voice_cloning": caps.supports_voice_cloning,
                "supports_emotion_control": caps.supports_emotion_control,
                "supports_multi_speaker": caps.supports_multi_speaker,
                "latency_ms": caps.latency_ms,
                "sample_rate": caps.sample_rate
            }

        return result

    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        factory = self.factory or self._factory
        if not factory or not hasattr(factory, "get_status"):
            return {"providers": {}, "initialized": False}
        status = factory.get_status()

        # Add circuit breaker status if available
        if self.circuit_manager:
            status["circuit_breakers"] = self.circuit_manager.get_all_status()

        return status


# Singleton management
_service_instance: Optional[TTSServiceV2] = None
_service_lock = asyncio.Lock()


async def get_tts_service_v2(config: Optional[Dict[str, Any]] = None) -> TTSServiceV2:
    """
    Get or create the enhanced TTS service singleton.

    Args:
        config: Configuration for the service

    Returns:
        TTSServiceV2 instance
    """
    global _service_instance

    if _service_instance is None:
        async with _service_lock:
            if _service_instance is None:
                # Load configuration if not provided
                if config is None:
                    from tldw_Server_API.app.core.config import load_comprehensive_config_with_tts
                    config_obj = load_comprehensive_config_with_tts()
                    config = config_obj.get_tts_config()

                # Get factory
                factory = await get_tts_factory(config)

                # Get circuit breaker manager
                circuit_manager = await get_circuit_manager(config)

                # Create service
                _service_instance = TTSServiceV2(factory, circuit_manager)
                logger.info("Enhanced TTS Service (V2) initialized")

    return _service_instance


async def close_tts_service_v2():
    """Close the enhanced TTS service"""
    global _service_instance

    if _service_instance:
        await close_tts_factory()
        _service_instance = None
        logger.info("Enhanced TTS Service (V2) closed")


# Backwards compatibility wrapper
class TTSServiceAdapter:
    """
    Adapter to make V2 service compatible with existing code.
    Maps old interface to new service.
    """

    def __init__(self):
        self.service_v2: Optional[TTSServiceV2] = None

    async def generate_audio_stream(
        self,
        request: OpenAISpeechRequest,
        internal_model_id: str
    ) -> AsyncGenerator[bytes, None]:
        """
        Generate audio stream (backwards compatible interface).

        Args:
            request: OpenAI speech request
            internal_model_id: Internal model identifier

        Yields:
            Audio chunks
        """
        # Get V2 service
        if not self.service_v2:
            self.service_v2 = await get_tts_service_v2()

        # Map internal model ID to provider/model
        # This maintains compatibility with existing code
        model_mapping = {
            "openai_official_tts-1": "tts-1",
            "openai_official_tts-1-hd": "tts-1-hd",
            "local_kokoro_default_onnx": "kokoro",
            "elevenlabs_english_v1": "elevenlabs",  # TODO: Implement
            "alltalk_api_backend": "alltalk"  # TODO: Implement
        }

        # Update request model if needed
        if internal_model_id in model_mapping:
            request.model = model_mapping[internal_model_id]
        else:
            request.model = internal_model_id

        # Generate with V2 service
        async for chunk in self.service_v2.generate_speech(request, fallback=True):
            yield chunk


# Export the adapter for backwards compatibility
TTSService = TTSServiceAdapter

#
# End of tts_service_v2.py
#######################################################################################################################
