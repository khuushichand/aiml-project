# Audio_Transcription_Nemo.py
#########################################
# Nemo Transcription Module
# This module provides transcription using NVIDIA Nemo models:
# - Canary-1b-v2: Multitask multilingual ASR/AST model supporting 25 European languages
#   for both speech transcription (ASR) and speech translation (AST).
# - Parakeet TDT: Efficient model with support for standard, ONNX, and MLX variants.
#
####################
# Function List
#
# 1. load_canary_model() - Load and cache Canary-1b-v2 model
# 2. load_parakeet_model(variant='standard') - Load Parakeet model (standard/ONNX/MLX)
# 3. transcribe_with_canary(audio_data, sample_rate, language, *, task, target_language) - Canary ASR/AST helper
# 4. transcribe_with_parakeet(audio_data, sample_rate, variant='standard') - Transcribe using Parakeet
# 5. transcribe_with_nemo(audio_data, sample_rate, model='parakeet', variant='standard') - Unified entry point
#
####################

import os
import sys
import logging
from loguru import logger
import tempfile
from pathlib import Path
from typing import Optional, Union, Tuple, Dict, Any, Callable
import numpy as np
import torch

# Apply NumPy 2.0 compatibility patches before importing Nemo
from .numpy_compat import ensure_numpy_compatibility
ensure_numpy_compatibility()

# Import local config helpers
from tldw_Server_API.app.core.config import get_stt_config, loaded_config_data

# Global model cache
_model_cache: Dict[str, Any] = {}

# Canonical language codes supported by Canary-1b-v2.
# See: https://huggingface.co/nvidia/canary-1b-v2
CANARY_SUPPORTED_LANG_CODES = {
    "bg",  # Bulgarian
    "hr",  # Croatian
    "cs",  # Czech
    "da",  # Danish
    "nl",  # Dutch
    "en",  # English
    "et",  # Estonian
    "fi",  # Finnish
    "fr",  # French
    "de",  # German
    "el",  # Greek
    "hu",  # Hungarian
    "it",  # Italian
    "lv",  # Latvian
    "lt",  # Lithuanian
    "mt",  # Maltese
    "pl",  # Polish
    "pt",  # Portuguese
    "ro",  # Romanian
    "sk",  # Slovak
    "sl",  # Slovenian
    "es",  # Spanish
    "sv",  # Swedish
    "ru",  # Russian
    "uk",  # Ukrainian
}

CANARY_SUPPORTED_LANG_CODES_STR = ", ".join(sorted(CANARY_SUPPORTED_LANG_CODES))

# Lightweight import probe for Nemo toolkit (used by streaming defaults and
# health checks to decide whether Parakeet/Canary are even eligible).
_nemo_import_checked: bool = False
_nemo_available: bool = False


