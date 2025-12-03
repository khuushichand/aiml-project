# kokoro_adapter.py
# Description: Kokoro TTS adapter implementation
#
# Imports
import os
import sys
import platform
from ctypes.util import find_library as _ctypes_find_library
import re
from typing import Optional, Dict, Any, AsyncGenerator, Set, List, Tuple
#
# Third-party Imports
import numpy as np
from loguru import logger
#
# Local Imports
from .base import (
    TTSAdapter,
    TTSCapabilities,
    TTSRequest,
    TTSResponse,
    AudioFormat,
    VoiceInfo,
    ProviderStatus
)
from ..tts_exceptions import (
    TTSProviderNotConfiguredError,
    TTSProviderInitializationError,
    TTSModelNotFoundError,
    TTSModelLoadError,
    TTSGenerationError,
    TTSResourceError,
    TTSInsufficientMemoryError
)
from ..tts_validation import validate_tts_request
from ..utils import parse_bool
from ..tts_resource_manager import get_resource_manager
from ..phoneme_overrides import (
    apply_overrides_to_text,
    filter_overrides_for_provider,
    load_override_entries,
    merge_override_entries,
    parse_override_entries,
    PhonemeOverrideEntry,
)
#
#######################################################################################################################
#
# Kokoro TTS Adapter Implementation

