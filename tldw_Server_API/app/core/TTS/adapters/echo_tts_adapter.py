# echo_tts_adapter.py
# Description: Echo-TTS adapter implementation (CUDA-only, voice reference required)
#
# Imports
import asyncio
import hashlib
import importlib
import sys
import tempfile
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple
#
# Third-party Imports
import numpy as np
from loguru import logger
#
# Local Imports
from .base import (
    AudioFormat,
    ProviderStatus,
    TTSCapabilities,
    TTSAdapter,
    TTSRequest,
    TTSResponse,
)
from ..tts_exceptions import (
    TTSGenerationError,
    TTSInvalidVoiceReferenceError,
    TTSModelLoadError,
    TTSProviderInitializationError,
    TTSProviderNotConfiguredError,
    TTSUnsupportedFormatError,
    TTSValidationError,
)
from ..tts_validation import validate_tts_request
from ..tts_resource_manager import get_resource_manager
from ..utils import parse_bool
from ..streaming_audio_writer import AudioNormalizer, StreamingAudioWriter
#
#######################################################################################################################
#
# Echo-TTS Adapter


class EchoTTSAdapter(TTSAdapter):
    """Adapter for Echo-TTS (CUDA-only, speaker reference required)."""

    PROVIDER_KEY = "echo_tts"
    SUPPORTED_FORMATS: Set[AudioFormat] = {
        AudioFormat.MP3,
        AudioFormat.WAV,
        AudioFormat.FLAC,
        AudioFormat.OPUS,
        AudioFormat.AAC,
        AudioFormat.PCM,
    }
    SUPPORTED_LANGUAGES = {"en"}
    DEFAULT_SAMPLE_RATE = 44100
    MAX_TEXT_LENGTH = 768
    DEFAULT_BLOCK_SIZE = 160

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        cfg = config or {}

        extra_cfg = cfg.get("extra_params") if isinstance(cfg.get("extra_params"), dict) else {}

        self.model_repo = (
            cfg.get("echo_tts_model")
            or cfg.get("model")
            or extra_cfg.get("model")
            or "jordand/echo-tts-base"
        )
        self.fish_ae_repo = (
            cfg.get("echo_tts_fish_ae_repo")
            or cfg.get("fish_ae_repo")
            or extra_cfg.get("fish_ae_repo")
            or "jordand/fish-s1-dac-min"
        )
        self.pca_state_file = (
            cfg.get("echo_tts_pca_state_file")
            or cfg.get("pca_state_file")
            or extra_cfg.get("pca_state_file")
            or "pca_state.safetensors"
        )
        self.module_path = Path(
            cfg.get("echo_tts_module_path")
            or cfg.get("module_path")
            or "../echo-tts"
        ).expanduser()

        self.device_pref = str(
            cfg.get("echo_tts_device")
            or cfg.get("device")
            or extra_cfg.get("device")
            or "auto"
        ).lower()
        self.sample_rate = int(
            cfg.get("echo_tts_sample_rate")
            or cfg.get("sample_rate")
            or extra_cfg.get("sample_rate")
            or self.DEFAULT_SAMPLE_RATE
        )

        self.cache_size = int(
            cfg.get("echo_tts_cache_size")
            or cfg.get("cache_size")
            or extra_cfg.get("cache_size")
            or 8
        )
        self.cache_ttl_sec = float(
            cfg.get("echo_tts_cache_ttl_sec")
            or cfg.get("cache_ttl_sec")
            or extra_cfg.get("cache_ttl_sec")
            or 3600
        )
        self.cache_on_device = parse_bool(
            cfg.get("echo_tts_cache_on_device")
            or cfg.get("cache_on_device")
            or extra_cfg.get("cache_on_device"),
            default=False,
        )

        self.max_reference_seconds = int(
            cfg.get("echo_tts_max_reference_seconds")
            or cfg.get("max_reference_seconds")
            or extra_cfg.get("max_reference_seconds")
            or 300
        )

        self._model = None
        self._fish_ae = None
        self._pca_state = None
        self._echo_modules_loaded = False
        self._model_lock = asyncio.Lock()
        self._cache_lock = asyncio.Lock()
        self._speaker_cache: "OrderedDict[str, Tuple[float, Any, Any]]" = OrderedDict()

        self._echo_inference = None
        self._echo_blockwise = None

    async def initialize(self) -> bool:
        """Initialize Echo-TTS adapter (verify dependencies and CUDA availability)."""
        try:
            torch = self._import_torch()
            self._resolve_device(torch)
            self._load_echo_modules()
            self._status = ProviderStatus.AVAILABLE
            return True
        except Exception as exc:
            logger.error(f"{self.provider_name}: initialization failed: {exc}")
            self._status = ProviderStatus.ERROR
            if isinstance(exc, TTSProviderInitializationError):
                raise
            return False

    async def get_capabilities(self) -> TTSCapabilities:
        supports_streaming = True
        if not self._echo_modules_loaded:
            # Best effort: capabilities should still list streaming support if module exists.
            try:
                self._load_echo_modules()
            except Exception:
                supports_streaming = False
        return TTSCapabilities(
            provider_name="EchoTTS",
            supported_languages=self.SUPPORTED_LANGUAGES,
            supported_voices=[],
            supported_formats=self.SUPPORTED_FORMATS,
            max_text_length=self.MAX_TEXT_LENGTH,
            supports_streaming=supports_streaming,
            supports_voice_cloning=True,
            supports_emotion_control=False,
            supports_speech_rate=False,
            supports_pitch_control=False,
            supports_volume_control=False,
            supports_ssml=False,
            supports_phonemes=False,
            supports_multi_speaker=False,
            supports_background_audio=False,
            latency_ms=1500,
            sample_rate=self.sample_rate,
            default_format=AudioFormat.WAV,
        )

    async def generate(self, request: TTSRequest) -> TTSResponse:
        if not await self.ensure_initialized():
            raise TTSProviderNotConfiguredError(
                "Echo-TTS adapter not initialized",
                provider=self.PROVIDER_KEY,
            )

        if request.format not in self.SUPPORTED_FORMATS:
            raise TTSUnsupportedFormatError(
                f"Format {request.format.value} not supported by Echo-TTS",
                provider=self.PROVIDER_KEY,
            )

        try:
            validate_tts_request(request, provider=self.PROVIDER_KEY)
        except TTSValidationError:
            raise
        except Exception as exc:
            raise TTSValidationError(
                f"Validation failed for Echo-TTS request: {exc}",
                provider=self.PROVIDER_KEY,
            ) from exc

        if not request.voice_reference:
            raise TTSInvalidVoiceReferenceError(
                "Echo-TTS requires voice_reference audio bytes",
                provider=self.PROVIDER_KEY,
            )

        await self._ensure_models_loaded()

        extras = request.extra_params or {}
        if not isinstance(extras, dict):
            extras = {}

        voice_bytes = self._extract_voice_reference(request.voice_reference)
        voice_bytes = await self._prepare_voice_reference(voice_bytes, extras)

        cache_key = self._cache_key(voice_bytes)
        speaker_latent, speaker_mask = await self._get_cached_speaker_latent(cache_key)
        if speaker_latent is None or speaker_mask is None:
            speaker_latent, speaker_mask = await self._compute_speaker_latent(voice_bytes)
            await self._store_speaker_latent(cache_key, speaker_latent, speaker_mask)

        torch = self._import_torch()
        inference = self._echo_inference
        if inference is None:
            raise TTSModelLoadError(
                "Echo-TTS inference module not loaded",
                provider=self.PROVIDER_KEY,
            )

        try:
            text_input_ids, text_mask, normalized_text_value = self._prepare_text_inputs(
                request,
                extras,
                inference,
            )
            speaker_latent = speaker_latent.to(self._model.device)
            speaker_mask = speaker_mask.to(self._model.device)

            if request.stream:
                audio_stream = self._stream_audio(
                    request=request,
                    extras=extras,
                    inference=inference,
                    text_input_ids=text_input_ids,
                    text_mask=text_mask,
                    speaker_latent=speaker_latent,
                    speaker_mask=speaker_mask,
                )
                return TTSResponse(
                    audio_stream=audio_stream,
                    format=request.format,
                    sample_rate=self.sample_rate,
                    channels=1,
                    text_processed=normalized_text_value,
                    voice_used=request.voice,
                    provider=self.PROVIDER_KEY,
                    model=request.model or self.model_repo,
                )

            latent_out = self._run_full_generation(
                inference=inference,
                text_input_ids=text_input_ids,
                text_mask=text_mask,
                speaker_latent=speaker_latent,
                speaker_mask=speaker_mask,
                extras=extras,
            )
            audio_bytes = await self._latent_to_audio_bytes(
                inference=inference,
                latent_out=latent_out,
                request_format=request.format,
            )
            return TTSResponse(
                audio_data=audio_bytes,
                format=request.format,
                sample_rate=self.sample_rate,
                channels=1,
                text_processed=normalized_text_value,
                voice_used=request.voice,
                provider=self.PROVIDER_KEY,
                model=request.model or self.model_repo,
            )
        except Exception as exc:
            logger.error("Echo-TTS generation failed: %s", exc, exc_info=True)
            raise TTSGenerationError(
                "Echo-TTS generation failed",
                provider=self.PROVIDER_KEY,
                details={"error": str(exc)},
            ) from exc

    async def generate_stream(self, request: TTSRequest):
        """Legacy streaming entrypoint used by older tests."""
        if not await self.ensure_initialized():
            raise TTSProviderNotConfiguredError(
                "Echo-TTS adapter not initialized",
                provider=self.PROVIDER_KEY,
            )

        request.stream = True
        response = await self.generate(request)
        if response.audio_stream is None:
            raise TTSGenerationError(
                "Echo-TTS streaming did not return an audio stream",
                provider=self.PROVIDER_KEY,
            )
        async for chunk in response.audio_stream:
            yield chunk

    async def _cleanup_resources(self) -> None:
        self._model = None
        self._fish_ae = None
        self._pca_state = None
        self._speaker_cache.clear()

    def _import_torch(self):
        try:
            import torch  # type: ignore
            return torch
        except Exception as exc:
            raise TTSModelLoadError(
                "PyTorch is required for Echo-TTS",
                provider=self.PROVIDER_KEY,
                details={"error": str(exc)},
            ) from exc

    def _resolve_device(self, torch_module) -> None:
        if self.device_pref == "auto":
            device = "cuda"
        elif self.device_pref == "cuda":
            device = self.device_pref
        elif self.device_pref == "cpu":
            raise TTSProviderInitializationError(
                "Echo-TTS is CUDA-only; device 'cpu' is not supported",
                provider=self.PROVIDER_KEY,
                details={"valid_devices": ["auto", "cuda"]},
            )
        else:
            raise TTSProviderInitializationError(
                f"Unsupported device '{self.device_pref}' for Echo-TTS",
                provider=self.PROVIDER_KEY,
                details={"valid_devices": ["auto", "cuda"]},
            )

        if device == "cuda" and not torch_module.cuda.is_available():
            raise TTSProviderInitializationError(
                "CUDA is required for Echo-TTS but is not available",
                provider=self.PROVIDER_KEY,
            )

        self.device = device

    def _load_echo_modules(self) -> None:
        if self._echo_modules_loaded:
            return
        try:
            inference = importlib.import_module("inference")
            blockwise = importlib.import_module("inference_blockwise")
        except Exception:
            module_dir = self.module_path
            if not module_dir.exists():
                raise TTSModelLoadError(
                    "Echo-TTS module path not found",
                    provider=self.PROVIDER_KEY,
                    details={"module_path": str(module_dir)},
                )
            module_path_str = str(module_dir)
            if module_path_str not in sys.path:
                sys.path.insert(0, module_path_str)
            inference = importlib.import_module("inference")
            blockwise = importlib.import_module("inference_blockwise")

        self._echo_inference = inference
        self._echo_blockwise = blockwise
        self._echo_modules_loaded = True

    async def _ensure_models_loaded(self) -> None:
        if self._model is not None and self._fish_ae is not None and self._pca_state is not None:
            return
        async with self._model_lock:
            if self._model is not None and self._fish_ae is not None and self._pca_state is not None:
                return

            self._load_echo_modules()
            inference = self._echo_inference
            if inference is None:
                raise TTSModelLoadError(
                    "Echo-TTS inference module not loaded",
                    provider=self.PROVIDER_KEY,
                )

            torch = self._import_torch()

            model_dtype = torch.bfloat16
            try:
                if parse_bool(self.config.get("echo_tts_use_fp16"), default=False):
                    model_dtype = torch.float16
                elif parse_bool(self.config.get("echo_tts_use_fp32"), default=False):
                    model_dtype = torch.float32
            except Exception:
                model_dtype = torch.bfloat16

            self._model = await asyncio.to_thread(
                inference.load_model_from_hf,
                repo_id=self.model_repo,
                device=self.device,
                dtype=model_dtype,
                compile=False,
                delete_blockwise_modules=True,
            )
            self._fish_ae = await asyncio.to_thread(
                inference.load_fish_ae_from_hf,
                repo_id=self.fish_ae_repo,
                device=self.device,
                dtype=torch.float32,
                compile=False,
            )
            self._pca_state = await asyncio.to_thread(
                inference.load_pca_state_from_hf,
                repo_id=self.model_repo,
                device=self.device,
                filename=self.pca_state_file,
            )

            # Register model for memory monitoring (best-effort)
            try:
                resource_manager = await get_resource_manager()
                resource_manager.memory_monitor.register_model(
                    self._model,
                    cleanup_callback=self._cleanup_resources,
                )
            except Exception:
                pass

    def _cache_key(self, voice_bytes: bytes) -> str:
        digest = hashlib.sha256(voice_bytes).hexdigest()
        return f"{digest}:{self.model_repo}:{self.fish_ae_repo}:{self.device}:{self.sample_rate}"

    async def _get_cached_speaker_latent(self, cache_key: str) -> Tuple[Optional[Any], Optional[Any]]:
        if self.cache_size <= 0:
            return None, None
        async with self._cache_lock:
            self._prune_cache_locked()
            entry = self._speaker_cache.get(cache_key)
            if not entry:
                return None, None
            timestamp, latent, mask = entry
            self._speaker_cache.move_to_end(cache_key)
            if not self.cache_on_device:
                latent = latent.to(self.device)
                mask = mask.to(self.device)
            return latent, mask

    async def _store_speaker_latent(self, cache_key: str, latent: Any, mask: Any) -> None:
        if self.cache_size <= 0:
            return
        try:
            resource_manager = await get_resource_manager()
            if resource_manager.memory_monitor.is_memory_critical():
                async with self._cache_lock:
                    self._speaker_cache.clear()
                return
        except Exception:
            pass

        if not self.cache_on_device:
            latent = latent.detach().cpu()
            mask = mask.detach().cpu()
        else:
            latent = latent.detach()
            mask = mask.detach()

        async with self._cache_lock:
            self._speaker_cache[cache_key] = (time.time(), latent, mask)
            self._speaker_cache.move_to_end(cache_key)
            self._prune_cache_locked()

    def _prune_cache_locked(self) -> None:
        if self.cache_ttl_sec > 0:
            now = time.time()
            expired = [key for key, (ts, _, _) in self._speaker_cache.items() if now - ts > self.cache_ttl_sec]
            for key in expired:
                self._speaker_cache.pop(key, None)
        while len(self._speaker_cache) > self.cache_size:
            self._speaker_cache.popitem(last=False)

    async def _compute_speaker_latent(self, voice_bytes: bytes):
        inference = self._echo_inference
        if inference is None:
            raise TTSModelLoadError(
                "Echo-TTS inference module not loaded",
                provider=self.PROVIDER_KEY,
            )
        voice_path = self._write_temp_audio(voice_bytes)
        try:
            speaker_audio = await asyncio.to_thread(
                inference.load_audio,
                voice_path,
                self.max_reference_seconds,
            )
        finally:
            Path(voice_path).unlink(missing_ok=True)

        speaker_audio = speaker_audio.to(device=self._model.device, dtype=self._fish_ae.dtype)
        speaker_latent, speaker_mask = inference.get_speaker_latent_and_mask(
            self._fish_ae,
            self._pca_state,
            speaker_audio,
        )
        return speaker_latent, speaker_mask

    def _prepare_text_inputs(
        self,
        request: TTSRequest,
        extras: Dict[str, Any],
        inference: Any,
    ) -> Tuple[Any, Any, str]:
        normalize_text = self._coerce_bool(extras.get("normalize_text"), True)
        text_input_ids, text_mask, normalized_text = inference.get_text_input_ids_and_mask(
            [request.text],
            max_length=min(self.MAX_TEXT_LENGTH, 768),
            device=self._model.device,
            normalize=normalize_text,
            return_normalized_text=True,
            pad_to_max=False,
        )
        normalized_text_value = normalized_text[0] if normalized_text else request.text
        return text_input_ids, text_mask, normalized_text_value

    def _run_full_generation(
        self,
        *,
        inference: Any,
        text_input_ids: Any,
        text_mask: Any,
        speaker_latent: Any,
        speaker_mask: Any,
        extras: Dict[str, Any],
    ):
        seq_len = self._resolve_sequence_length(extras)
        rng_seed = self._coerce_int(extras.get("rng_seed"), 0)
        cfg_scale_text = self._coerce_float(extras.get("cfg_scale_text"), 3.0)
        cfg_scale_speaker = self._coerce_float(extras.get("cfg_scale_speaker"), 8.0)
        cfg_min_t = self._coerce_float(extras.get("cfg_min_t"), 0.5)
        cfg_max_t = self._coerce_float(extras.get("cfg_max_t"), 1.0)
        truncation_factor = self._coerce_optional_float(extras.get("truncation_factor"))
        rescale_k = self._coerce_optional_float(extras.get("rescale_k"))
        rescale_sigma = self._coerce_optional_float(extras.get("rescale_sigma"))
        speaker_kv_scale = self._coerce_optional_float(extras.get("speaker_kv_scale"))
        speaker_kv_min_t = self._coerce_optional_float(extras.get("speaker_kv_min_t"))
        speaker_kv_max_layers = self._coerce_optional_int(extras.get("speaker_kv_max_layers"))
        num_steps = self._coerce_int(extras.get("num_steps"), 40)

        return inference.sample_euler_cfg_independent_guidances(
            model=self._model,
            speaker_latent=speaker_latent,
            speaker_mask=speaker_mask,
            text_input_ids=text_input_ids,
            text_mask=text_mask,
            rng_seed=rng_seed,
            num_steps=num_steps,
            cfg_scale_text=cfg_scale_text,
            cfg_scale_speaker=cfg_scale_speaker,
            cfg_min_t=cfg_min_t,
            cfg_max_t=cfg_max_t,
            truncation_factor=truncation_factor,
            rescale_k=rescale_k,
            rescale_sigma=rescale_sigma,
            speaker_kv_scale=speaker_kv_scale,
            speaker_kv_max_layers=speaker_kv_max_layers,
            speaker_kv_min_t=speaker_kv_min_t,
            sequence_length=seq_len,
        )

    async def _latent_to_audio_bytes(
        self,
        *,
        inference: Any,
        latent_out: Any,
        request_format: AudioFormat,
    ) -> bytes:
        audio_out = inference.ae_decode(self._fish_ae, self._pca_state, latent_out)
        audio_out = inference.crop_audio_to_flattening_point(audio_out, latent_out[0])
        audio_np = audio_out[0].detach().cpu().numpy().astype(np.float32)
        return await self.convert_audio_format(
            audio_np,
            source_format=AudioFormat.PCM,
            target_format=request_format,
            sample_rate=self.sample_rate,
        )

    def _stream_audio(
        self,
        *,
        request: TTSRequest,
        extras: Dict[str, Any],
        inference: Any,
        text_input_ids: Any,
        text_mask: Any,
        speaker_latent: Any,
        speaker_mask: Any,
    ):
        blockwise = self._echo_blockwise
        if blockwise is None:
            raise TTSGenerationError(
                "Echo-TTS blockwise module not available for streaming",
                provider=self.PROVIDER_KEY,
            )

        torch = self._import_torch()
        audio_normalizer = AudioNormalizer()
        writer = StreamingAudioWriter(
            format=request.format.value,
            sample_rate=self.sample_rate,
            channels=1,
        )

        seq_len = self._resolve_sequence_length(extras)
        block_size = self.DEFAULT_BLOCK_SIZE
        if block_size <= 0:
            block_size = 160
        block_sizes = []
        remaining = seq_len
        while remaining > 0:
            chunk = min(block_size, remaining)
            block_sizes.append(chunk)
            remaining -= chunk

        rng_seed = self._coerce_int(extras.get("rng_seed"), 0)
        cfg_scale_text = self._coerce_float(extras.get("cfg_scale_text"), 3.0)
        cfg_scale_speaker = self._coerce_float(extras.get("cfg_scale_speaker"), 8.0)
        cfg_min_t = self._coerce_float(extras.get("cfg_min_t"), 0.5)
        cfg_max_t = self._coerce_float(extras.get("cfg_max_t"), 1.0)
        truncation_factor = self._coerce_optional_float(extras.get("truncation_factor"))
        rescale_k = self._coerce_optional_float(extras.get("rescale_k"))
        rescale_sigma = self._coerce_optional_float(extras.get("rescale_sigma"))
        speaker_kv_scale = self._coerce_optional_float(extras.get("speaker_kv_scale"))
        speaker_kv_min_t = self._coerce_optional_float(extras.get("speaker_kv_min_t"))
        speaker_kv_max_layers = self._coerce_optional_int(extras.get("speaker_kv_max_layers"))
        num_steps = self._coerce_int(extras.get("num_steps"), 40)

        async def stream():
            init_scale = 0.999
            device = self._model.device
            dtype = self._model.dtype
            batch_size = text_input_ids.shape[0]

            rng = torch.Generator(device=device).manual_seed(rng_seed)
            t_schedule = torch.linspace(1.0, 0.0, num_steps + 1, device=device) * init_scale

            text_mask_uncond = torch.zeros_like(text_mask)
            speaker_mask_uncond = torch.zeros_like(speaker_mask)

            kv_text_cond = self._model.get_kv_cache_text(text_input_ids, text_mask)
            kv_speaker_cond = self._model.get_kv_cache_speaker(speaker_latent.to(dtype))

            kv_text_full = blockwise._concat_kv_caches(kv_text_cond, kv_text_cond, kv_text_cond)
            kv_speaker_full = blockwise._concat_kv_caches(kv_speaker_cond, kv_speaker_cond, kv_speaker_cond)

            full_text_mask = torch.cat([text_mask, text_mask_uncond, text_mask], dim=0)
            full_speaker_mask = torch.cat([speaker_mask, speaker_mask, speaker_mask_uncond], dim=0)

            prefix_latent = torch.zeros(
                (batch_size, sum(block_sizes), 80),
                device=device,
                dtype=torch.float32,
            )

            start_pos = 0
            for current_block_size in block_sizes:
                if speaker_kv_scale is not None:
                    blockwise._multiply_kv_cache(kv_speaker_cond, speaker_kv_scale, speaker_kv_max_layers)
                    kv_speaker_full = blockwise._concat_kv_caches(
                        kv_speaker_cond, kv_speaker_cond, kv_speaker_cond
                    )

                full_prefix_latent = torch.cat([prefix_latent, prefix_latent, prefix_latent], dim=0)
                kv_latent_full = self._model.get_kv_cache_latent(full_prefix_latent.to(dtype))
                kv_latent_cond = [(k[:batch_size], v[:batch_size]) for k, v in kv_latent_full]

                x_t = torch.randn(
                    (batch_size, current_block_size, 80),
                    device=device,
                    dtype=torch.float32,
                    generator=rng,
                )
                if truncation_factor is not None:
                    x_t = x_t * truncation_factor

                for i in range(num_steps):
                    t, t_next = t_schedule[i], t_schedule[i + 1]
                    has_cfg = ((t >= cfg_min_t) * (t <= cfg_max_t)).item()

                    if has_cfg:
                        v_cond, v_uncond_text, v_uncond_speaker = self._model(
                            x=torch.cat([x_t, x_t, x_t], dim=0).to(dtype),
                            t=(torch.ones((batch_size * 3,), device=device) * t).to(dtype),
                            text_mask=full_text_mask,
                            speaker_mask=full_speaker_mask,
                            start_pos=start_pos,
                            kv_cache_text=kv_text_full,
                            kv_cache_speaker=kv_speaker_full,
                            kv_cache_latent=kv_latent_full,
                        ).float().chunk(3, dim=0)
                        v_pred = (
                            v_cond
                            + cfg_scale_text * (v_cond - v_uncond_text)
                            + cfg_scale_speaker * (v_cond - v_uncond_speaker)
                        )
                    else:
                        v_pred = self._model(
                            x=x_t.to(dtype),
                            t=(torch.ones((batch_size,), device=device) * t).to(dtype),
                            text_mask=text_mask,
                            speaker_mask=speaker_mask,
                            start_pos=start_pos,
                            kv_cache_text=kv_text_cond,
                            kv_cache_speaker=kv_speaker_cond,
                            kv_cache_latent=kv_latent_cond,
                        ).float()

                    if rescale_k is not None and rescale_sigma is not None:
                        v_pred = blockwise._temporal_score_rescale(v_pred, x_t, t, rescale_k, rescale_sigma)

                    if (
                        speaker_kv_scale is not None
                        and speaker_kv_min_t is not None
                        and t_next < speaker_kv_min_t
                        and t >= speaker_kv_min_t
                    ):
                        blockwise._multiply_kv_cache(kv_speaker_cond, 1.0 / speaker_kv_scale, speaker_kv_max_layers)
                        kv_speaker_full = blockwise._concat_kv_caches(
                            kv_speaker_cond, kv_speaker_cond, kv_speaker_cond
                        )

                    x_t = x_t + v_pred * (t_next - t)

                prefix_latent[:, start_pos:start_pos + current_block_size] = x_t

                audio_chunk = inference.ae_decode(self._fish_ae, self._pca_state, x_t)
                audio_np = audio_chunk[0].detach().cpu().numpy().astype(np.float32)
                audio_i16 = audio_normalizer.normalize(audio_np, target_dtype=np.int16)
                data = writer.write_chunk(audio_i16)
                if data:
                    yield data

                start_pos += current_block_size

            final_bytes = writer.write_chunk(finalize=True)
            if final_bytes:
                yield final_bytes

        return stream()

    def _extract_voice_reference(self, voice_reference: Any) -> bytes:
        if voice_reference is None:
            raise TTSInvalidVoiceReferenceError(
                "Echo-TTS requires voice_reference audio bytes",
                provider=self.PROVIDER_KEY,
            )
        if isinstance(voice_reference, (bytes, bytearray)):
            return bytes(voice_reference)
        if isinstance(voice_reference, str):
            try:
                from tldw_Server_API.app.core.TTS.audio_utils import AudioProcessor
                return AudioProcessor().decode_base64_audio(voice_reference)
            except Exception as exc:
                raise TTSInvalidVoiceReferenceError(
                    "Echo-TTS voice_reference is not valid base64",
                    provider=self.PROVIDER_KEY,
                    details={"error": str(exc)},
                ) from exc
        raise TTSInvalidVoiceReferenceError(
            "Echo-TTS voice_reference must be bytes or base64 string",
            provider=self.PROVIDER_KEY,
            details={"type": type(voice_reference).__name__},
        )

    async def _prepare_voice_reference(self, voice_bytes: bytes, extras: Dict[str, Any]) -> bytes:
        validate_ref = self._coerce_bool(extras.get("validate_reference"), True)
        convert_ref = self._coerce_bool(extras.get("convert_reference"), True)

        from tldw_Server_API.app.core.TTS.audio_utils import AudioProcessor

        processor = AudioProcessor()
        if validate_ref:
            is_valid, error_msg, _ = processor.validate_audio(
                voice_bytes,
                provider=self.PROVIDER_KEY,
                check_duration=True,
                check_quality=False,
            )
            if not is_valid:
                raise TTSInvalidVoiceReferenceError(
                    error_msg or "Echo-TTS voice reference validation failed",
                    provider=self.PROVIDER_KEY,
                )

        if convert_ref:
            voice_bytes = await processor.convert_audio_async(
                voice_bytes,
                target_format="wav",
                target_sample_rate=self.sample_rate,
                provider=self.PROVIDER_KEY,
            )

        return voice_bytes

    def _write_temp_audio(self, audio_bytes: bytes) -> str:
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
                prefix="echo_tts_voice_",
            ) as tmp:
                tmp.write(audio_bytes)
                return tmp.name
        except Exception as exc:
            raise TTSInvalidVoiceReferenceError(
                "Failed to prepare Echo-TTS voice reference file",
                provider=self.PROVIDER_KEY,
                details={"error": str(exc)},
            ) from exc

    def _resolve_sequence_length(self, extras: Dict[str, Any]) -> int:
        return self._coerce_int(extras.get("sequence_length"), 640)

    def _coerce_bool(self, value: Any, default: bool) -> bool:
        try:
            return parse_bool(value, default=default)
        except Exception:
            return default

    def _coerce_int(self, value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _coerce_optional_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _coerce_float(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _coerce_optional_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