def _temp_wav_from_numpy(audio_np: np.ndarray, sample_rate: int) -> str:
    """Write NumPy audio to a temporary WAV file and return its path."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        import soundfile as sf
        sf.write(tmp_file.name, audio_np, sample_rate)
        return tmp_file.name


def is_nemo_available() -> bool:
    """Return True if the core Nemo ASR toolkit appears importable.

    This performs a lightweight import check (without loading any models) and
    caches the result for subsequent calls. It does not guarantee that specific
    models (Parakeet/Canary) are available, only that the `nemo.collections.asr`
    package can be imported.
    """
    global _nemo_import_checked, _nemo_available
    if _nemo_import_checked:
        return _nemo_available

    _nemo_import_checked = True
    try:
        import nemo.collections.asr  # type: ignore  # noqa: F401
        _nemo_available = True
    except Exception:
        _nemo_available = False
    return _nemo_available

#######################################################################################################################
# Model Loading Functions
#


def _normalize_canary_lang(code: Optional[str]) -> Optional[str]:
    """
    Normalize a language code for Canary-1b-v2.

    Accepts BCP-47 style codes such as "en-US" or "de_DE" and normalizes them
    to a two-letter ISO 639-1 code when possible. Returns None if the language
    is not supported by Canary.
    """
    if not code:
        return None

    raw = str(code).strip().lower()
    if not raw:
        return None

    # Accept simple locale-style codes like "en-US" or "de_DE"
    if len(raw) >= 4 and raw[2] in {"-", "_"}:
        raw = raw[:2]

    if raw not in CANARY_SUPPORTED_LANG_CODES:
        logging.warning(
            "Canary received unsupported language code '%s'; "
            "supported codes are: %s",
            code,
            CANARY_SUPPORTED_LANG_CODES_STR,
        )
        return None

    return raw

def _get_model_cache_key(model_name: str, variant: str = 'standard') -> str:
    """Generate a cache key for model storage."""
    return f"{model_name}_{variant}"


def _get_cache_dir() -> Path:
    """Get the cache directory for Nemo models."""
    try:
        stt_cfg = get_stt_config()
    except Exception:
        stt_cfg = {}
    cache_dir = stt_cfg.get('nemo_cache_dir', './models/nemo')

    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    return cache_path


def load_canary_model():
    """
    Load and cache the Canary-1b model.

    Returns:
        The loaded Canary model instance, or None if loading fails.
    """
    cache_key = _get_model_cache_key('canary', 'standard')

    if cache_key in _model_cache:
        logging.debug(f"Using cached Canary model")
        return _model_cache[cache_key]

    try:
        import nemo.collections.asr as nemo_asr
    except ImportError as e:
        logging.error("Nemo toolkit not installed. Install with: pip install nemo_toolkit[asr]")
        return None

    try:
        logging.info("Loading Canary-1b model from NVIDIA...")

        # Set cache directory for Nemo
        cache_dir = _get_cache_dir()
        os.environ['NEMO_CACHE_DIR'] = str(cache_dir)

        # Load the model
        model = nemo_asr.models.EncDecMultiTaskModel.from_pretrained("nvidia/canary-1b-v2")

        # Configure device
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        try:
            stt_cfg = get_stt_config()
        except Exception:
            stt_cfg = {}
        device = stt_cfg.get('nemo_device', device)

        if device == 'cuda' and torch.cuda.is_available():
            model = model.cuda()
        else:
            model = model.cpu()

        model.eval()

        _model_cache[cache_key] = model
        logging.info(f"Successfully loaded Canary-1b model on {device}")
        return model

    except Exception as e:
        logging.error(f"Failed to load Canary model: {e}")
        return None


def load_parakeet_model(variant: str = 'standard'):
    """
    Load and cache the Parakeet TDT model.

    Args:
        variant: Model variant to load ('standard', 'onnx', 'mlx')

    Returns:
        The loaded Parakeet model instance, or None if loading fails.
    """
    cache_key = _get_model_cache_key('parakeet', variant)

    if cache_key in _model_cache:
        logging.debug(f"Using cached Parakeet model (variant: {variant})")
        return _model_cache[cache_key]

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    try:
        stt_cfg = get_stt_config()
    except Exception:
        stt_cfg = {}
    device = stt_cfg.get('nemo_device', device)

    try:
        if variant == 'onnx':
            return _load_parakeet_onnx(device)
        elif variant == 'mlx':
            return _load_parakeet_mlx()
        else:  # standard
            return _load_parakeet_standard(device)
    except Exception as e:
        logging.error(f"Failed to load Parakeet model (variant: {variant}): {e}")
        return None


def _load_parakeet_standard(device: str):
    """Load standard Nemo Parakeet model."""
    try:
        import nemo.collections.asr as nemo_asr
    except ImportError:
        logging.error("Nemo toolkit not installed. Install with: pip install nemo_toolkit[asr]")
        return None

    logging.info("Loading Parakeet TDT model from NVIDIA...")

    # Set cache directory
    cache_dir = _get_cache_dir()
    os.environ['NEMO_CACHE_DIR'] = str(cache_dir)

    # Load the model
    model = nemo_asr.models.EncDecRNNTBPEModel.from_pretrained("nvidia/parakeet-tdt-0.6b-v3")

    # Configure for efficient inference
    model.change_decoding_strategy(None)  # Use greedy decoding for speed

    if device == 'cuda' and torch.cuda.is_available():
        model = model.cuda()
    else:
        model = model.cpu()

    model.eval()

    cache_key = _get_model_cache_key('parakeet', 'standard')
    _model_cache[cache_key] = model
    logging.info(f"Successfully loaded Parakeet TDT model on {device}")
    return model


def _load_parakeet_onnx(device: str):
    """Load ONNX variant of Parakeet model using proper implementation."""
    try:
        # Import the proper ONNX implementation
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Parakeet_ONNX import (
            load_parakeet_onnx_model
        )

        logging.info("Loading Parakeet TDT ONNX model...")

        # Load model with proper tokenizer
        session, tokenizer = load_parakeet_onnx_model(device=device)

        if session is None or tokenizer is None:
            logging.error("Failed to load ONNX model or tokenizer")
            return None

        # Wrap in a class for consistent interface
        class ONNXParakeetModel:
            def __init__(self, session, tokenizer):
                self.session = session
                self.tokenizer = tokenizer

            def transcribe(self, audio_path, chunk_duration=None, overlap_duration=15.0, chunk_callback=None):
                # Use the proper ONNX transcription
                from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Parakeet_ONNX import (
                    transcribe_with_parakeet_onnx
                )

                result = transcribe_with_parakeet_onnx(
                    audio_path,
                    device=device,
                    chunk_duration=chunk_duration,
                    overlap_duration=overlap_duration,
                    chunk_callback=chunk_callback
                )

                # Return as list for compatibility
                return [result] if result else ["[No transcription produced]"]

        model = ONNXParakeetModel(session, tokenizer)
        cache_key = _get_model_cache_key('parakeet', 'onnx')
        _model_cache[cache_key] = model
        logging.info(f"Successfully loaded Parakeet ONNX model with tokenizer")
        return model

    except ImportError as e:
        logging.error(f"Failed to import ONNX implementation: {e}")
        logging.error("Ensure Audio_Transcription_Parakeet_ONNX.py is available")
        return None
    except Exception as e:
        logging.error(f"Failed to load ONNX model: {e}")
        return None


def _load_parakeet_mlx():
    """Load MLX variant of Parakeet model for Apple Silicon."""
    # Check if we're on macOS with Apple Silicon
    if sys.platform != 'darwin':
        logging.warning("MLX variant is only supported on macOS. Falling back to standard variant.")
        return _load_parakeet_standard('cpu')

    try:
        # Import the specialized MLX implementation
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Parakeet_MLX import (
            load_parakeet_mlx_model,
            check_mlx_available
        )

        if not check_mlx_available():
            logging.warning("MLX not available. Falling back to standard variant.")
            return _load_parakeet_standard('cpu')

        logging.info("Loading Parakeet MLX model using specialized implementation...")
        model = load_parakeet_mlx_model()

        if model is not None:
            cache_key = _get_model_cache_key('parakeet', 'mlx')
            _model_cache[cache_key] = model
            logging.info("Successfully loaded Parakeet MLX model")
            return model
        else:
            logging.warning("Failed to load MLX model. Falling back to standard variant.")
            return _load_parakeet_standard('cpu')

    except ImportError as e:
        logging.warning(f"MLX implementation not available: {e}. Falling back to standard variant.")
        return _load_parakeet_standard('cpu')
    except Exception as e:
        logging.error(f"Error loading Parakeet MLX model: {e}")
        return _load_parakeet_standard('cpu')


#######################################################################################################################
# Transcription Functions
#

def transcribe_with_canary(
    audio_data: Union[np.ndarray, str],
    sample_rate: int = 16000,
    language: Optional[str] = None,
    *,
    task: str = "transcribe",
    target_language: Optional[str] = None,
) -> str:
    """
    Transcribe or translate audio using the Canary-1b-v2 model.

    This helper wraps NeMo's multitask ASR/AST interface and normalizes the
    configuration used across the codebase.

    Args:
        audio_data: Either a numpy array of audio samples or path to audio file
        sample_rate: Sample rate of the audio
        language: Optional source language hint (ISO 639-1 code such as 'en',
            'fr', 'de', 'es', or any of the 25 Canary-supported languages).
            When provided and valid, it is passed as `source_lang` to NeMo.
        task: High-level task, either "transcribe" (default) for same-language
            ASR or "translate" for AST. Any other value is normalized to
            "transcribe".
        target_language: Optional target language code (ISO 639-1). When
            omitted:
              - For task="transcribe", Canary defaults to same-language output
                (target_lang == source_lang when known).
              - For task="translate", the default target is English ("en"),
                matching OpenAI's /audio/translations semantics.

    Returns:
        Transcribed text string
    """
    model = load_canary_model()
    if model is None:
        return "[Error: Canary model could not be loaded]"

    # Normalize task
    task_normalized = (task or "transcribe").strip().lower()
    if task_normalized not in {"transcribe", "translate"}:
        task_normalized = "transcribe"

    # Normalize languages using the Canary-supported set
    source_lang = _normalize_canary_lang(language)
    normalized_target = _normalize_canary_lang(target_language) if target_language else None

    if task_normalized == "transcribe":
        # For pure ASR we keep source and target aligned when possible so the
        # model performs same-language transcription.
        target_lang = normalized_target or source_lang
    else:
        # For AST we aim for cross-lingual output. If no explicit target is
        # provided, we default to English to mirror Whisper's translate mode.
        target_lang = normalized_target or "en"
        # If caller accidentally requests translate-to-same-language, fall back
        # to normal transcription semantics.
        if source_lang and target_lang == source_lang:
            task_normalized = "transcribe"

    # Build language kwargs for NeMo; we only pass values that survived
    # normalization to avoid raising on unsupported codes.
    lang_kwargs: Dict[str, Any] = {}
    if source_lang:
        lang_kwargs["source_lang"] = source_lang
    if target_lang:
        lang_kwargs["target_lang"] = target_lang

    cleanup_temp = False
    audio_path: Optional[str] = None
    audio_source: Union[np.ndarray, str] = audio_data

    def _extract_result(transcriptions):
        if transcriptions and len(transcriptions) > 0:
            result = transcriptions[0]
            if hasattr(result, 'text'):
                result = result.text
            elif not isinstance(result, str):
                result = str(result)
        else:
            result = "[No transcription produced]"
        return result

    if isinstance(audio_data, np.ndarray):
        audio_np = np.asarray(audio_data, dtype=np.float32)
        try:
            transcriptions = model.transcribe([audio_np], batch_size=1, **lang_kwargs)
            return _extract_result(transcriptions)
        except Exception as direct_err:
            logging.debug(f"Canary direct numpy transcription failed, falling back to temp file: {direct_err}")
            audio_path = _temp_wav_from_numpy(audio_np, sample_rate)
            audio_source = audio_path
            cleanup_temp = True

    try:
        # Perform transcription/translation with language hints when available.
        transcriptions = model.transcribe(
            [audio_source],
            batch_size=1,
            **lang_kwargs,
        )

        return _extract_result(transcriptions)

    except Exception as e:
        logging.error(f"Error during Canary transcription: {e}")
        return f"[Transcription error: {str(e)}]"
    finally:
        if cleanup_temp and audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as rm_err:
                logging.debug(f"Failed to remove temp audio file (Canary): path={audio_path}, error={rm_err}")


def transcribe_with_parakeet(
    audio_data: Union[np.ndarray, str],
    sample_rate: int = 16000,
    variant: str = 'standard',
    chunk_duration: Optional[float] = None,
    overlap_duration: float = 15.0,
    chunk_callback: Optional[Callable[[int, int], None]] = None
) -> str:
    """
    Transcribe audio using the Parakeet TDT model.

    Args:
        audio_data: Either a numpy array of audio samples or path to audio file
        sample_rate: Sample rate of the audio
        variant: Model variant to use ('standard', 'onnx', 'mlx')
        chunk_duration: Duration in seconds for chunking long audio (None = no chunking)
        overlap_duration: Overlap between chunks in seconds (default 15.0)
        chunk_callback: Callback function for chunk progress (current, total)

    Returns:
        Transcribed text string
    """
    # Get variant from config if not specified
    if variant == 'auto':
        try:
            stt_cfg = get_stt_config()
        except Exception:
            stt_cfg = {}
        variant = stt_cfg.get('nemo_model_variant', 'standard')

    model = load_parakeet_model(variant)
    if model is None:
        return f"[Error: Parakeet model ({variant}) could not be loaded]"

    cleanup_temp = False
    audio_path: Optional[str] = None
    audio_source: Union[np.ndarray, str] = audio_data

    try:
        # Perform transcription based on variant
        if variant == 'mlx':
            # Use specialized MLX transcription
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Parakeet_MLX import (
                transcribe_with_parakeet_mlx as mlx_transcribe
            )
            result = mlx_transcribe(
                audio_source,
                sample_rate=sample_rate,
                chunk_duration=chunk_duration,
                overlap_duration=overlap_duration,
                chunk_callback=chunk_callback
            )
            transcriptions = [result] if result else ["[No transcription produced]"]
        elif isinstance(audio_source, np.ndarray):
            audio_np = np.asarray(audio_source, dtype=np.float32)
            try:
                transcriptions = model.transcribe(
                    audio_np,
                    chunk_duration=chunk_duration,
                    overlap_duration=overlap_duration,
                    chunk_callback=chunk_callback
                )
            except Exception as direct_err:
                logging.debug(f"Parakeet direct numpy transcription failed, falling back to temp file: {direct_err}")
                audio_path = _temp_wav_from_numpy(audio_np, sample_rate)
                audio_source = audio_path
                cleanup_temp = True
                transcriptions = model.transcribe(
                    audio_source,
                    chunk_duration=chunk_duration,
                    overlap_duration=overlap_duration,
                    chunk_callback=chunk_callback
                )
        else:
            transcriptions = model.transcribe(
                audio_source,
                chunk_duration=chunk_duration,
                overlap_duration=overlap_duration,
                chunk_callback=chunk_callback
            )

        if transcriptions and len(transcriptions) > 0:
            result = transcriptions[0]
            # Handle Hypothesis objects from Nemo
            if hasattr(result, 'text'):
                result = result.text
            elif not isinstance(result, str):
                result = str(result)
        else:
            result = "[No transcription produced]"

        return result

    except Exception as e:
        logging.error(f"Error during Parakeet transcription: {e}")
        return f"[Transcription error: {str(e)}]"
    finally:
        if cleanup_temp and audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as rm_err:
                logging.debug(f"Failed to remove temp audio file (Parakeet): path={audio_path}, error={rm_err}")


def transcribe_with_nemo(
    audio_data: Union[np.ndarray, str],
    sample_rate: int = 16000,
    model: str = 'parakeet',
    variant: str = 'standard',
    language: Optional[str] = None,
    chunk_duration: Optional[float] = None,
    overlap_duration: float = 15.0,
    chunk_callback: Optional[Callable[[int, int], None]] = None
) -> str:
    """
    Unified entry point for Nemo model transcription.

    Args:
        audio_data: Either a numpy array of audio samples or path to audio file
        sample_rate: Sample rate of the audio
        model: Which model to use ('parakeet' or 'canary')
        variant: Model variant for Parakeet ('standard', 'onnx', 'mlx')
        language: Source language hint for Canary (any Canary-supported ISO
            639-1 code) or None to rely on model defaults. For Parakeet this
            parameter is currently ignored.
        chunk_duration: Duration in seconds for chunking long audio (None = no chunking)
        overlap_duration: Overlap between chunks in seconds (default 15.0)
        chunk_callback: Callback function for chunk progress (current, total)

    Returns:
        Transcribed text string
    """
    if model.lower() == 'canary':
        # Note: Canary doesn't support chunking in current implementation
        return transcribe_with_canary(audio_data, sample_rate, language)
    elif model.lower() == 'parakeet':
        return transcribe_with_parakeet(
            audio_data, sample_rate, variant,
            chunk_duration=chunk_duration,
            overlap_duration=overlap_duration,
            chunk_callback=chunk_callback
        )
    else:
        return f"[Error: Unknown Nemo model: {model}]"


def unload_nemo_models():
    """Unload all cached Nemo models to free memory."""
    global _model_cache

    for key, model in _model_cache.items():
        try:
            # Try to free GPU memory if applicable
            if hasattr(model, 'cpu'):
                model.cpu()
            del model
        except Exception as free_err:
            logging.debug(f"Failed to release Nemo model resources: key={key}, error={free_err}")

    _model_cache.clear()

    # Force garbage collection
    import gc
    gc.collect()

    # Clear GPU cache if available
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    logging.info("Unloaded all Nemo models from memory")


#######################################################################################################################
# End of Audio_Transcription_Nemo.py
#######################################################################################################################
