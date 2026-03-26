from __future__ import annotations

import asyncio
import contextlib
import tempfile
import wave
from pathlib import Path
from typing import Any, Optional

import numpy as np
from loguru import logger

from ..audio_converter import AudioConverter
from ..streaming_audio_writer import AudioNormalizer
from ..tts_exceptions import (
    TTSGenerationError,
    TTSInvalidVoiceReferenceError,
    TTSModelNotFoundError,
    TTSProviderInitializationError,
    TTSProviderNotConfiguredError,
    TTSTimeoutError,
    TTSUnsupportedFormatError,
    TTSValidationError,
)
from ..tts_validation import validate_tts_request
from ..utils import parse_bool
from .base import AudioFormat, ProviderStatus, TTSAdapter, TTSCapabilities, TTSRequest, TTSResponse
from .pocket_tts_cpp_runtime import (
    PROVIDER_KEY,
    VALID_PRECISIONS,
    build_cli_command,
    validate_runtime_assets,
)


class PocketTTSCppAdapter(TTSAdapter):
    """Adapter for the PocketTTS.cpp command-line runtime."""

    PROVIDER_KEY = "pocket_tts_cpp"
    SUPPORTED_FORMATS: set[AudioFormat] = {
        AudioFormat.MP3,
        AudioFormat.WAV,
        AudioFormat.OPUS,
        AudioFormat.FLAC,
        AudioFormat.PCM,
        AudioFormat.AAC,
    }
    SUPPORTED_LANGUAGES = {"en"}
    DEFAULT_SAMPLE_RATE = 24000
    MAX_TEXT_LENGTH = 5000

    def __init__(self, config: Optional[dict[str, Any]] = None):
        super().__init__(config)
        cfg = config or {}
        extras = cfg.get("extra_params", {}) or {}

        def _cfg_value(key: str, default: Any = None) -> Any:
            value = cfg.get(key)
            if value is None:
                value = extras.get(key)
            return default if value is None else value

        def _float_value(key: str, default: Optional[float] = None) -> Optional[float]:
            value = _cfg_value(key, default)
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        def _int_value(key: str, default: Optional[int] = None) -> Optional[int]:
            value = _cfg_value(key, default)
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        self.binary_path = Path(_cfg_value("binary_path", "bin/pocket-tts")).expanduser()
        self.model_path = Path(_cfg_value("model_path", "models/pocket_tts_cpp/onnx")).expanduser()
        self.tokenizer_path = Path(_cfg_value("tokenizer_path", "models/pocket_tts_cpp/tokenizer.model")).expanduser()
        self.voices_dir = _cfg_value("voices_dir")
        self.voices_dir = Path(self.voices_dir).expanduser() if self.voices_dir else None

        self.precision = str(_cfg_value("precision", "int8")).lower()
        self.timeout = _int_value("timeout", 60) or 60
        self.stream_probe_timeout = _float_value("stream_probe_timeout", 5.0) or 5.0
        self.prefer_stdout = parse_bool(_cfg_value("prefer_stdout", True), default=True)
        self.enable_voice_cache = parse_bool(_cfg_value("enable_voice_cache", True), default=True)
        self.temperature = _float_value("temperature")
        self.lsd_steps = _int_value("lsd_steps")
        self.eos_threshold = _float_value("eos_threshold")
        self.eos_extra = _float_value("eos_extra")
        self.noise_clamp = _float_value("noise_clamp")
        self.threads = _int_value("threads")
        self.verbose = parse_bool(_cfg_value("verbose", False), default=False)
        self.profile = parse_bool(_cfg_value("profile", False), default=False)

        self._audio_normalizer = AudioNormalizer()

    async def initialize(self) -> bool:
        if self._initialized:
            return True

        if self.precision not in VALID_PRECISIONS:
            raise TTSProviderInitializationError(
                f"Invalid precision '{self.precision}' for PocketTTS.cpp",
                provider=self.PROVIDER_KEY,
                details={"valid_precisions": sorted(VALID_PRECISIONS)},
            )

        validate_runtime_assets(
            binary_path=self.binary_path,
            model_path=self.model_path,
            tokenizer_path=self.tokenizer_path,
            precision=self.precision,
        )

        self._capabilities = await self.get_capabilities()
        self._status = ProviderStatus.AVAILABLE
        self._initialized = True
        logger.info(
            "PocketTTS.cpp adapter initialized (binary={}, models={}, tokenizer={}, precision={})",
            self.binary_path,
            self.model_path,
            self.tokenizer_path,
            self.precision,
        )
        return True

    async def generate(self, request: TTSRequest) -> TTSResponse:
        if not await self.ensure_initialized():
            raise TTSProviderNotConfiguredError(
                "PocketTTS.cpp adapter not initialized",
                provider=self.PROVIDER_KEY,
            )

        if request.stream:
            raise TTSValidationError(
                "PocketTTS.cpp streaming is not implemented yet",
                provider=self.PROVIDER_KEY,
                details={"hint": "Use stream=false until Task 4 lands"},
            )

        if request.format not in self.SUPPORTED_FORMATS:
            raise TTSUnsupportedFormatError(
                f"Format {request.format.value} not supported by PocketTTS.cpp",
                provider=self.PROVIDER_KEY,
            )

        try:
            validate_tts_request(request, provider=self.PROVIDER_KEY)
        except TTSValidationError:
            raise
        except Exception as exc:
            raise TTSValidationError(
                f"Validation failed for PocketTTS.cpp request: {exc}",
                provider=self.PROVIDER_KEY,
            ) from exc

        voice_path = self._resolve_voice_path(request)
        use_stdout = self._should_use_stdout(request)

        temp_output_path: Optional[Path] = None
        temp_converted_path: Optional[Path] = None
        try:
            if not use_stdout:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_output:
                    temp_output_path = Path(temp_output.name)

            command = build_cli_command(
                binary_path=self.binary_path,
                text=self.preprocess_text(request.text),
                voice_path=voice_path,
                model_path=self.model_path,
                tokenizer_path=self.tokenizer_path,
                output_path=temp_output_path,
                precision=self.precision,
                prefer_stdout=use_stdout,
                enable_voice_cache=self.enable_voice_cache,
                voices_dir=self.voices_dir,
                temperature=self.temperature,
                lsd_steps=self.lsd_steps,
                eos_threshold=self.eos_threshold,
                eos_extra=self.eos_extra,
                noise_clamp=self.noise_clamp,
                threads=self.threads,
                verbose=self.verbose,
                profile=self.profile,
            )

            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
            except asyncio.TimeoutError as exc:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                with contextlib.suppress(Exception):
                    await process.communicate()
                raise TTSTimeoutError(
                    "Timed out waiting for PocketTTS.cpp CLI output",
                    provider=self.PROVIDER_KEY,
                    details={"timeout_seconds": self.timeout},
                ) from exc

            if process.returncode != 0:
                stderr_text = stderr.decode("utf-8", errors="ignore").strip()
                raise TTSGenerationError(
                    "PocketTTS.cpp CLI exited with an error",
                    provider=self.PROVIDER_KEY,
                    details={
                        "returncode": process.returncode,
                        "stderr": stderr_text,
                    },
                )

            if use_stdout:
                audio_bytes = await self._convert_stdout_audio(stdout, request.format)
                transport = "stdout"
            else:
                if temp_output_path is None or not temp_output_path.exists():
                    raise TTSGenerationError(
                        "PocketTTS.cpp did not produce an output file",
                        provider=self.PROVIDER_KEY,
                    )
                audio_bytes, temp_converted_path = await self._load_file_output(
                    output_path=temp_output_path,
                    target_format=request.format,
                )
                transport = "file"

            return TTSResponse(
                audio_data=audio_bytes,
                format=request.format,
                sample_rate=self.DEFAULT_SAMPLE_RATE,
                channels=1,
                text_processed=request.text,
                voice_used=request.voice,
                provider=self.PROVIDER_KEY,
                model=request.model or self.PROVIDER_KEY,
                metadata={"transport": transport},
            )
        except (TTSValidationError, TTSModelNotFoundError, TTSUnsupportedFormatError, TTSTimeoutError):
            raise
        except Exception as exc:
            logger.error("PocketTTS.cpp generation failed: {}", exc, exc_info=True)
            raise TTSGenerationError(
                "PocketTTS.cpp generation failed",
                provider=self.PROVIDER_KEY,
                details={"error": str(exc)},
            ) from exc
        finally:
            for path in (temp_output_path, temp_converted_path):
                if path is not None:
                    with contextlib.suppress(OSError):
                        path.unlink()

    async def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            provider_name="PocketTTS.cpp",
            supported_languages=self.SUPPORTED_LANGUAGES,
            supported_voices=[],
            supported_formats=self.SUPPORTED_FORMATS,
            max_text_length=self.MAX_TEXT_LENGTH,
            supports_streaming=False,
            supports_voice_cloning=True,
            sample_rate=self.DEFAULT_SAMPLE_RATE,
            default_format=AudioFormat.WAV,
        )

    def _resolve_voice_path(self, request: TTSRequest) -> Path:
        extras = request.extra_params if isinstance(request.extra_params, dict) else {}
        raw_voice_path = extras.get("pocket_tts_cpp_voice_path")
        if not raw_voice_path:
            raise TTSInvalidVoiceReferenceError(
                "PocketTTS.cpp requires a provider-managed voice path",
                provider=self.PROVIDER_KEY,
                details={"param": "extra_params.pocket_tts_cpp_voice_path"},
            )

        voice_path = Path(str(raw_voice_path)).expanduser()
        if not voice_path.exists() or not voice_path.is_file():
            raise TTSInvalidVoiceReferenceError(
                "PocketTTS.cpp voice path does not exist",
                provider=self.PROVIDER_KEY,
                details={"voice_path": str(voice_path)},
            )
        return voice_path

    def _should_use_stdout(self, request: TTSRequest) -> bool:
        extras = request.extra_params if isinstance(request.extra_params, dict) else {}
        if "prefer_stdout" in extras:
            prefer_stdout = parse_bool(extras.get("prefer_stdout"), default=self.prefer_stdout)
        else:
            prefer_stdout = self.prefer_stdout
        return prefer_stdout and request.format == AudioFormat.PCM

    async def _convert_stdout_audio(self, stdout: bytes, target_format: AudioFormat) -> bytes:
        if not stdout:
            raise TTSGenerationError(
                "PocketTTS.cpp stdout transport returned no audio",
                provider=self.PROVIDER_KEY,
            )

        audio = np.frombuffer(stdout, dtype=np.float32)
        if audio.size == 0:
            raise TTSGenerationError(
                "PocketTTS.cpp stdout transport returned empty PCM data",
                provider=self.PROVIDER_KEY,
            )

        audio_i16 = self._audio_normalizer.normalize(audio, target_dtype=np.int16)
        return await self.convert_audio_format(
            audio_i16,
            source_format=AudioFormat.PCM,
            target_format=target_format,
            sample_rate=self.DEFAULT_SAMPLE_RATE,
        )

    async def _load_file_output(
        self,
        *,
        output_path: Path,
        target_format: AudioFormat,
    ) -> tuple[bytes, Optional[Path]]:
        if target_format == AudioFormat.WAV:
            return output_path.read_bytes(), None
        if target_format == AudioFormat.PCM:
            with wave.open(str(output_path), "rb") as wav_file:
                return wav_file.readframes(wav_file.getnframes()), None

        with tempfile.NamedTemporaryFile(suffix=f".{target_format.value}", delete=False) as converted_file:
            converted_path = Path(converted_file.name)

        converted = await AudioConverter.convert_format(
            output_path,
            converted_path,
            target_format.value,
            sample_rate=self.DEFAULT_SAMPLE_RATE,
            channels=1,
        )
        converted_path = converted_path.with_suffix(f".{target_format.value}")
        if not converted or not converted_path.exists():
            raise TTSGenerationError(
                f"Failed converting PocketTTS.cpp output to {target_format.value}",
                provider=self.PROVIDER_KEY,
                details={"target_format": target_format.value},
            )
        return converted_path.read_bytes(), converted_path