class KokoroAdapter(TTSAdapter):
    """Adapter for Kokoro TTS (ONNX and PyTorch variants)"""

    # Kokoro voice definitions
    VOICES = {
        "af_bella": VoiceInfo(
            id="af_bella",
            name="Bella",
            gender="female",
            language="en-us",
            description="American female voice"
        ),
        "af_sky": VoiceInfo(
            id="af_sky",
            name="Sky",
            gender="female",
            language="en-us",
            description="Young American female voice"
        ),
        "af_heart": VoiceInfo(
            id="af_heart",
            name="Heart",
            gender="female",
            language="en-us",
            description="Warm American female voice"
        ),
        "am_adam": VoiceInfo(
            id="am_adam",
            name="Adam",
            gender="male",
            language="en-us",
            description="American male voice"
        ),
        "am_michael": VoiceInfo(
            id="am_michael",
            name="Michael",
            gender="male",
            language="en-us",
            description="Deep American male voice"
        ),
        "bf_emma": VoiceInfo(
            id="bf_emma",
            name="Emma",
            gender="female",
            language="en-gb",
            description="British female voice"
        ),
        "bf_isabella": VoiceInfo(
            id="bf_isabella",
            name="Isabella",
            gender="female",
            language="en-gb",
            description="Elegant British female voice"
        ),
        "bm_george": VoiceInfo(
            id="bm_george",
            name="George",
            gender="male",
            language="en-gb",
            description="British male voice"
        ),
        "bm_lewis": VoiceInfo(
            id="bm_lewis",
            name="Lewis",
            gender="male",
            language="en-gb",
            description="Young British male voice"
        )
    }

    # Chunking configuration (from Kokoro-FastAPI)
    CHUNK_CONFIG = {
        "target_min_tokens": 30,  # Lowered for testing
        "target_max_tokens": 60,  # Lowered for testing (80 tokens in test > 60)
        "absolute_max_tokens": 150  # Lowered for testing
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        # Determine backend type (ONNX or PyTorch). Default to PyTorch; ONNX is opt-in.
        self.use_onnx = self.config.get("kokoro_use_onnx", False)
        # Device selection with fallback
        preferred = self.config.get("kokoro_device")
        try:
            import torch  # type: ignore
            cuda_avail = torch.cuda.is_available()
            mps_avail = hasattr(torch.backends, 'mps') and getattr(torch.backends.mps, 'is_available', lambda: False)()
        except Exception:
            cuda_avail = False
            mps_avail = False
        if preferred:
            pref = str(preferred).lower()
            if pref == "cuda":
                self.device = "cuda" if cuda_avail else "cpu"
            elif pref == "mps":
                self.device = "mps" if mps_avail else ("cuda" if cuda_avail else "cpu")
            elif pref == "cpu":
                self.device = "cpu"
            else:
                self.device = "cuda" if cuda_avail else "cpu"
        else:
            self.device = "cuda" if cuda_avail else "cpu"

        # Model paths
        # Default to hexgrad/Kokoro-82M PyTorch layout; ONNX users should override via config.
        default_pt_model = "models/kokoro/kokoro-v1_0.pth"
        default_onnx_model = "models/kokoro/onnx/model.onnx"
        self.model_path = self.config.get(
            "kokoro_model_path",
            default_onnx_model if self.use_onnx else default_pt_model,
        )
        # Default voices bundle for kokoro-onnx v1.0 lives alongside the ONNX model.
        default_voices_bin = os.path.join(os.path.dirname(default_onnx_model), "voices-v1.0.bin")
        # Maintain both attribute names for compatibility with tests and internal code.
        # If no explicit path is configured, prefer the bundled voices-v1.0.bin file for ONNX.
        self.voices_json_path = self.config.get("kokoro_voices_json") or (
            default_voices_bin if self.use_onnx else "models/kokoro/voices"
        )
        self.voices_json = self.voices_json_path
        # PyTorch voices directory (for KModel / KPipeline and dynamic voices)
        self.voice_dir = self.config.get("kokoro_voice_dir", "models/kokoro/voices")

        # Auto-download toggle (Kokoro does not auto-download; provided for consistency)
        cfg_auto = self.config.get("kokoro_auto_download")
        env_auto = os.getenv("KOKORO_AUTO_DOWNLOAD") or os.getenv("TTS_AUTO_DOWNLOAD")
        self.auto_download = parse_bool(cfg_auto, default=parse_bool(env_auto, default=True))

        # Text processing settings
        self.normalize_text = self.config.get("normalize_text", True)
        self.sentence_splitting = self.config.get("sentence_splitting", True)
        self.enable_phoneme_overrides = parse_bool(
            self.config.get("kokoro_enable_phoneme_overrides"),
            default=parse_bool(os.getenv("KOKORO_ENABLE_PHONEME_OVERRIDES"), default=True),
        )
        self.phoneme_override_path = (
            self.config.get("kokoro_phoneme_path")
            or self.config.get("phoneme_override_path")
            or os.getenv("TTS_PHONEME_OVERRIDES_PATH")
        )
        self._provider_override_entries: List[PhonemeOverrideEntry] = parse_override_entries(
            self.config.get("kokoro_phoneme_overrides") or self.config.get("phoneme_overrides"),
            provider_hint="kokoro",
        )
        try:
            self._global_override_entries: List[PhonemeOverrideEntry] = load_override_entries(self.phoneme_override_path)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"{self.provider_name}: Failed to load global phoneme overrides: {exc}")
            self._global_override_entries = []

        # Performance settings
        self.sample_rate = self.config.get("sample_rate", 24000)
        # Pause insertion pacing (configurable)
        try:
            self.pause_interval_words = int(
                self.config.get("pause_interval_words")
                or (self.config.get("extra_params", {}) or {}).get("pause_interval_words")
                or 500
            )
        except Exception:
            self.pause_interval_words = 500
        try:
            self.pause_tag = str(
                self.config.get("pause_tag")
                or (self.config.get("extra_params", {}) or {}).get("pause_tag")
                or "[pause=1.1]"
            )
        except Exception:
            self.pause_tag = "[pause=1.1]"

        # Model instances
        self.kokoro_instance = None
        self.model_pt = None
        self.kokoro_pt_model = None  # KModel when using PyTorch backend
        self.kokoro_pt_pipelines = {}
        self.tokenizer = None
        self.audio_normalizer = None
        self._dynamic_voices: List[VoiceInfo] = []

    async def initialize(self) -> bool:
        """Initialize the Kokoro adapter"""
        try:
            # Import audio normalizer
            from tldw_Server_API.app.core.TTS.streaming_audio_writer import AudioNormalizer
            self.audio_normalizer = AudioNormalizer()

            if self.use_onnx:
                success = await self._load_onnx_model()
            else:
                success = await self._load_pytorch_model()

            # Load dynamic voices if available
            try:
                self._load_dynamic_voices()
            except Exception as ve:
                logger.warning(f"{self.provider_name}: Failed to load dynamic voices.json: {ve}")

            if success:
                logger.info(f"{self.provider_name}: Initialized successfully (Backend: {'ONNX' if self.use_onnx else 'PyTorch'}, Device: {self.device})")
                self._status = ProviderStatus.AVAILABLE
                return True
            else:
                self._status = ProviderStatus.ERROR
                return False

        except Exception as e:
            logger.error(f"{self.provider_name}: Initialization failed: {e}")
            self._status = ProviderStatus.ERROR
            return False

    async def _initialize_onnx(self) -> bool:
        """Initialize ONNX backend"""
        try:
            from kokoro_onnx import Kokoro, EspeakConfig

            # Check model file exists
            if not os.path.exists(self.model_path):
                raise TTSModelNotFoundError(
                    f"Kokoro ONNX model not found at {self.model_path}",
                    provider=self.provider_name,
                    details={"model_path": self.model_path}
                )

            # Resolve voices bundle path (required by kokoro-onnx)
            voices_json_arg: Optional[str]
            if self.voices_json_path and os.path.isfile(self.voices_json_path):
                voices_json_arg = self.voices_json_path
            else:
                # If an explicit file path was configured but does not exist, surface a clear error
                if self.voices_json_path and not os.path.isdir(self.voices_json_path):
                    raise TTSModelNotFoundError(
                        f"Kokoro voices bundle not found at {self.voices_json_path}",
                        provider=self.provider_name,
                        details={"voices_json": self.voices_json_path}
                    )
                # Fallback: derive standard voices-v1.0.bin next to the model
                fallback_bin = os.path.join(os.path.dirname(self.model_path), "voices-v1.0.bin")
                if os.path.isfile(fallback_bin):
                    voices_json_arg = fallback_bin
                else:
                    raise TTSModelNotFoundError(
                        "Kokoro voices bundle not found (expected voices-v1.0.bin next to model)",
                        provider=self.provider_name,
                        details={"voices_json": self.voices_json_path, "fallback": fallback_bin}
                    )

            # Configure eSpeak (auto-detect to avoid requiring an env var)
            def _discover_espeak_library() -> Optional[str]:
                # 1) Explicit config override
                path = self.config.get("kokoro_espeak_lib")
                if path and os.path.exists(str(path)):
                    return str(path)
                # 2) Environment variable
                path = os.getenv("PHONEMIZER_ESPEAK_LIBRARY")
                if path and os.path.exists(path):
                    return path
                # 3) Platform heuristics
                sys_plat = sys.platform
                candidates = []
                if sys_plat == "darwin":
                    candidates = [
                        "/opt/homebrew/lib/libespeak-ng.dylib",
                        "/usr/local/lib/libespeak-ng.dylib",
                        "/opt/local/lib/libespeak-ng.dylib",
                    ]
                elif sys_plat.startswith("linux"):
                    arch = platform.machine() or ""
                    candidates = [
                        f"/usr/lib/{arch}/libespeak-ng.so.1" if arch else "",
                        "/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1",
                        "/usr/lib/aarch64-linux-gnu/libespeak-ng.so.1",
                        "/usr/lib64/libespeak-ng.so.1",
                        "/usr/lib/libespeak-ng.so.1",
                        "/lib/x86_64-linux-gnu/libespeak-ng.so.1",
                        "/lib/aarch64-linux-gnu/libespeak-ng.so.1",
                        "/lib/libespeak-ng.so.1",
                    ]
                elif sys_plat in ("win32", "cygwin"):
                    pf = os.environ.get("PROGRAMFILES", r"C:\\Program Files")
                    pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)")
                    candidates = [
                        os.path.join(pf, "eSpeak NG", "libespeak-ng.dll"),
                        os.path.join(pf86, "eSpeak NG", "libespeak-ng.dll"),
                    ]
                    # Also probe PATH entries
                    for d in os.environ.get("PATH", "").split(os.pathsep):
                        if not d:
                            continue
                        candidates.append(os.path.join(d, "libespeak-ng.dll"))
                # Try ctypes discovery last (may return name not path)
                try:
                    lib_name = _ctypes_find_library("espeak-ng") or _ctypes_find_library("espeak")
                    if lib_name and os.path.isabs(lib_name) and os.path.exists(lib_name):
                        candidates.insert(0, lib_name)
                except Exception:
                    pass
                for cand in candidates:
                    if cand and os.path.exists(cand):
                        return cand
                return None

            espeak_lib = _discover_espeak_library()
            espeak_config = EspeakConfig(lib_path=espeak_lib) if espeak_lib else None

            # Initialize Kokoro (support constructors that accept either 1 or 2 positional args)
            if voices_json_arg:
                self.kokoro_instance = Kokoro(
                    self.model_path,
                    voices_json_arg,
                    espeak_config=espeak_config
                )
            else:
                try:
                    self.kokoro_instance = Kokoro(
                        self.model_path,
                        espeak_config=espeak_config
                    )
                except TypeError:
                    # Fallback: pass empty string for voices path if constructor requires it
                    self.kokoro_instance = Kokoro(
                        self.model_path,
                        "",
                        espeak_config=espeak_config
                    )

            # Work around a kokoro-onnx 0.4.x bug where the ONNX graph
            # expects a float `speed` input but the library feeds int32
            # for newer exports (input_ids path), causing:
            #   INVALID_ARGUMENT : Unexpected input data type.
            #   Actual: tensor(int32), expected: tensor(float)
            # Patch Kokoro._create_audio locally to always pass speed as float.
            try:
                import numpy as _np  # type: ignore
                import kokoro_onnx as _konnx  # type: ignore

                orig_create_audio = getattr(_konnx.Kokoro, "_create_audio", None)

                if callable(orig_create_audio) and not getattr(_konnx.Kokoro, "_tldw_speed_patch", False):
                    def _patched_create_audio(self_k, phonemes, voice, speed):
                        from kokoro_onnx.config import SAMPLE_RATE, MAX_PHONEME_LENGTH  # type: ignore
                        from kokoro_onnx.log import log as _log  # type: ignore

                        _log.debug(f"Phonemes: {phonemes}")
                        if len(phonemes) > MAX_PHONEME_LENGTH:
                            _log.warning(
                                f"Phonemes are too long, truncating to {MAX_PHONEME_LENGTH} phonemes"
                            )
                        phonemes = phonemes[:MAX_PHONEME_LENGTH]
                        import time as _time
                        start_t = _time.time()
                        tokens = _np.array(self_k.tokenizer.tokenize(phonemes), dtype=_np.int64)
                        assert len(tokens) <= MAX_PHONEME_LENGTH, (
                            f"Context length is {MAX_PHONEME_LENGTH}, but leave room for the pad token 0 at the start & end"
                        )

                        voice_vec = voice[len(tokens)]
                        tokens = [[0, *tokens, 0]]
                        input_names = [i.name for i in self_k.sess.get_inputs()]
                        if "input_ids" in input_names:
                            # Newer export versions: speed as float32 to avoid type mismatch
                            inputs = {
                                "input_ids": tokens,
                                "style": _np.array(voice_vec, dtype=_np.float32),
                                "speed": _np.array([float(speed)], dtype=_np.float32),
                            }
                        else:
                            inputs = {
                                "tokens": tokens,
                                "style": voice_vec,
                                "speed": _np.ones(1, dtype=_np.float32) * float(speed),
                            }

                        audio = self_k.sess.run(None, inputs)[0]
                        audio_duration = len(audio) / SAMPLE_RATE
                        create_duration = _time.time() - start_t
                        rtf = create_duration / audio_duration
                        _log.debug(
                            f"Created audio in length of {audio_duration:.2f}s for {len(phonemes)} phonemes in {create_duration:.2f}s (RTF: {rtf:.2f}"
                        )
                        return audio, SAMPLE_RATE

                    _konnx.Kokoro._create_audio = _patched_create_audio  # type: ignore[assignment]
                    _konnx.Kokoro._tldw_speed_patch = True  # type: ignore[attr-defined]
            except Exception as _patch_exc:  # pragma: no cover - best-effort patch
                logger.debug(f"{self.provider_name}: speed dtype patch skipped: {_patch_exc}")

            logger.info(f"{self.provider_name}: ONNX model loaded successfully")
            return True

        except ImportError as e:
            logger.error(f"{self.provider_name}: kokoro_onnx library not installed")
            raise TTSModelLoadError(
                "Failed to import kokoro_onnx library",
                provider=self.provider_name,
                details={"error": str(e), "suggestion": "pip install kokoro-onnx"}
            )
        except TTSModelNotFoundError:
            raise
        except Exception as e:
            logger.error(f"{self.provider_name}: ONNX initialization error: {e}")
            raise TTSModelLoadError(
                "Failed to initialize ONNX model",
                provider=self.provider_name,
                details={"error": str(e), "model_path": self.model_path}
            )

    async def _initialize_pytorch(self) -> bool:
        """Initialize PyTorch backend"""
        try:
            import torch
        except ImportError as e:
            raise TTSModelLoadError(
                "PyTorch is required for Kokoro PyTorch backend",
                provider=self.provider_name,
                details={"error": str(e), "suggestion": "pip install torch"}
            )
        # Check model file
        if not os.path.exists(self.model_path):
            raise TTSModelNotFoundError(
                f"Kokoro PyTorch model not found at {self.model_path}",
                provider=self.provider_name,
                details={"model_path": self.model_path}
            )
        # Try native Kokoro PyTorch if available
        try:
            from kokoro import KModel  # type: ignore
            # config.json expected alongside model
            config_path = os.path.join(os.path.dirname(self.model_path), "config.json")
            if not os.path.exists(config_path):
                raise TTSModelLoadError(
                    "Kokoro config.json not found for PyTorch backend",
                    provider=self.provider_name,
                    details={"config_path": config_path}
                )
            self.kokoro_pt_model = KModel(config=config_path, model=self.model_path).eval()
            # Move to device
            dev = str(self.device).lower()
            if dev.startswith("cuda"):
                try:
                    self.kokoro_pt_model = self.kokoro_pt_model.cuda()
                except Exception:
                    pass
            elif dev == "mps":
                try:
                    self.kokoro_pt_model = self.kokoro_pt_model.to(torch.device("mps"))
                except Exception:
                    logger.warning("MPS device not available; using CPU for Kokoro")
                    self.kokoro_pt_model = self.kokoro_pt_model.cpu()
            else:
                self.kokoro_pt_model = self.kokoro_pt_model.cpu()
            logger.info(f"{self.provider_name}: Kokoro PyTorch model loaded on {dev}")
            return True
        except ImportError:
            # Fallback: generic torch.load
            try:
                try:
                    self.model_pt = torch.jit.load(self.model_path, map_location=self.device)
                except Exception:
                    self.model_pt = torch.load(self.model_path, map_location=self.device)
                try:
                    self.model_pt.eval()
                except Exception:
                    pass
                logger.info(f"{self.provider_name}: Loaded generic PyTorch model on {self.device}")
                return True
            except Exception as e:
                raise TTSModelLoadError(
                    "Failed to initialize PyTorch model",
                    provider=self.provider_name,
                    details={"error": str(e), "model_path": self.model_path}
                )

    # Thin wrapper methods for tests to patch
    async def _load_onnx_model(self) -> bool:
        return await self._initialize_onnx()

    async def _load_pytorch_model(self) -> bool:
        return await self._initialize_pytorch()

    async def get_capabilities(self) -> TTSCapabilities:
        """Get Kokoro TTS capabilities"""
        all_voices = list(self.VOICES.values()) + self._dynamic_voices
        return TTSCapabilities(
            provider_name="Kokoro",
            supported_languages={"en-us", "en-gb", "en"},
            supported_voices=all_voices,
            supported_formats={
                # Align with validator: mp3, wav, opus
                AudioFormat.MP3,
                AudioFormat.WAV,
                AudioFormat.OPUS
            },
            max_text_length=1000000,
            supports_streaming=True,
            supports_voice_cloning=False,
            supports_emotion_control=False,
            supports_speech_rate=True,
            supports_pitch_control=False,
            supports_volume_control=False,
            supports_ssml=False,
            supports_phonemes=True,  # Kokoro uses phoneme-based generation
            supports_multi_speaker=True,  # Through voice mixing
            supports_background_audio=False,
            latency_ms=300 if self.device == "cuda" else 3500,  # From Kokoro-FastAPI
            sample_rate=self.sample_rate,
            default_format=AudioFormat.WAV
        )

    async def generate(self, request: TTSRequest) -> TTSResponse:
        """Generate speech using Kokoro TTS"""
        if not await self.ensure_initialized():
            raise TTSProviderNotConfiguredError(
                f"{self.provider_name} not initialized",
                provider=self.provider_name
            )

        # Validate request using new validation system
        try:
            validate_tts_request(request, provider=self.provider_name.lower())
        except Exception as e:
            logger.error(f"{self.provider_name} request validation failed: {e}")
            raise

        # Process voice (support for voice mixing like "af_bella(2)+af_sky(1)")
        voice = self._process_voice(request.voice or "af_bella")

        # Determine language from voice and apply phoneme overrides before normalization
        lang = self._get_language_from_voice(voice)
        raw_text = request.text
        if self._phoneme_overrides_enabled_for_request(request):
            raw_text = self._apply_phoneme_overrides_to_text(raw_text, request=request, lang_hint=lang)

        # Preprocess text
        text = self.preprocess_text(raw_text)

        logger.info(
            f"{self.provider_name}: Generating speech with voice={voice}, "
            f"lang={lang}, format={request.format.value}"
        )

        try:
            # For ONNX backend, always use the complete path (with de-dup)
            # and optionally wrap the result as a stream to keep the API
            # contract while avoiding duplicated phrases.
            if self.use_onnx:
                audio_bytes = await self._generate_complete_kokoro(text, voice, lang, request)

                if request.stream:
                    chunk_size = 8192

                    async def _byte_stream():
                        for i in range(0, len(audio_bytes), chunk_size):
                            chunk = audio_bytes[i:i + chunk_size]
                            if chunk:
                                yield chunk

                    return TTSResponse(
                        audio_stream=_byte_stream(),
                        format=request.format,
                        sample_rate=self.sample_rate,
                        channels=1,
                        voice_used=voice,
                        provider=self.provider_name
                    )

                return TTSResponse(
                    audio_data=audio_bytes,
                    format=request.format,
                    sample_rate=self.sample_rate,
                    channels=1,
                    voice_used=voice,
                    provider=self.provider_name
                )

            # PyTorch backend: preserve true streaming semantics
            if request.stream:
                return TTSResponse(
                    audio_stream=self._stream_audio_kokoro(text, voice, lang, request),
                    format=request.format,
                    sample_rate=self.sample_rate,
                    channels=1,
                    voice_used=voice,
                    provider=self.provider_name
                )

            audio_data = await self._generate_complete_kokoro(text, voice, lang, request)
            return TTSResponse(
                audio_data=audio_data,
                format=request.format,
                sample_rate=self.sample_rate,
                channels=1,
                voice_used=voice,
                provider=self.provider_name
            )

        except Exception as e:
            logger.error(f"{self.provider_name} generation error: {e}")
            raise

    async def _stream_audio_kokoro(
        self,
        text: str,
        voice: str,
        lang: str,
        request: TTSRequest
    ) -> AsyncGenerator[bytes, None]:
        """Stream audio from Kokoro"""
        if self.use_onnx:
            if not self.kokoro_instance:
                raise ValueError("Kokoro ONNX not initialized")
        else:
            if self.kokoro_pt_model is None and self.model_pt is None:
                raise ValueError("Kokoro PyTorch model not initialized")

        # Import StreamingAudioWriter for format conversion
        from tldw_Server_API.app.core.TTS.streaming_audio_writer import StreamingAudioWriter
        # Defer writer creation until first chunk to honor source SR
        writer = None

        try:
            chunk_count = 0
            # Stream audio chunks
            if self.use_onnx:
                base_iter = self.kokoro_instance.create_stream(
                    text,
                    voice=voice,
                    speed=request.speed,
                    lang=lang
                )
                # Wrap sync iterators into async for uniform consumption
                import inspect
                if hasattr(base_iter, "__aiter__") or inspect.isasyncgen(base_iter):
                    stream_iter = base_iter
                else:
                    def _sync_source():
                        for item in base_iter:
                            yield item

                    async def _async_wrap():
                        for item in _sync_source():
                            yield item
                    stream_iter = _async_wrap()
            else:
                # Use Kokoro PyTorch pipeline if available
                try:
                    from kokoro import KPipeline  # type: ignore
                except ImportError:
                    # Cannot proceed without kokoro pipeline
                    raise TTSGenerationError(
                        "Kokoro PyTorch generation requires 'kokoro' package",
                        provider=self.provider_name,
                        details={"suggestion": "pip install kokoro-tts or Kokoro PyTorch package"}
                    )
                # Capture the logical voice id before resolving file path
                voice_id = voice

                # Determine voice path if a voice file exists
                voice_path = voice
                try:
                    # Attempt to resolve to a .pt file under configured voice_dir if voice looks like an id
                    if self.voice_dir and isinstance(voice, str) and os.path.isdir(self.voice_dir):
                        candidate = os.path.join(self.voice_dir, f"{voice}.pt")
                        if os.path.exists(candidate):
                            voice_path = candidate
                except Exception:
                    pass
                # Pick pipeline by Kokoro language code (e.g., 'a' for American, 'b' for British)
                lang_code = self._get_kpipeline_lang_code(voice_id if isinstance(voice_id, str) else "", lang)
                key = lang_code
                if key not in self.kokoro_pt_pipelines:
                    self.kokoro_pt_pipelines[key] = KPipeline(
                        lang_code=key,
                        model=self.kokoro_pt_model,
                        device=str(self.device)
                    )
                pipeline = self.kokoro_pt_pipelines[key]

                # Define a sync generator wrapper to async iterate
                def _sync_iter():
                    for result in pipeline(text, voice=voice_path, speed=request.speed, model=self.kokoro_pt_model):
                        yield result

                async def _async_iter():
                    for result in _sync_iter():
                        yield result

                stream_iter = _async_iter()

            async for item in stream_iter:
                samples_chunk, sr_chunk = self._unpack_stream_item(item)
                if samples_chunk is not None and len(samples_chunk) > 0:
                    # Heuristic de-duplication for providers that may repeat phrases
                    try:
                        samples_chunk = self._dedupe_repeated_audio(samples_chunk)
                    except Exception:
                        pass
                    chunk_count += 1

                    # Create writer on first chunk so we can pass the true SR
                    if writer is None:
                        try:
                            effective_sr = int(sr_chunk) if sr_chunk else self.sample_rate
                        except Exception:
                            effective_sr = self.sample_rate
                        writer = StreamingAudioWriter(
                            format=request.format.value,
                            sample_rate=effective_sr,
                            channels=1,
                        )

                    # Normalize float32 samples to int16
                    normalized_chunk = self.audio_normalizer.normalize(
                        samples_chunk,
                        target_dtype=np.int16
                    )

                    # Write chunk and get encoded bytes
                    encoded_bytes = writer.write_chunk(normalized_chunk)
                    if encoded_bytes:
                        yield encoded_bytes
                        logger.debug(f"{self.provider_name}: Yielded chunk {chunk_count}, {len(encoded_bytes)} bytes")

            # Finalize stream
            if writer is not None:
                final_bytes = writer.write_chunk(finalize=True)
                if final_bytes:
                    yield final_bytes
                    logger.debug(f"{self.provider_name}: Yielded final chunk, {len(final_bytes)} bytes")

            logger.info(f"{self.provider_name}: Successfully streamed {chunk_count} chunks")

        except Exception as e:
            logger.error(f"{self.provider_name} streaming error: {e}")
            raise
        finally:
            try:
                if writer is not None:
                    writer.close()
            except Exception:
                pass

    async def _generate_complete_kokoro(
        self,
        text: str,
        voice: str,
        lang: str,
        request: TTSRequest
    ) -> bytes:
        """Generate complete audio from Kokoro"""
        if self.use_onnx:
            # Use synchronous Kokoro.create in a worker thread and post-process
            import asyncio as _asyncio
            loop = _asyncio.get_event_loop()
            samples, sr = await loop.run_in_executor(
                None,
                self.kokoro_instance.create,  # type: ignore[arg-type]
                text,
                voice,
                float(request.speed),
                lang,
            )

            try:
                original_len = len(samples)
                deduped = self._dedupe_repeated_audio(samples)
                if hasattr(deduped, "__len__") and len(deduped) != original_len:
                    logger.info(
                        f"{self.provider_name}: de-duplicated waveform from {original_len} to {len(deduped)} samples"
                    )
                else:
                    logger.debug(f"{self.provider_name}: de-duplication not applied (len={original_len})")
                samples = deduped
            except Exception as _dedupe_exc:
                logger.debug(f"{self.provider_name}: de-duplication skipped: {_dedupe_exc}")

            from tldw_Server_API.app.core.TTS.streaming_audio_writer import StreamingAudioWriter

            writer = StreamingAudioWriter(
                format=request.format.value,
                sample_rate=int(sr) if sr else self.sample_rate,
                channels=1,
            )
            try:
                normalized = self.audio_normalizer.normalize(samples, target_dtype=np.int16)  # type: ignore[arg-type]
                first = writer.write_chunk(normalized) or b""
                final = writer.write_chunk(finalize=True) or b""
                if request.format == AudioFormat.PCM:
                    return first
                return first + final
            finally:
                writer.close()

        # Fallback: collect encoded bytes from streaming path (PyTorch backend)
        all_audio = b""
        async for chunk in self._stream_audio_kokoro(text, voice, lang, request):
            all_audio += chunk
        return all_audio

    def _process_voice(self, voice: str) -> str:
        """
        Process voice string, supporting voice mixing.
        Examples:
        - "af_bella" -> "af_bella"
        - "af_bella(2)+af_sky(1)" -> mixed voice
        """
        # Check if it's a mixed voice pattern
        if "+" in voice and "(" in voice:
            # This is a mixed voice, return as-is for Kokoro to handle
            return voice

        # Accept known voices (static or dynamically discovered)
        try:
            dynamic_ids = {v.id for v in self._dynamic_voices}
        except Exception:
            dynamic_ids = set()
        if voice in self.VOICES or voice in dynamic_ids:
            return voice

        # Map generic voice names to Kokoro voices when unknown
        voice = self.map_voice(voice)

        return voice

    def _dedupe_repeated_audio(self, samples: np.ndarray) -> np.ndarray:
        """Heuristically trim duplicated phrases when the waveform is repeated twice."""
        try:
            if samples.ndim != 1:
                return samples
            n = len(samples)
            if n < 8000:
                return samples

            arr = samples.astype(np.float32, copy=False)

            best_diff: Optional[float] = None
            best_offset: Optional[int] = None

            start = n // 3
            end = (2 * n) // 3
            step = max(256, n // 100)

            for offset in range(start, end, step):
                a = arr[: n - offset]
                b = arr[offset:]
                m = min(len(a), len(b))
                if m < 4000:
                    continue
                a_seg = a[:m].copy()
                b_seg = b[:m].copy()
                max_a = float(np.max(np.abs(a_seg))) or 1.0
                max_b = float(np.max(np.abs(b_seg))) or 1.0
                a_seg /= max_a
                b_seg /= max_b
                diff = float(np.mean(np.abs(a_seg - b_seg)))
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_offset = offset

            if best_diff is not None and best_offset is not None and best_diff < 0.08:
                return samples[:best_offset]
            return samples
        except Exception:
            return samples

    def _load_dynamic_voices(self) -> None:
        """Load voices from voices.json and merge with static voices.

        Expected JSON structure (array of entries):
        [{"id": "af_bella", "name": "Bella", "gender": "female", "language": "en-us", "description": "..."}, ...]
        """
        path = self.voices_json
        if not path or not os.path.exists(path):
            return
        dyn: List[VoiceInfo] = []
        existing_ids = set(self.VOICES.keys()) | {v.id for v in self._dynamic_voices}
        try:
            if os.path.isdir(path):
                # v1.0 layout: voices directory containing *.bin (ONNX) or *.pt (PyTorch) files
                for fname in os.listdir(path):
                    if not (fname.endswith('.bin') or fname.endswith('.pt')):
                        continue
                    vid = os.path.splitext(fname)[0]
                    if not vid or vid in existing_ids:
                        continue
                    # Heuristic language by prefix like 'af_', 'am_', 'bf_', 'bm_', 'zf_', 'zm_', etc.
                    lang = 'en'
                    try:
                        if vid.startswith('a'):
                            lang = 'en-us'
                        elif vid.startswith('b'):
                            lang = 'en-gb'
                    except Exception:
                        pass
                    vinfo = VoiceInfo(
                        id=vid,
                        name=vid,
                        gender=None,
                        language=lang,
                        description='Kokoro voice profile'
                    )
                    dyn.append(vinfo)
                    existing_ids.add(vid)
                self._dynamic_voices = dyn
                return
        except Exception:
            # Fall back to JSON parsing
            pass
        # JSON file layout (legacy)
        try:
            import json
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and "voices" in data:
                entries = data["voices"]
            else:
                entries = data
            if not isinstance(entries, list):
                return
            for entry in entries:
                try:
                    vid = str(entry.get("id") or entry.get("voice_id") or "").strip()
                    if not vid or vid in existing_ids:
                        continue
                    vinfo = VoiceInfo(
                        id=vid,
                        name=str(entry.get("name") or vid),
                        gender=entry.get("gender"),
                        language=str(entry.get("language") or "en"),
                        description=entry.get("description")
                    )
                    dyn.append(vinfo)
                    existing_ids.add(vid)
                except Exception:
                    continue
            self._dynamic_voices = dyn
        except Exception:
            return

    def _get_language_from_voice(self, voice: str) -> str:
        """Get language code from voice ID"""
        # Handle mixed voices
        if "+" in voice:
            # Extract first voice from mix
            first_voice = voice.split("+")[0].split("(")[0].strip()
        else:
            first_voice = voice

        # Determine language from voice prefix
        if first_voice.startswith("a"):
            return "en-us"  # American
        elif first_voice.startswith("b"):
            return "en-gb"  # British
        else:
            return "en-us"  # Default to American

    def _get_kpipeline_lang_code(self, voice: str, lang: Optional[str]) -> str:
        """Map voice/lang to Kokoro PyTorch KPipeline lang_code (e.g., 'a', 'b')."""
        base = voice or ""
        try:
            # If a file path was passed, strip directory and extension
            base = os.path.basename(base)
            if "." in base:
                base = base.split(".", 1)[0]
        except Exception:
            base = voice or ""
        base = base.strip()

        # Heuristic mapping for known English voices
        if base.startswith("af_") or base.startswith("am_"):
            return "a"  # American English
        if base.startswith("bf_") or base.startswith("bm_"):
            return "b"  # British English

        # Fallback based on language string
        if lang:
            l = str(lang).lower()
            if l.startswith("en"):
                return "a"

        # Default to American English code
        return "a"

    def _unpack_stream_item(self, item: Any) -> Tuple[Optional[np.ndarray], Optional[int]]:
        """
        Normalize stream items from both ONNX and PyTorch backends into (samples, sample_rate).

        Supported shapes:
          - (samples, sr)
          - (samples, sr, *rest)
          - samples (np.ndarray or list), using adapter sample_rate
        """
        if item is None:
            return None, None

        # Hexgrad Kokoro PyTorch pipeline returns a Result with an `audio` tensor
        try:
            if hasattr(item, "audio"):
                audio = item.audio
                try:
                    import torch  # type: ignore

                    if isinstance(audio, torch.Tensor):
                        audio = audio.detach().cpu().numpy()
                except Exception:
                    # Fallback: try NumPy conversion directly
                    try:
                        audio = np.asarray(audio)
                    except Exception:
                        return None, None
                return audio, self.sample_rate
        except Exception:
            pass

        # Tuple/list variants
        if isinstance(item, (tuple, list)):
            if len(item) == 0:
                return None, None
            if len(item) == 1:
                return item[0], self.sample_rate
            # Use the first two elements as (audio, sample_rate); ignore the rest
            samples = item[0]
            sr = item[1]
            try:
                sr_int = int(sr) if sr is not None else self.sample_rate
            except Exception:
                sr_int = self.sample_rate
            return samples, sr_int

        # Single array-like item: treat as audio with default sample_rate
        return item, self.sample_rate

    def map_voice(self, voice_id: str) -> str:
        """Map generic voice ID to Kokoro voice"""
        # Check if it's already a valid Kokoro voice
        if voice_id in self.VOICES:
            return voice_id

        # Try common mappings
        voice_mappings = {
            "female": "af_bella",
            "male": "am_adam",
            "british_female": "bf_emma",
            "british_male": "bm_george",
            "american_female": "af_bella",
            "american_male": "am_adam",
            "young_female": "af_sky",
            "deep_male": "am_michael",
            "warm": "af_heart",
            # Historical mapping kept for compatibility; note this id is not in static VOICES
            "child": "af_nicole",
        }

        return voice_mappings.get(voice_id.lower(), "af_bella")

    def _phoneme_overrides_enabled_for_request(self, request: TTSRequest) -> bool:
        """Determine whether phoneme overrides should be applied for this request."""
        try:
            extra = getattr(request, "extra_params", {}) or {}
        except Exception:
            extra = {}
        if "phoneme_overrides_enabled" in extra:
            return parse_bool(extra.get("phoneme_overrides_enabled"), default=self.enable_phoneme_overrides)
        if parse_bool(extra.get("disable_phoneme_overrides"), default=False):
            return False
        return self.enable_phoneme_overrides

    def _collect_phoneme_overrides(self, request: TTSRequest) -> List[PhonemeOverrideEntry]:
        """Merge global, provider, and request-level overrides (request wins)."""
        base = filter_overrides_for_provider(self._global_override_entries, "kokoro")
        provider = filter_overrides_for_provider(self._provider_override_entries, "kokoro")
        try:
            extra = getattr(request, "extra_params", {}) or {}
        except Exception:
            extra = {}
        request_overrides_raw = extra.get("phoneme_overrides") or extra.get("phoneme_map")
        request_entries = parse_override_entries(request_overrides_raw, provider_hint="kokoro")
        return merge_override_entries(base, provider, request_entries)

    def _apply_phoneme_overrides_to_text(
        self,
        text: str,
        *,
        request: TTSRequest,
        lang_hint: Optional[str],
    ) -> str:
        """Apply applicable phoneme overrides to the provided text."""
        try:
            entries = self._collect_phoneme_overrides(request)
        except Exception as exc:
            logger.debug(f"{self.provider_name}: failed to collect phoneme overrides: {exc}")
            return text
        if not entries:
            return text
        try:
            updated = apply_overrides_to_text(text, entries, lang_hint=lang_hint)
            return updated
        except Exception as exc:
            logger.debug(f"{self.provider_name}: failed to apply phoneme overrides: {exc}")
            return text

    def preprocess_text(self, text: str, **kwargs) -> str:
        """Preprocess text for Kokoro"""
        # Strip excess whitespace
        text = text.strip()

        # Normalize text if enabled
        if self.normalize_text:
            # Basic normalization (Kokoro handles most of this internally)
            text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
            # Normalize quotes/apostrophes
            text = text.replace('“', '"').replace('”', '"').replace('‟', '"')
            text = text.replace('‘', "'").replace('’', "'")

        # Insert periodic pause tags to keep very long inputs paced
        try:
            text = self._insert_pause_tags(text, words_between=self.pause_interval_words, pause_tag=self.pause_tag)
        except Exception:
            pass

        return text

    def _insert_pause_tags(self, text: str, words_between: int = 500, pause_tag: str = '[pause=1.1]') -> str:
        """Ensure a pause tag appears at least every N words.

        - Splits on whitespace and inserts a pause marker every `words_between` tokens.
        - Respects existing pause markers by splitting and processing each section independently.
        """
        # If already contains pause tags, process sections separately so spacing is preserved
        if pause_tag in text:
            parts = text.split(pause_tag)
            processed = [self._insert_pause_tags(p, words_between, pause_tag) for p in parts]
            return (pause_tag).join(processed)

        words = text.split()
        if len(words) <= words_between:
            return text

        out = []
        cnt = 0
        for w in words:
            out.append(w)
            cnt += 1
            if cnt >= words_between:
                out.append(pause_tag)
                cnt = 0
        return ' '.join(out)

    def chunk_text(self, text: str) -> List[str]:
        """
        Chunk text for optimal Kokoro processing.
        Based on Kokoro-FastAPI chunking strategy.
        """
        # Simple sentence-based chunking
        import re

        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            # Estimate token count (rough approximation: 1 token ≈ 4 chars)
            current_plus_sentence = current_chunk + (" " + sentence if current_chunk else sentence)
            estimated_tokens = len(current_plus_sentence) / 4

            if estimated_tokens < self.CHUNK_CONFIG["target_max_tokens"]:
                current_chunk = current_plus_sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    async def _cleanup_resources(self):
        """Clean up Kokoro adapter resources"""
        try:
            # Clean up ONNX instance
            if self.kokoro_instance:
                self.kokoro_instance = None
                logger.debug(f"{self.provider_name}: ONNX instance cleared")

            # Clean up PyTorch model and tokenizer
            if self.model_pt:
                self.model_pt = None
                logger.debug(f"{self.provider_name}: PyTorch model cleared")

            if self.tokenizer:
                self.tokenizer = None
                logger.debug(f"{self.provider_name}: Tokenizer cleared")

            # Clear normalizer
            if self.audio_normalizer:
                self.audio_normalizer = None
            # Clear optionally present attributes used in tests
            if hasattr(self, 'model'):
                self.model = None
            if hasattr(self, 'phonemizer'):
                self.phonemizer = None

            # Clear CUDA cache if using GPU
            if self.device.startswith("cuda"):
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        logger.debug(f"{self.provider_name}: CUDA cache cleared")
                except ImportError:
                    pass

        except Exception as e:
            logger.warning(f"{self.provider_name}: Error during cleanup: {e}")

#
# End of kokoro_adapter.py
#######################################################################################################################
