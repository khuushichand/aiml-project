# diarization_service.py
"""
Speaker diarization service for tldw_chatbook.
Implements speaker identification using vector embeddings approach.
"""
#
# Imports
import os
import sys
import time
import threading
from functools import lru_cache
import importlib.util
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Callable, Tuple, TYPE_CHECKING, TypedDict
import json
#
# 3rd-Party Libraries
from loguru import logger
from contextlib import contextmanager
from enum import Enum
#
# Local Imports
from tldw_Server_API.app.core.config import loaded_config_data
#
######################################################################################################################
# Type checking imports (not loaded at runtime)
if TYPE_CHECKING:
    import numpy as np
    import torch


# Module availability probes (evaluated lazily to avoid heavy imports during test collection)

@lru_cache(maxsize=1)
def _module_spec_available(module_name: str) -> bool:
    """Best-effort probe using importlib without importing heavy modules."""
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception as exc:  # pragma: no cover - defensive logging
        try:
            logger.debug(f"Module spec probe failed for {module_name}: {exc}")
        except Exception:
            pass
        return False


@lru_cache(maxsize=1)
def _torch_available() -> bool:
    if not _module_spec_available("torch"):
        logger.debug("PyTorch not installed or not discoverable.")
        return False
    try:
        import torch  # type: ignore  # noqa: F401
        return True
    except Exception as exc:  # pragma: no cover - import error surfaces once
        logger.debug(f"PyTorch import failed: {exc}")
        return False


@lru_cache(maxsize=1)
def _torchaudio_available() -> bool:
    if not _module_spec_available("torchaudio"):
        logger.debug("TorchAudio not installed or not discoverable.")
        return False
    try:
        import torchaudio  # type: ignore  # noqa: F401
        return True
    except Exception as exc:  # pragma: no cover - import error surfaces once
        logger.debug(f"TorchAudio import failed: {exc}")
        return False


@lru_cache(maxsize=1)
def _speechbrain_available() -> bool:
    # Avoid importing heavy modules if prerequisites are clearly missing.
    if not _module_spec_available("speechbrain"):
        logger.debug("SpeechBrain not installed or not discoverable.")
        return False
    if not _torchaudio_available():
        logger.debug("TorchAudio missing; SpeechBrain disabled.")
        return False
    try:
        import speechbrain  # type: ignore  # noqa: F401
        return True
    except Exception as exc:  # pragma: no cover - import error surfaces once
        logger.debug(f"SpeechBrain import failed: {exc}")
        return False


@lru_cache(maxsize=1)
def _sklearn_available() -> bool:
    if not _module_spec_available("sklearn"):
        logger.debug("scikit-learn not installed or not discoverable.")
        return False
    try:
        import sklearn  # type: ignore  # noqa: F401
        return True
    except Exception as exc:  # pragma: no cover - import error surfaces once
        logger.debug(f"scikit-learn import failed: {exc}")
        return False

# Lazy-loaded modules (will be imported only when needed)
_torch = None
_numpy = None
_silero_vad_model = None
_silero_vad_utils = None
_speechbrain_encoder = None
_sklearn_modules = None
_torchaudio = None


# Enums and Constants
class ClusteringMethod(Enum):
    """Clustering methods for speaker identification."""
    SPECTRAL = 'spectral'
    AGGLOMERATIVE = 'agglomerative'


class EmbeddingDevice(Enum):
    """Device options for embedding model."""
    AUTO = 'auto'
    CPU = 'cpu'
    CUDA = 'cuda'


class SegmentDict(TypedDict, total=False):
    """Type definition for segment dictionaries."""
    start: float
    end: float
    waveform: Any  # torch.Tensor
    speaker_id: Optional[int]
    speaker_label: Optional[str]
    is_padded: bool
    original_duration: float
    speech_region: Dict[str, Any]
    # Memory-efficient fields
    start_sample: Optional[int]
    end_sample: Optional[int]
    waveform_ref: Optional[Any]  # Reference to original waveform instead of copy


class DiarizationResult(TypedDict):
    """Type definition for diarization results."""
    segments: List[Dict[str, Any]]
    speakers: List[Dict[str, Any]]
    duration: float
    num_speakers: int
    processing_time: float


# Constants
DEFAULT_VAD_THRESHOLD = 0.5
DEFAULT_SEGMENT_DURATION = 2.0
DEFAULT_SEGMENT_OVERLAP = 0.5
DEFAULT_MIN_SPEAKERS = 1
DEFAULT_MAX_SPEAKERS = 10
DEFAULT_SIMILARITY_THRESHOLD = 0.85
DEFAULT_EMBEDDING_BATCH_SIZE = 32
DEFAULT_EMBEDDING_MODEL = 'speechbrain/spkrec-ecapa-voxceleb'
SPEAKER_LABEL_PREFIX = 'SPEAKER_'
# Memory-efficient mode constants
DEFAULT_MEMORY_EFFICIENT = False
DEFAULT_MAX_MEMORY_MB = 2048  # 2GB default memory limit


def _sanitize_path_component(name: str) -> str:
    """Sanitize a string to be safe for use as a directory/file name.

    Args:
        name: The string to sanitize

    Returns:
        A sanitized string safe for use in file paths
    """
    # Replace path separators and other unsafe characters
    safe_name = name.replace('/', '_').replace('\\', '_').replace(':', '_')
    safe_name = safe_name.replace('..', '_')  # Prevent directory traversal

    # Keep only alphanumeric, underscore, hyphen, and dot
    safe_name = ''.join(c if c.isalnum() or c in ('_', '-', '.') else '_' for c in safe_name)

    # Remove leading/trailing dots and underscores
    safe_name = safe_name.strip('._')

    # Ensure it's not empty
    if not safe_name:
        safe_name = 'model'

    return safe_name


def _lazy_import_torch():
    """Lazy import torch."""
    global _torch
    if _torch is None and _torch_available():
        try:
            import torch
            _torch = torch
        except ImportError as e:
            logger.warning(f"Failed to import torch: {e}")
            _torch = None
    return _torch


def _lazy_import_numpy():
    """Lazy import numpy."""
    global _numpy
    if _numpy is None:
        try:
            import numpy
            _numpy = numpy
        except ImportError:
            logger.warning("NumPy not available")
            return None
    return _numpy


def _lazy_import_silero_vad():
    """
    Load and cache the Silero VAD model and its utility functions from the torch hub.

    This function configures a torch hub cache directory (derived from TORCH_HOME or TORCH_HUB), attempts to load the Silero VAD package via torch.hub.load, validates the returned (model, utils) tuple, and stores them in module-level cache variables for reuse. On failure the cache is left unset and the function returns (None, None).

    Returns:
        tuple: `(model, utils)` on success where `utils` is a sequence whose first five items are, in order, `get_speech_timestamps`, `save_audio`, `read_audio`, `VADIterator`, and `collect_chunks`; `(None, None)` if loading or validation fails.
    """
    global _silero_vad_model, _silero_vad_utils

    # Check if already loaded
    if _silero_vad_model is not None:
        return _silero_vad_model, _silero_vad_utils

    # Check torch availability
    if not _torch_available():
        logger.warning("PyTorch not available, cannot load Silero VAD")
        return None, None

    torch = _lazy_import_torch()
    if not torch:
        logger.warning("Failed to import torch for Silero VAD")
        return None, None

    try:
        logger.info("Loading Silero VAD model from torch hub...")

        # Configure torch hub cache directory
        # Prefer TORCH_HOME (root), fallback to default; allow explicit TORCH_HUB as hub dir
        default_home_dir = Path.home() / '.cache' / 'torch'
        torch_home = Path(os.environ.get('TORCH_HOME', str(default_home_dir)))
        # If TORCH_HUB is set, treat it as explicit hub dir; otherwise derive from TORCH_HOME
        hub_dir = Path(os.environ.get('TORCH_HUB', str(torch_home / 'hub')))
        hub_dir.mkdir(parents=True, exist_ok=True)
        try:
            # Ensure torch uses the directory we just created
            if hasattr(torch, 'hub') and hasattr(torch.hub, 'set_dir'):
                torch.hub.set_dir(str(hub_dir))
        except Exception as _hub_dir_err:  # pragma: no cover - best-effort
            logger.debug(f"torch.hub.set_dir failed: {_hub_dir_err}")

        # Load model with explicit parameters
        result = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,  # Use cached version if available
            trust_repo=True,  # Required for loading
            verbose=False  # Reduce output noise
        )

        # Validate the result format
        if not isinstance(result, (tuple, list)) or len(result) != 2:
            logger.error(
                f"Unexpected Silero VAD return format. Expected (model, utils) tuple, "
                f"got {type(result).__name__} with length {len(result) if hasattr(result, '__len__') else 'unknown'}"
            )
            return None, None

        model, utils = result

        # Validate model
        if model is None:
            logger.error("Silero VAD model is None")
            return None, None

        # Validate utils format
        if not isinstance(utils, (tuple, list)) or len(utils) < 5:
            logger.error(
                f"Unexpected Silero VAD utils format. Expected tuple/list with 5+ items, "
                f"got {type(utils).__name__} with {len(utils) if hasattr(utils, '__len__') else 'unknown'} items"
            )
            return None, None

        # Store globally for future use
        _silero_vad_model = model
        _silero_vad_utils = utils

        logger.info("Silero VAD loaded successfully")
        logger.debug(f"Silero VAD utils count: {len(utils)}")

        return model, utils

    except Exception as e:
        logger.error(f"Failed to load Silero VAD: {type(e).__name__}: {e}")
        logger.debug("Full error:", exc_info=True)

        # Reset globals on failure
        _silero_vad_model = None
        _silero_vad_utils = None

        return None, None


def _lazy_import_speechbrain():
    """Lazy import SpeechBrain encoder."""
    global _speechbrain_encoder
    if _speechbrain_encoder is None and _speechbrain_available():
        try:
            from speechbrain.inference.speaker import EncoderClassifier
            _speechbrain_encoder = EncoderClassifier
        except ImportError:
            try:
                # Fallback for older versions
                from speechbrain.pretrained import EncoderClassifier
                _speechbrain_encoder = EncoderClassifier
            except ImportError as e:
                logger.warning(f"Failed to import SpeechBrain EncoderClassifier: {e}")
                _speechbrain_encoder = None
    return _speechbrain_encoder


def _lazy_import_sklearn():
    """Lazy import sklearn modules."""
    global _sklearn_modules
    if _sklearn_modules is None and _sklearn_available():
        try:
            from sklearn.cluster import SpectralClustering, AgglomerativeClustering
            from sklearn.preprocessing import normalize
            from sklearn.metrics import silhouette_score
            from sklearn.metrics.pairwise import cosine_similarity
            _sklearn_modules = {
                'SpectralClustering': SpectralClustering,
                'AgglomerativeClustering': AgglomerativeClustering,
                'normalize': normalize,
                'silhouette_score': silhouette_score,
                'cosine_similarity': cosine_similarity
            }
        except ImportError as e:
            logger.warning(f"Failed to import sklearn modules: {e}")
            _sklearn_modules = None
    return _sklearn_modules


def _lazy_import_torchaudio():
    """Lazy import torchaudio."""
    global _torchaudio
    if _torchaudio is None and _torchaudio_available():
        try:
            import torchaudio
            _torchaudio = torchaudio
        except ImportError as e:
            logger.warning(f"Failed to import torchaudio: {e}")
            _torchaudio = None
    return _torchaudio


class DiarizationError(Exception):
    """Base exception for diarization errors."""
    pass


class DiarizationService:
    """
    Speaker diarization service using vector embeddings approach.

    Pipeline:
    1. Voice Activity Detection (VAD) to find speech segments
    2. Split speech into fixed-length overlapping segments
    3. Extract speaker embeddings for each segment
    4. Cluster embeddings to identify speakers
    5. Merge consecutive segments from same speaker

    Attributes:
        is_available (bool): Whether all required dependencies are available.
                           Can be accessed directly or via is_diarization_available().
        config (dict): Configuration parameters for diarization.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 config_loader: Optional[Callable[[], Dict[str, Any]]] = None):
        """Initialize the diarization service.

        Args:
            config: Optional configuration override
            config_loader: Optional configuration loader function
        """
        logger.info("Initializing DiarizationService...")

        # Use provided config loader or default
        if config_loader is None:
            config_loader = self._default_config_loader

        # Load configuration
        self.config = config_loader()

        # Override with provided config
        if config:
            self.config.update(config)

    async def propose_human_edit_boundaries(
        self,
        transcript_entries: List[Dict[str, Any]],
        K: int = 6,
        min_segment_size: int = 5,
        lambda_balance: float = 0.01,
        utterance_expansion_width: int = 2,
        embeddings_provider: Optional[str] = None,
        embeddings_model: Optional[str] = None,
        embedder: Optional[Callable[[List[str]], Any]] = None,
    ) -> Dict[str, Any]:
        """
        Propose segment boundaries for human editing using TreeSeg on transcript entries.

        Args:
            transcript_entries: List of utterance dicts. Each must include 'composite'.
            K: Maximum number of segments to produce.
            min_segment_size: Minimum number of items per segment.
            lambda_balance: Balance penalty coefficient.
            utterance_expansion_width: Number of prior utterances to concatenate per block.
            embeddings_provider: Optional provider for embedding service (if not using embedder).
            embeddings_model: Optional model for embedding service.
            embedder: Optional async callable for embeddings; overrides provider/model.

        Returns:
            Dict with 'transitions' vector and 'segments' list (indices, times, speakers, text).
        """
        try:
            # Import lazily to avoid heavy imports on module load
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Transcript_TreeSegmentation import (
                TreeSegmenter,
            )

            configs = {
                "MIN_SEGMENT_SIZE": int(min_segment_size),
                "LAMBDA_BALANCE": float(lambda_balance),
                "UTTERANCE_EXPANSION_WIDTH": int(utterance_expansion_width),
            }

            if embeddings_provider:
                configs["EMBEDDINGS_PROVIDER"] = embeddings_provider
            if embeddings_model:
                configs["EMBEDDINGS_MODEL"] = embeddings_model

            segmenter = await TreeSegmenter.create_async(
                configs=configs,
                entries=transcript_entries,
                embedder=embedder,
            )
            transitions = segmenter.segment_meeting(K=K)
            segments = segmenter.get_segments()

            return {
                "transitions": transitions,
                "segments": segments,
            }

        except Exception as e:
            logger.error(f"Failed to propose edit boundaries: {e}")
            raise

        logger.debug(f"Diarization service configuration: {self.config}")

        # Validate configuration
        self._validate_config(self.config)

        # Model storage (lazy loaded)
        self._vad_model = None
        self._vad_utils = None
        self._embedding_model = None
        self._model_lock = threading.RLock()

        # Check availability (without importing)
        # Public attribute - can be accessed directly by callers
        self.is_available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if all required dependencies are available."""
        required = [
            (_torch_available(), "PyTorch"),
            (_speechbrain_available(), "SpeechBrain"),
            (_sklearn_available(), "scikit-learn"),
        ]

        missing = [name for available, name in required if not available]
        if missing:
            logger.warning(f"Diarization unavailable. Missing: {', '.join(missing)}")
            return False

        return True

    def _get_default_config(self) -> Dict[str, Any]:
        """
        Provide the default configuration dictionary used by DiarizationService.

        Returns:
            dict: Mapping of configuration option names to their default values. Main keys include:
                - vad_threshold: float threshold for voice activity detection.
                - vad_min_speech_duration: minimum speech duration (seconds) to consider as speech.
                - vad_min_silence_duration: minimum silence duration (seconds) used by VAD.
                - allow_vad_fallback: allow a full-span fallback region if VAD is unavailable or fails.
                - enable_torch_hub_fetch: allow fetching Silero VAD from torch.hub when not cached.
                - segment_duration: target segment length (seconds).
                - segment_overlap: overlap between consecutive segments (seconds).
                - min_segment_duration / max_segment_duration: bounds for created segments (seconds).
                - embedding_model: pretrained embedding model identifier.
                - embedding_device: device selection for embeddings (AUTO/CPU/CUDA).
                - embedding_local_only: require local embedding files when True.
                - clustering_method: clustering algorithm to use (SPECTRAL/AGGLOMERATIVE).
                - similarity_threshold: similarity cutoff used for single-speaker detection.
                - min_speakers / max_speakers: allowed speaker count bounds for clustering.
                - merge_threshold: maximum gap (seconds) to merge adjacent same-speaker segments.
                - min_speaker_duration: minimum total duration (seconds) for a speaker to be kept.
                - embedding_batch_size: number of segments processed per embedding batch.
                - memory_efficient: enable memory-efficient mode for waveform handling.
                - max_memory_mb: memory budget in megabytes when memory_efficient is enabled.
                - detect_overlapping_speech: enable overlapping-speech detection post-processing.
                - overlap_confidence_threshold: confidence threshold for marking overlaps.
        """
        return {
            # VAD settings
            'vad_threshold': DEFAULT_VAD_THRESHOLD,
            'vad_min_speech_duration': 0.25,
            'vad_min_silence_duration': 0.25,
            # Allow fallback when VAD unavailable (e.g., no network/cache)
            'allow_vad_fallback': True,
            # Allow torch.hub to fetch Silero VAD when not cached (set False to fail fast)
            'enable_torch_hub_fetch': True,

            # Segmentation settings
            'segment_duration': DEFAULT_SEGMENT_DURATION,
            'segment_overlap': DEFAULT_SEGMENT_OVERLAP,
            'min_segment_duration': 1.0,
            'max_segment_duration': 3.0,

            # Embedding model
            'embedding_model': DEFAULT_EMBEDDING_MODEL,
            'embedding_device': EmbeddingDevice.AUTO.value,
            'embedding_local_only': False,  # If True, do not download; require local model files

            # Clustering settings
            'clustering_method': ClusteringMethod.SPECTRAL.value,
            'similarity_threshold': DEFAULT_SIMILARITY_THRESHOLD,
            'min_speakers': DEFAULT_MIN_SPEAKERS,
            'max_speakers': DEFAULT_MAX_SPEAKERS,

            # Post-processing
            'merge_threshold': 0.5,
            'min_speaker_duration': 3.0,

            # Batch processing
            'embedding_batch_size': DEFAULT_EMBEDDING_BATCH_SIZE,

            # Memory-efficient mode
            'memory_efficient': DEFAULT_MEMORY_EFFICIENT,
            'max_memory_mb': DEFAULT_MAX_MEMORY_MB,

            # Overlapping speech detection
            'detect_overlapping_speech': False,
            'overlap_confidence_threshold': 0.7,
        }

    def _default_config_loader(self) -> Dict[str, Any]:
        """Default configuration loader using loaded_config_data."""
        default_config = self._get_default_config()

        # Override with settings from config file if available
        if loaded_config_data:
            diarization_config = loaded_config_data.get('diarization', {})
            config = {**default_config, **diarization_config}
        else:
            config = default_config

        return config

    def _validate_config(self, config: Dict) -> None:
        """Validate configuration parameters.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If configuration is invalid
        """
        # VAD settings validation
        if config['vad_threshold'] < 0 or config['vad_threshold'] > 1:
            raise ValueError("vad_threshold must be between 0 and 1")

        if config['vad_min_speech_duration'] < 0:
            raise ValueError("vad_min_speech_duration must be non-negative")

        if config['vad_min_silence_duration'] < 0:
            raise ValueError("vad_min_silence_duration must be non-negative")

        # Segmentation settings validation
        if config['segment_overlap'] >= config['segment_duration']:
            raise ValueError("segment_overlap must be less than segment_duration")

        if config['segment_overlap'] < 0:
            raise ValueError("segment_overlap must be non-negative")

        if config['min_segment_duration'] > config['max_segment_duration']:
            raise ValueError("min_segment_duration must be <= max_segment_duration")

        if config['segment_duration'] > config['max_segment_duration']:
            raise ValueError("segment_duration must be <= max_segment_duration")

        # Clustering settings validation
        if config['min_speakers'] < 1:
            raise ValueError("min_speakers must be at least 1")

        if config['max_speakers'] < config['min_speakers']:
            raise ValueError("max_speakers must be >= min_speakers")

        if config['similarity_threshold'] < 0 or config['similarity_threshold'] > 1:
            raise ValueError("similarity_threshold must be between 0 and 1")

        # Post-processing validation
        if config['merge_threshold'] < 0:
            raise ValueError("merge_threshold must be non-negative")

        if config['min_speaker_duration'] < 0:
            raise ValueError("min_speaker_duration must be non-negative")

        # Batch processing validation
        if config['embedding_batch_size'] < 1:
            raise ValueError("embedding_batch_size must be at least 1")

        # Embedding device validation
        valid_devices = [e.value for e in EmbeddingDevice]
        if config['embedding_device'] not in valid_devices:
            raise ValueError(f"embedding_device must be one of {valid_devices}")

        # Clustering method validation
        valid_methods = [m.value for m in ClusteringMethod]
        if config['clustering_method'] not in valid_methods:
            raise ValueError(f"clustering_method must be one of {valid_methods}")

    def _get_device(self) -> str:
        """Determine the device to use for inference."""
        if self.config['embedding_device'] == EmbeddingDevice.AUTO.value:
            torch = _lazy_import_torch()
            if torch:
                try:
                    if hasattr(torch, 'cuda') and torch.cuda.is_available():
                        return EmbeddingDevice.CUDA.value
                except (AttributeError, RuntimeError) as e:
                    logger.debug(f"Error checking CUDA availability: {e}")
            return EmbeddingDevice.CPU.value
        return self.config['embedding_device']

    def _load_embedding_model(self):
        """
        Load and cache the speaker embedding model according to the current configuration.

        This method ensures a SpeechBrain EncoderClassifier is initialized and stored on the service instance for reuse. It selects the device from the service configuration, prefers a local model path or cached model directory when available, and enforces local-only mode if configured (raising DiarizationError when local files are required but missing). On failure to obtain or initialize the model it raises DiarizationError.
        """
        with self._model_lock:
            if self._embedding_model is None:
                logger.info(f"Loading embedding model: {self.config['embedding_model']}")
                try:
                    EncoderClassifier = _lazy_import_speechbrain()
                    if not EncoderClassifier:
                        raise DiarizationError("SpeechBrain EncoderClassifier not available")

                    device = self._get_device()
                    # Sanitize model name for safe directory creation
                    model_name = self.config['embedding_model']
                    safe_model_name = _sanitize_path_component(model_name)

                    # Use pathlib for path construction
                    model_dir = Path('pretrained_models') / safe_model_name
                    model_dir.mkdir(parents=True, exist_ok=True)

                    # Local-only behavior: never fetch from network; require local files
                    local_only = bool(self.config.get('embedding_local_only', False))
                    local_source: Optional[Path] = None
                    # If user provided a path that exists, prefer it
                    candidate_path = Path(model_name)
                    if candidate_path.exists():
                        local_source = candidate_path
                    elif model_dir.exists() and any(model_dir.iterdir()):
                        # Use pre-populated cache directory
                        local_source = model_dir

                    if local_only:
                        if not local_source:
                            raise DiarizationError(
                                "Embedding model files not found locally. "
                                "Set embedding_local_only=false to allow download or provide a local path in embedding_model."
                            )
                        self._embedding_model = EncoderClassifier.from_hparams(
                            source=str(local_source),
                            savedir=str(local_source),
                            run_opts={"device": device}
                        )
                    else:
                        # Allow download/resolve from repo string, but cache under model_dir
                        self._embedding_model = EncoderClassifier.from_hparams(
                            source=model_name,
                            savedir=str(model_dir),
                            run_opts={"device": device}
                        )
                    logger.info(f"Embedding model loaded successfully on {device}")
                except Exception as e:
                    logger.error(f"Failed to load embedding model: {e}")
                    raise DiarizationError(f"Failed to load embedding model: {e}") from e

    def _load_vad_model(self):
        """
        Load and validate the Silero voice-activity-detection (VAD) model and its utilities into the instance.

        This method lazy-loads the Silero VAD model and maps its returned utilities into self._vad_model and a dict self._vad_utils with keys
        'get_speech_timestamps', 'save_audio', 'read_audio', 'VADIterator', and 'collect_chunks'. It validates the utilities' presence and
        that each utility is callable (except 'VADIterator', which is expected to be a class). Loading may be skipped when the configuration
        flag 'enable_torch_hub_fetch' is False.

        Raises:
            DiarizationError: If loading or validation fails, or if torch hub fetch is disabled by configuration.
        """
        with self._model_lock:  # Add thread safety
            if self._vad_model is None:
                try:
                    # Optionally prevent torch.hub fetching for locked-down environments
                    if not bool(self.config.get('enable_torch_hub_fetch', True)):
                        raise DiarizationError(
                            "Silero VAD load skipped: enable_torch_hub_fetch is False"
                        )
                    model, utils = _lazy_import_silero_vad()
                    if not model or not utils:
                        raise DiarizationError("Silero VAD model or utilities not available")

                    # Basic validation - detailed validation already done in _lazy_import_silero_vad
                    if not utils:
                        raise DiarizationError("Silero VAD utilities not available")

                    # Store model
                    self._vad_model = model

                    # Map utilities with extensive validation
                    # NOTE: This mapping is fragile and depends on Silero's return order
                    try:
                        self._vad_utils = {
                            'get_speech_timestamps': utils[0],  # Main VAD function
                            'save_audio': utils[1],  # Audio saving utility
                            'read_audio': utils[2],  # Audio loading utility
                            'VADIterator': utils[3],  # Streaming VAD class
                            'collect_chunks': utils[4]  # Chunk collection utility
                        }

                        # Validate that each utility is callable (except VADIterator which is a class)
                        for name, func in self._vad_utils.items():
                            if name != 'VADIterator' and not callable(func):
                                raise DiarizationError(f"VAD utility '{name}' is not callable")

                        logger.debug("VAD utilities loaded and validated successfully")

                    except (IndexError, TypeError) as e:
                        raise DiarizationError(
                            f"Failed to map Silero VAD utilities. The utility order may have changed. Error: {e}"
                        ) from e

                except Exception as e:
                    logger.error(f"Failed to load VAD model: {e}")
                    self._vad_model = None
                    self._vad_utils = None
                    raise DiarizationError(f"Failed to load Silero VAD model: {e}") from e

    def _get_vad_utility(self, name: str) -> Callable:
        """Safely get a VAD utility function with validation.

        Args:
            name: Name of the utility ('get_speech_timestamps', 'read_audio', etc.)

        Returns:
            The utility function

        Raises:
            DiarizationError: If utility is not available or not callable
        """
        if not self._vad_utils:
            raise DiarizationError("VAD utilities not loaded")

        if name not in self._vad_utils:
            raise DiarizationError(
                f"VAD utility '{name}' not found. Available: {list(self._vad_utils.keys())}"
            )

        utility = self._vad_utils[name]

        # Special case for VADIterator which is a class, not a function
        if name == 'VADIterator':
            return utility

        if not callable(utility):
            raise DiarizationError(
                f"VAD utility '{name}' is not callable. Got type: {type(utility).__name__}"
            )

        return utility

    def diarize(
            self,
            audio_path: str,
            transcription_segments: Optional[List[Dict]] = None,
            num_speakers: Optional[int] = None,
            progress_callback: Optional[Callable[[float, str, Optional[Dict]], None]] = None
    ) -> Dict[str, Any]:
        """
            Perform speaker diarization for an audio file and return time-aligned segments with speaker assignments.

            This method runs voice-activity detection, creates analysis segments, extracts speaker embeddings, clusters segments into speakers, optionally detects overlapping speech, merges adjacent segments for the same speaker, and optionally aligns results to provided transcription segments.

            Parameters:
                audio_path: Path to the input audio file. Prefer a 16 kHz mono WAV for best results; common audio formats will be converted when possible.
                transcription_segments: Optional list of transcription segment dictionaries to align diarization output to; if provided, aligned segments will inherit timestamps/text from these entries with speaker assignments applied.
                num_speakers: Optional fixed number of speakers to force; when omitted the service will estimate the speaker count within configured min/max limits.
                progress_callback: Optional callable invoked with progress updates: (progress_percent: float, message: str, metadata: Optional[dict]). Metadata (when provided) may include final 'num_speakers' and 'duration'.

            Returns:
                A dictionary with diarization results:
                    - 'segments': list of segment dictionaries (each includes start, end, speaker_id, speaker_label and related metadata).
                    - 'speakers': list of per-speaker statistics dictionaries (total_time, segment_count, first_appearance, last_appearance, etc.).
                    - 'duration': audio duration in seconds.
                    - 'num_speakers': number of unique speakers identified.
                    - 'processing_time': wall-clock time in seconds spent performing diarization.

            Raises:
                DiarizationError: If required dependencies are missing or an error occurs during processing.
            """
        if not self.is_available:
            raise DiarizationError("Diarization service is not available due to missing dependencies")

        start_time = time.time()
        logger.info(f"Starting diarization for: {audio_path}")

        try:
            # Load audio
            if progress_callback:
                progress_callback(0, "Loading audio file...", None)

            waveform = self._load_audio(audio_path)
            sample_rate = 16000  # Assuming 16kHz as standard

            # Step 1: Voice Activity Detection
            if progress_callback:
                progress_callback(10, "Detecting speech segments...", None)

            # Use streaming VAD if memory-efficient mode is enabled
            streaming_vad = self.config.get('memory_efficient', False)
            speech_timestamps = self._detect_speech(waveform, sample_rate, streaming=streaming_vad)
            logger.debug(f"Found {len(speech_timestamps)} speech segments")

            if not speech_timestamps:
                logger.warning("No speech detected in audio")
                return {
                    'segments': [],
                    'speakers': [],
                    'duration': len(waveform) / sample_rate,
                    'num_speakers': 0
                }

            # Step 2: Create overlapping segments
            if progress_callback:
                progress_callback(20, "Creating analysis segments...", None)

            segments = self._create_segments(waveform, speech_timestamps, sample_rate)
            logger.debug(f"Created {len(segments)} analysis segments")

            # Step 3: Extract embeddings
            if progress_callback:
                progress_callback(30, "Extracting speaker embeddings...", None)

            embeddings = self._extract_embeddings(segments, progress_callback)
            logger.debug(f"Extracted {len(embeddings)} embeddings")

            # Step 4: Determine speakers (fast path for single-speaker)
            if progress_callback:
                progress_callback(70, "Clustering speakers...", None)

            if num_speakers == 1:
                np = _lazy_import_numpy()
                if not np:
                    raise DiarizationError("NumPy not available for single-speaker labeling")
                speaker_labels = np.zeros(len(embeddings), dtype=int)
            else:
                speaker_labels = self._cluster_speakers(
                    embeddings,
                    num_speakers=num_speakers
                )

            # Count unique speakers
            unique_speakers = len(set(speaker_labels))
            logger.info(f"Identified {unique_speakers} speakers")

            # Step 5: Assign speakers to segments
            for segment, label in zip(segments, speaker_labels):
                segment['speaker_id'] = int(label)
                segment['speaker_label'] = f"{SPEAKER_LABEL_PREFIX}{label}"

            # Step 5b: Detect overlapping speech (if configured)
            if self.config.get('detect_overlapping_speech', False):
                if progress_callback:
                    progress_callback(75, "Detecting overlapping speech...", None)

                segments = self._detect_overlapping_speech(segments, embeddings, speaker_labels)

            # Step 6: Merge consecutive segments
            if progress_callback:
                progress_callback(85, "Merging segments...", None)

            merged_segments = self._merge_segments(segments)

            # Step 7: Align with transcription if provided
            if transcription_segments:
                if progress_callback:
                    progress_callback(90, "Aligning with transcription...", None)

                aligned_segments = self._align_with_transcription(
                    merged_segments,
                    transcription_segments
                )
            else:
                aligned_segments = merged_segments

            # Calculate speaker statistics
            speaker_stats = self._calculate_speaker_stats(aligned_segments)

            duration = time.time() - start_time
            logger.info(f"Diarization completed in {duration:.2f} seconds")

            if progress_callback:
                progress_callback(100, "Diarization complete", {
                    'num_speakers': unique_speakers,
                    'duration': duration
                })

            result: DiarizationResult = {
                'segments': aligned_segments,
                'speakers': speaker_stats,
                'duration': len(waveform) / sample_rate,
                'num_speakers': unique_speakers,
                'processing_time': duration
            }
            return result

        except Exception as e:
            logger.error(f"Diarization failed: {e}", exc_info=True)
            raise DiarizationError(f"Diarization failed: {str(e)}") from e

    def _load_audio(self, audio_path: str):
        """
        Load an audio file and return a mono waveform sampled at 16 kHz.

        Tries to load using torchaudio (converting multi-channel audio to mono and resampling to 16 kHz if needed). If torchaudio is unavailable or fails, falls back to the Silero VAD `read_audio` utility. Raises DiarizationError if neither loader can produce a valid waveform.

        Returns:
            A 1-D tensor or array of audio samples resampled to 16 kHz.

        Raises:
            DiarizationError: If audio cannot be loaded by either torchaudio or Silero VAD.
        """
        torchaudio = _lazy_import_torchaudio()
        torch = _lazy_import_torch()

        if torchaudio and torch:
            try:
                waveform, sample_rate = torchaudio.load(audio_path)
                # Convert to mono if stereo
                if waveform.shape[0] > 1:
                    waveform = torch.mean(waveform, dim=0, keepdim=True)
                # Resample to 16kHz if needed
                if sample_rate != 16000:
                    resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                    waveform = resampler(waveform)
                return waveform.squeeze()
            except Exception as e:
                logger.warning(f"Failed to load audio with torchaudio: {e}")
                # Fall through to Silero VAD fallback
        else:
            # Fallback to read_audio from Silero VAD utilities
            logger.info("Falling back to Silero VAD read_audio function")

            # Ensure VAD utilities are loaded
            if not self._vad_utils:
                try:
                    self._load_vad_model()
                except Exception as e:
                    logger.error(f"Failed to load VAD model for audio reading: {e}")
                    raise DiarizationError(f"Cannot load audio: VAD model load failed: {e}") from e

            # Validate read_audio function exists and is callable
            if not self._vad_utils or 'read_audio' not in self._vad_utils:
                raise DiarizationError(
                    "VAD utilities missing 'read_audio' function. "
                    "Neither torchaudio nor Silero VAD audio loading available."
                )

            # Get read_audio function using safe getter
            read_audio = self._get_vad_utility('read_audio')

            try:
                # Call read_audio with proper parameters
                # NOTE: Silero's read_audio expects 'sampling_rate' not 'sample_rate'
                waveform = read_audio(audio_path, sampling_rate=16000)

                # Validate the loaded waveform
                if waveform is None:
                    raise DiarizationError("read_audio returned None")

                return waveform

            except Exception as e:
                logger.error(f"Failed to load audio with Silero read_audio: {e}")
                raise DiarizationError(
                    f"Failed to load audio file '{audio_path}': {str(e)}"
                ) from e

    def _detect_speech(self, waveform, sample_rate: int, streaming: bool = False) -> List[Dict]:
        """
        Detect speech regions in an audio waveform using the configured VAD, optionally in streaming mode, and fall back to a single full-span region when VAD is unavailable.

        Parameters:
            waveform: Audio waveform tensor or sequence of samples.
            sample_rate (int): Sampling rate of the waveform in Hz.
            streaming (bool): If True, attempt a lower-memory streaming VAD pass; falls back to standard VAD on failure.

        Returns:
            List[Dict]: A list of speech segments where each dict contains numeric `start` and `end` keys expressed in seconds.

        Raises:
            DiarizationError: If VAD is unavailable and `allow_vad_fallback` in the configuration is False.
        """
        allow_fallback: bool = bool(self.config.get('allow_vad_fallback', True))

        def _fallback_full_span() -> List[Dict]:
            """
            Produce a single full-span speech region covering the entire waveform or raise an error if fallback is disabled.

            Returns:
                list[dict]: A list with one timestamp dict {'start': 0.0, 'end': <duration_seconds>} giving the speech region in seconds.

            Raises:
                DiarizationError: If fallback is not allowed.
            """
            dur = float(len(waveform) / max(1, sample_rate))
            if allow_fallback:
                logger.warning("VAD unavailable; falling back to single full-span speech region")
                return [{'start': 0.0, 'end': dur}]
            raise DiarizationError("VAD unavailable and allow_vad_fallback is False")

        try:
            # Ensure VAD model is loaded
            if not self._vad_model:
                self._load_vad_model()

            # Validate VAD utilities are loaded
            if not self._vad_utils or 'get_speech_timestamps' not in self._vad_utils:
                logger.debug("VAD utilities missing get_speech_timestamps; using fallback")
                return _fallback_full_span()

            if streaming and 'VADIterator' in self._vad_utils:
                # Use streaming VAD for lower memory usage
                try:
                    VADIterator = self._get_vad_utility('VADIterator')
                    vad_iterator = VADIterator(
                        model=self._vad_model,
                        threshold=self.config['vad_threshold'],
                        sampling_rate=sample_rate,
                        min_silence_duration_ms=int(self.config['vad_min_silence_duration'] * 1000),
                        speech_pad_ms=int(self.config.get('vad_speech_pad_ms', 30))
                    )

                    # Process in chunks for streaming
                    chunk_size = int(sample_rate * 10)  # 10 second chunks
                    speech_timestamps = []

                    for i in range(0, len(waveform), chunk_size):
                        chunk = waveform[i:i + chunk_size]
                        speech_dict = vad_iterator(chunk, return_seconds=False)

                        if speech_dict:
                            # Adjust timestamps for chunk offset
                            for ts in speech_dict.get('speech_timestamps', []):
                                ts['start'] = ts['start'] + i
                                ts['end'] = ts['end'] + i
                                speech_timestamps.append(ts)

                    # Reset iterator
                    vad_iterator.reset_states()

                except Exception as e:
                    logger.warning(f"Streaming VAD failed, falling back to standard VAD: {e}")
                    streaming = False

            if not streaming:
                # Standard (non-streaming) VAD
                # Get the speech detection function using safe getter
                get_speech_timestamps = self._get_vad_utility('get_speech_timestamps')

                try:
                    # Call the VAD function with proper parameters
                    # NOTE: Parameter names and order are critical for Silero VAD
                    speech_timestamps = get_speech_timestamps(
                        waveform,
                        self._vad_model,
                        sampling_rate=sample_rate,  # Must be 'sampling_rate', not 'sample_rate'
                        threshold=self.config['vad_threshold'],
                        min_speech_duration_ms=int(self.config['vad_min_speech_duration'] * 1000),
                        min_silence_duration_ms=int(self.config['vad_min_silence_duration'] * 1000)
                    )

                    # Validate the output format
                    if not isinstance(speech_timestamps, list):
                        logger.debug("Unexpected VAD output type; using fallback full-span")
                        return _fallback_full_span()

                    # Validate each timestamp has required fields
                    for i, ts in enumerate(speech_timestamps):
                        if not isinstance(ts, dict) or 'start' not in ts or 'end' not in ts:
                            logger.debug("Invalid VAD timestamp format; using fallback full-span")
                            return _fallback_full_span()

                except Exception as e:
                    logger.warning(f"VAD detection failed: {e}; using fallback full-span")
                    return _fallback_full_span()

            # Convert to seconds
            for ts in speech_timestamps:
                ts['start'] = ts['start'] / sample_rate
                ts['end'] = ts['end'] / sample_rate

            return speech_timestamps

        except Exception as outer:
            logger.warning(f"VAD unavailable or failed early: {outer}; using fallback full-span")
            return _fallback_full_span()

    def _create_segments(
            self,
            waveform: "torch.Tensor",
            speech_timestamps: List[Dict],
            sample_rate: int
    ) -> List[SegmentDict]:
        """
            Create fixed-length, overlapping speech segments from detected speech regions.

            Segments cover each speech region with windows of length `segment_duration` and overlap `segment_overlap`
            (from the instance configuration). Short regions are either padded up to the minimum segment duration
            or emitted as shorter padded segments at the end of a region depending on their length relative to
            `min_segment_duration`. When the `memory_efficient` config flag is enabled, segments store index
            references into the original waveform (`start_sample`, `end_sample`, `waveform_ref`) and padding metadata
            instead of copying waveform tensors.

            Parameters:
                waveform (torch.Tensor): Mono audio samples (1D tensor) used as the source for segment extraction.
                speech_timestamps (List[Dict]): List of speech region dictionaries with numeric `start` and `end`
                    values given in seconds.
                sample_rate (int): Sampling rate of `waveform` in Hz.

            Returns:
                List[SegmentDict]: A list of segment dictionaries. Each segment includes start/end times (seconds),
                either a `waveform` tensor (copied and possibly padded) or `waveform_ref` with `start_sample`/`end_sample`
                when memory-efficient mode is active, an `is_padded` flag, and other metadata such as `original_duration`
                and `speech_region`.
            """
        torch = _lazy_import_torch()
        if not torch:
            raise DiarizationError("PyTorch not available for segment creation")

        segments = []
        segment_samples = int(self.config['segment_duration'] * sample_rate)
        min_segment_samples = int(self.config.get('min_segment_duration', 1.0) * sample_rate)
        overlap_samples = int(self.config['segment_overlap'] * sample_rate)
        step_samples = segment_samples - overlap_samples

        # Check if memory-efficient mode is enabled
        memory_efficient = self.config.get('memory_efficient', False)

        for speech in speech_timestamps:
            start_sample = int(speech['start'] * sample_rate)
            end_sample = int(speech['end'] * sample_rate)
            speech_duration = end_sample - start_sample

            if speech_duration < min_segment_samples:
                # Handle short segments by padding
                if memory_efficient:
                    # Store indices instead of waveform copy
                    segments.append({
                        'start': start_sample / sample_rate,
                        'end': end_sample / sample_rate,
                        'start_sample': start_sample,
                        'end_sample': end_sample,
                        'waveform_ref': waveform,  # Reference to original
                        'is_padded': True,
                        'padding_needed': min_segment_samples - speech_duration,
                        'original_duration': speech_duration / sample_rate,
                        'speech_region': speech
                    })
                else:
                    # Original behavior - copy waveform
                    segment_waveform = waveform[start_sample:end_sample]
                    # Pad to minimum length with silence
                    padding_needed = min_segment_samples - speech_duration
                    try:
                        padded_waveform = torch.nn.functional.pad(segment_waveform, (0, padding_needed))
                    except Exception as e:
                        logger.warning(f"Failed to pad short segment: {e}")
                        continue  # Skip this segment if padding fails

                    segments.append({
                        'start': start_sample / sample_rate,
                        'end': end_sample / sample_rate,
                        'waveform': padded_waveform,
                        'is_padded': True,
                        'original_duration': speech_duration / sample_rate,
                        'speech_region': speech  # Keep reference to original speech region
                    })
            else:
                # Create overlapping segments within this speech region
                for i in range(start_sample, end_sample - segment_samples + 1, step_samples):
                    if memory_efficient:
                        # Store indices instead of waveform copy
                        segments.append({
                            'start': i / sample_rate,
                            'end': (i + segment_samples) / sample_rate,
                            'start_sample': i,
                            'end_sample': i + segment_samples,
                            'waveform_ref': waveform,  # Reference to original
                            'is_padded': False,
                            'speech_region': speech
                        })
                    else:
                        # Original behavior - copy waveform
                        segment_waveform = waveform[i:i + segment_samples]

                        segments.append({
                            'start': i / sample_rate,
                            'end': (i + segment_samples) / sample_rate,
                            'waveform': segment_waveform,
                            'is_padded': False,
                            'speech_region': speech  # Keep reference to original speech region
                        })

                # Handle the last segment if it's shorter than segment_duration but longer than min_segment_duration
                last_segment_start = start_sample + (
                            (end_sample - start_sample - segment_samples) // step_samples) * step_samples + step_samples
                if last_segment_start < end_sample:
                    remaining_samples = end_sample - last_segment_start
                    if remaining_samples >= min_segment_samples:
                        if memory_efficient:
                            # Store indices for last segment
                            segments.append({
                                'start': last_segment_start / sample_rate,
                                'end': end_sample / sample_rate,
                                'start_sample': last_segment_start,
                                'end_sample': end_sample,
                                'waveform_ref': waveform,  # Reference to original
                                'is_padded': True,
                                'padding_needed': segment_samples - remaining_samples,
                                'original_duration': remaining_samples / sample_rate,
                                'speech_region': speech
                            })
                        else:
                            # Original behavior - copy waveform
                            segment_waveform = waveform[last_segment_start:end_sample]
                            # Pad to segment_duration
                            padding_needed = segment_samples - remaining_samples
                            try:
                                padded_waveform = torch.nn.functional.pad(segment_waveform, (0, padding_needed))
                                segments.append({
                                    'start': last_segment_start / sample_rate,
                                    'end': end_sample / sample_rate,
                                    'waveform': padded_waveform,
                                    'is_padded': True,
                                    'original_duration': remaining_samples / sample_rate,
                                    'speech_region': speech
                                })
                            except Exception as e:
                                logger.warning(f"Failed to pad last segment: {e}")

        return segments

    def _extract_embeddings(
            self,
            segments: List[SegmentDict],
            progress_callback: Optional[Callable[[float, str, Optional[Dict]], None]] = None
    ) -> "np.ndarray":
        """
            Compute speaker embeddings for each provided segment in batches.

            Processes segments in configurable batches, supports memory-efficient on-demand waveform loading, and returns a 2-D NumPy array with one embedding vector per segment.

            Returns:
                np.ndarray: 2-D array of shape (n_segments, embedding_dim) containing embeddings for each segment.

            Raises:
                DiarizationError: If PyTorch or NumPy are unavailable, or if batching/embedding extraction fails.
            """
        # Load embedding model if not already loaded
        self._load_embedding_model()

        embeddings = []
        total_segments = len(segments)
        batch_size = self.config.get('embedding_batch_size', 32)
        memory_efficient = self.config.get('memory_efficient', False)

        torch = _lazy_import_torch()
        if not torch:
            raise DiarizationError("PyTorch not available for embedding extraction")

        # Process segments in batches
        for batch_idx in range(0, len(segments), batch_size):
            batch_segments = segments[batch_idx:batch_idx + batch_size]

            # Stack waveforms for batch processing
            try:
                if memory_efficient:
                    # Load waveforms on-demand for memory-efficient mode
                    batch_waveforms = []
                    for seg in batch_segments:
                        if 'waveform_ref' in seg and 'start_sample' in seg:
                            # Extract waveform from reference
                            start = seg['start_sample']
                            end = seg['end_sample']
                            waveform = seg['waveform_ref'][start:end]

                            # Apply padding if needed
                            if seg.get('is_padded', False) and 'padding_needed' in seg:
                                waveform = torch.nn.functional.pad(waveform, (0, seg['padding_needed']))

                            batch_waveforms.append(waveform.unsqueeze(0))
                        else:
                            # Fallback to stored waveform
                            batch_waveforms.append(seg['waveform'].unsqueeze(0))

                    waveforms = torch.stack(batch_waveforms)
                else:
                    # Original behavior - use stored waveforms
                    waveforms = torch.stack([seg['waveform'].unsqueeze(0) for seg in batch_segments])
            except Exception as e:
                logger.error(f"Failed to stack waveforms for batch {batch_idx}: {e}")
                raise DiarizationError(f"Failed to prepare batch: {e}") from e

            # Extract embeddings for the batch
            try:
                # Prefer inference_mode (lower autograd overhead), fallback to no_grad, then raw call
                if hasattr(torch, 'inference_mode'):
                    try:
                        with torch.inference_mode():  # type: ignore[attr-defined]
                            batch_embeddings = self._embedding_model.encode_batch(waveforms)
                    except Exception as e:
                        logger.debug(f"torch.inference_mode failed: {e}; trying no_grad")
                        if hasattr(torch, 'no_grad'):
                            try:
                                with torch.no_grad():
                                    batch_embeddings = self._embedding_model.encode_batch(waveforms)
                            except Exception as e2:
                                logger.debug(f"torch.no_grad failed: {e2}; calling directly")
                                batch_embeddings = self._embedding_model.encode_batch(waveforms)
                        else:
                            batch_embeddings = self._embedding_model.encode_batch(waveforms)
                elif hasattr(torch, 'no_grad'):
                    try:
                        with torch.no_grad():
                            batch_embeddings = self._embedding_model.encode_batch(waveforms)
                    except Exception as e:
                        logger.debug(f"torch.no_grad failed: {e}; calling directly")
                        batch_embeddings = self._embedding_model.encode_batch(waveforms)
                else:
                    # No inference helpers available, run without context manager
                    batch_embeddings = self._embedding_model.encode_batch(waveforms)

                # Convert to numpy
                batch_embeddings = batch_embeddings.cpu().numpy()

                # Add each embedding from the batch
                for embedding in batch_embeddings:
                    embeddings.append(embedding.squeeze())

            except Exception as e:
                logger.error(f"Failed to extract embeddings for batch starting at {batch_idx}: {e}")
                raise DiarizationError(f"Batch embedding extraction failed: {e}") from e

            # Progress update
            if progress_callback:
                processed = min(batch_idx + len(batch_segments), total_segments)
                progress = 30 + (40 * processed / total_segments)  # 30-70% range
                progress_callback(
                    progress,
                    f"Processing batch {batch_idx // batch_size + 1}/{(total_segments + batch_size - 1) // batch_size}",
                    {'current': processed, 'total': total_segments}
                )

        np = _lazy_import_numpy()
        if not np:
            raise DiarizationError("NumPy not available for creating embedding array")

        try:
            return np.array(embeddings)
        except Exception as e:
            logger.error(f"Failed to create numpy array from embeddings: {e}")
            raise DiarizationError(f"Failed to create embedding array: {e}") from e

    def _cluster_speakers(
            self,
            embeddings: "np.ndarray",
            num_speakers: Optional[int] = None
    ) -> "np.ndarray":
        """
            Perform speaker clustering on precomputed embeddings and return integer cluster labels.

            Clusters the provided L2-normalized embeddings into speaker groups using either spectral
            or agglomerative clustering as configured. If `num_speakers` is 1 or the embeddings are
            determined to come from a single speaker, all labels will be zero. When `num_speakers`
            is None the method will attempt to estimate an appropriate number of speakers.

            Parameters:
                embeddings (np.ndarray): 2D array of embedding vectors (one row per segment).
                num_speakers (Optional[int]): Desired number of speaker clusters; when None the
                    method will estimate the number of speakers. If set to 1, all segments are
                    assigned the same speaker label.

            Returns:
                np.ndarray: 1D integer array of cluster labels with length equal to the number
                of input embeddings.

            Raises:
                DiarizationError: If NumPy or scikit-learn modules are not available for clustering.
            """
        np = _lazy_import_numpy()
        if not np:
            raise DiarizationError("NumPy not available for clustering")

        # Handle single speaker case
        if num_speakers == 1:
            return np.zeros(len(embeddings), dtype=int)

        sklearn_modules = _lazy_import_sklearn()
        if not sklearn_modules:
            raise DiarizationError("scikit-learn modules not available for clustering")

        # Normalize embeddings
        normalize = sklearn_modules['normalize']
        embeddings = normalize(embeddings, axis=1, norm='l2')

        # Add single-speaker detection before clustering
        if num_speakers is None:
            if self._is_single_speaker(embeddings):
                return np.zeros(len(embeddings), dtype=int)
            num_speakers = self._estimate_num_speakers(embeddings)
            logger.info(f"Estimated {num_speakers} speakers")

        # Ensure num_speakers is within bounds
        num_speakers = max(self.config['min_speakers'],
                           min(num_speakers, self.config['max_speakers']))

        if self.config['clustering_method'] == ClusteringMethod.SPECTRAL.value:
            SpectralClustering = sklearn_modules['SpectralClustering']
            clustering = SpectralClustering(
                n_clusters=num_speakers,
                affinity='cosine',
                assign_labels='kmeans',
                random_state=42
            )
        else:  # agglomerative
            AgglomerativeClustering = sklearn_modules['AgglomerativeClustering']
            # scikit-learn >= 1.4 uses 'metric' instead of deprecated 'affinity'
            try:
                clustering = AgglomerativeClustering(
                    n_clusters=num_speakers,
                    linkage='average',
                    metric='cosine',
                )
            except TypeError:
                # Backward compatibility with older sklearn versions
                clustering = AgglomerativeClustering(
                    n_clusters=num_speakers,
                    affinity='cosine',
                    linkage='average',
                )

        labels = clustering.fit_predict(embeddings)
        return labels

    def _estimate_num_speakers(self, embeddings: "np.ndarray") -> int:
        """Estimate the number of speakers using silhouette analysis."""
        sklearn_modules = _lazy_import_sklearn()
        if not sklearn_modules:
            # Default to 2 speakers if sklearn not available
            return 2

        max_score = -1
        best_n = 2

        SpectralClustering = sklearn_modules['SpectralClustering']
        silhouette_score = sklearn_modules['silhouette_score']

        # Try different numbers of speakers
        for n in range(2, min(len(embeddings), self.config['max_speakers'] + 1)):
            try:
                clustering = SpectralClustering(
                    n_clusters=n,
                    affinity='cosine',
                    assign_labels='kmeans',
                    random_state=42
                )
                labels = clustering.fit_predict(embeddings)

                # Calculate silhouette score
                score = silhouette_score(embeddings, labels, metric='cosine')

                if score > max_score:
                    max_score = score
                    best_n = n

            except Exception as e:
                logger.warning(f"Failed to test {n} speakers: {e}")

        return best_n

    def _is_single_speaker(self, embeddings: "np.ndarray", threshold: Optional[float] = None) -> bool:
        """Check if all embeddings likely belong to a single speaker.

        Args:
            embeddings: Normalized speaker embeddings
            threshold: Similarity threshold (default from config)

        Returns:
            True if likely single speaker, False otherwise
        """
        if threshold is None:
            threshold = self.config.get('similarity_threshold', 0.85)

        np = _lazy_import_numpy()
        if not np:
            # Can't check without numpy, assume multiple speakers
            return False

        sklearn_modules = _lazy_import_sklearn()
        if not sklearn_modules or 'normalize' not in sklearn_modules:
            # Can't normalize without sklearn, assume multiple speakers
            return False

        try:
            # Ensure embeddings are normalized
            normalize = sklearn_modules['normalize']
            normalized = normalize(embeddings, axis=1, norm='l2')

            # Compute pairwise cosine similarities
            similarities = normalized @ normalized.T

            # Calculate average similarity (excluding diagonal)
            n = len(embeddings)
            if n <= 1:
                return True  # Single embedding is single speaker

            # Sum all similarities minus diagonal, divide by number of pairs
            avg_similarity = (similarities.sum() - n) / (n * (n - 1))

            logger.debug(f"Average cosine similarity: {avg_similarity:.3f}, threshold: {threshold}")

            # If average similarity is very high, likely single speaker
            return avg_similarity > threshold

        except Exception as e:
            logger.warning(f"Failed to check single speaker: {e}")
            # On error, assume multiple speakers for safety
            return False

    def _merge_segments(self, segments: List[Dict]) -> List[Dict]:
        """Merge consecutive segments from the same speaker."""
        if not segments:
            return []

        # Sort by start time
        segments = sorted(segments, key=lambda x: x['start'])

        merged = []
        current = segments[0].copy()

        for segment in segments[1:]:
            # Check if same speaker and close enough in time
            same_speaker = segment['speaker_id'] == current['speaker_id']
            close_enough = segment['start'] - current['end'] <= self.config['merge_threshold']

            if same_speaker and close_enough:
                # Extend current segment
                current['end'] = segment['end']
            else:
                # Save current and start new
                merged.append(current)
                current = segment.copy()

        # Don't forget the last segment
        merged.append(current)

        return merged

    def _align_with_transcription(
            self,
            diarization_segments: List[Dict],
            transcription_segments: List[Dict]
    ) -> List[Dict]:
        """Align diarization results with transcription segments."""
        aligned = []

        for trans_seg in transcription_segments:
            # Find overlapping diarization segments
            overlaps = []

            for diar_seg in diarization_segments:
                # Check for overlap
                overlap_start = max(trans_seg['start'], diar_seg['start'])
                overlap_end = min(trans_seg['end'], diar_seg['end'])

                if overlap_end > overlap_start:
                    overlap_duration = overlap_end - overlap_start
                    overlaps.append((diar_seg['speaker_id'], overlap_duration))

            # Assign speaker based on maximum overlap
            if overlaps:
                # Sort by overlap duration
                overlaps.sort(key=lambda x: x[1], reverse=True)
                speaker_id = overlaps[0][0]

                # Create aligned segment
                aligned_seg = trans_seg.copy()
                aligned_seg['speaker_id'] = speaker_id
                aligned_seg['speaker_label'] = f"{SPEAKER_LABEL_PREFIX}{speaker_id}"
                aligned.append(aligned_seg)
            else:
                # No overlap found, keep original
                aligned.append(trans_seg)

        return aligned

    def _calculate_speaker_stats(self, segments: List[Dict]) -> List[Dict]:
        """Calculate statistics for each speaker."""
        speaker_times = {}

        for segment in segments:
            speaker_id = segment.get('speaker_id', -1)
            duration = segment['end'] - segment['start']

            if speaker_id not in speaker_times:
                speaker_times[speaker_id] = {
                    'total_time': 0,
                    'segment_count': 0,
                    'first_appearance': segment['start'],
                    'last_appearance': segment['end']
                }

            stats = speaker_times[speaker_id]
            stats['total_time'] += duration
            stats['segment_count'] += 1
            stats['last_appearance'] = segment['end']

        # Convert to list format
        speakers = []
        for speaker_id, stats in speaker_times.items():
            speakers.append({
                'speaker_id': speaker_id,
                'speaker_label': f"{SPEAKER_LABEL_PREFIX}{speaker_id}",
                'total_time': stats['total_time'],
                'segment_count': stats['segment_count'],
                'first_appearance': stats['first_appearance'],
                'last_appearance': stats['last_appearance']
            })

        # Sort by total time (most talkative first)
        speakers.sort(key=lambda x: x['total_time'], reverse=True)

        return speakers

    def _detect_overlapping_speech(
            self,
            segments: List[Dict],
            embeddings: "np.ndarray",
            primary_labels: "np.ndarray"
    ) -> List[Dict]:
        """
            Annotate segments that likely contain overlapping speech based on embedding similarities.

            This function compares each segment's embedding to cluster centroids derived from the provided primary labels and annotates segments where the primary-speaker confidence falls below the configured overlap_confidence_threshold. Annotated fields added or updated on segments:
            - `is_overlapping` (bool): whether the segment is likely overlapping speech.
            - `primary_confidence` (float): similarity score of the segment to its primary cluster.
            - `secondary_speakers` (list[dict]): up to two candidate secondary speakers with keys `speaker_id` (int) and `confidence` (float).

            Returns:
                List[Dict]: The same list of segments with added overlap-related annotations where applicable.
            """
        # Get threshold from config
        confidence_threshold = self.config.get('overlap_confidence_threshold', 0.7)

        # Import required modules
        np = _lazy_import_numpy()
        if not np:
            logger.warning("NumPy not available for overlap detection")
            return segments

        sklearn_modules = _lazy_import_sklearn()
        if not sklearn_modules:
            logger.warning("scikit-learn not available for overlap detection")
            return segments

        try:
            # Get cosine_similarity function
            cosine_similarity = sklearn_modules['cosine_similarity']

            # Get cluster centers (mean of embeddings per cluster) with explicit label→index mapping
            unique_labels = sorted(set(primary_labels))
            label_to_index = {lbl: idx for idx, lbl in enumerate(unique_labels)}
            cluster_centers = []
            for label in unique_labels:
                mask = primary_labels == label
                cluster_center = embeddings[mask].mean(axis=0)
                cluster_centers.append(cluster_center)

            cluster_centers = np.array(cluster_centers)

            # Calculate similarity to all clusters for each segment
            similarities = cosine_similarity(embeddings, cluster_centers)

            # Detect overlapping speech
            for i, (segment, sim_scores) in enumerate(zip(segments, similarities)):
                primary_label = primary_labels[i]
                primary_index = label_to_index.get(primary_label, 0)
                primary_confidence = sim_scores[primary_index]

                # Check if confidence is low (potential overlap)
                if primary_confidence < confidence_threshold:
                    # Find secondary speaker(s)
                    secondary_speakers = []
                    for idx, confidence in enumerate(sim_scores):
                        label = unique_labels[idx]
                        if label != primary_label and confidence > 0.3:
                            secondary_speakers.append({
                                'speaker_id': int(label),
                                'confidence': float(confidence)
                            })

                    if secondary_speakers:
                        segment['is_overlapping'] = True
                        segment['primary_confidence'] = float(primary_confidence)
                        segment['secondary_speakers'] = sorted(
                            secondary_speakers,
                            key=lambda x: x['confidence'],
                            reverse=True
                        )[:2]  # Keep top 2 secondary speakers
                        logger.debug(
                            f"Potential overlap detected at {segment['start']:.2f}s: "
                            f"Primary speaker {primary_label} ({primary_confidence:.2f}), "
                            f"Secondary: {secondary_speakers[0]}"
                        )
                else:
                    segment['is_overlapping'] = False
                    segment['primary_confidence'] = float(primary_confidence)

            # Log overlap statistics
            overlapping_count = sum(1 for s in segments if s.get('is_overlapping', False))
            if overlapping_count > 0:
                logger.info(
                    f"Detected {overlapping_count} segments ({overlapping_count / len(segments) * 100:.1f}%) "
                    f"with potential overlapping speech"
                )

        except Exception as e:
            logger.warning(f"Failed to detect overlapping speech: {e}")
            # Don't fail the whole process, just skip overlap detection

        return segments

    def is_diarization_available(self) -> bool:
        """Check if diarization is available.

        Returns:
            bool: True if all required dependencies are available

        Note:
            You can also directly access the `is_available` attribute
            for the same information.
        """
        return self.is_available

    def get_requirements(self) -> Dict[str, bool]:
        """Get the status of required dependencies."""
        return {
            'torch': _torch_available(),
            'speechbrain': _speechbrain_available(),
            'sklearn': _sklearn_available(),
            'torchaudio': _torchaudio_available()
        }

######################################################################################################################
# Backward Compatibility Wrapper Functions
######################################################################################################################

def audio_diarization(
    audio_file_path: str,
    config_path: Optional[str] = None,
    num_speakers: Optional[int] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Backward compatibility wrapper for audio diarization.

    This function provides compatibility with code expecting the old PyAnnote-based
    diarization interface. It wraps the new DiarizationService class.

    Args:
        audio_file_path: Path to the audio file to diarize
        config_path: Path to configuration file (ignored - uses config.py)
        num_speakers: Number of speakers (if known)
        min_speakers: Minimum number of speakers
        max_speakers: Maximum number of speakers

    Returns:
        List of diarization segments with speaker labels

    Raises:
        DiarizationError: If diarization fails
    """
    try:
        # Create service with optional speaker constraints
        config = {}
        if num_speakers is not None:
            config['num_speakers'] = num_speakers
        if min_speakers is not None:
            config['min_speakers'] = min_speakers
        if max_speakers is not None:
            config['max_speakers'] = max_speakers

        service = DiarizationService(config=config)

        if not service.is_available:
            raise DiarizationError(
                "Diarization dependencies not available. "
                "Install with: pip install tldw-server[diarization]"
            )

        # Perform diarization
        result = service.diarize(audio_path=audio_file_path)

        # Extract segments from result
        if result and 'segments' in result:
            return result['segments']
        else:
            return []

    except Exception as e:
        if isinstance(e, DiarizationError):
            raise
        else:
            raise DiarizationError(f"Diarization failed: {str(e)}")


def combine_transcription_and_diarization(
    transcription_segments: List[Dict[str, Any]],
    diarization_segments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Backward compatibility wrapper for combining transcription and diarization.

    With the new implementation, this is handled internally by DiarizationService.diarize()
    when transcription_segments are provided. This function exists for compatibility.

    Args:
        transcription_segments: List of transcription segments
        diarization_segments: List of diarization segments (ignored in new implementation)

    Returns:
        Combined segments with speaker labels
    """
    # In the new implementation, diarization already handles combination
    # when transcription segments are provided
    if not transcription_segments:
        return []

    # If segments already have speaker info, return as-is
    if transcription_segments and 'speaker' in transcription_segments[0]:
        return transcription_segments

    # Otherwise, perform diarization with transcription
    try:
        service = DiarizationService()

        if not service.is_available:
            logger.warning("Diarization not available, returning transcription without speakers")
            return transcription_segments

        # Get audio path from first segment if available
        audio_path = None
        if transcription_segments and 'audio_path' in transcription_segments[0]:
            audio_path = transcription_segments[0]['audio_path']

        if not audio_path:
            logger.warning("No audio path found in segments, returning transcription without speakers")
            return transcription_segments

        # Perform diarization with transcription segments
        result = service.diarize(
            audio_path=audio_path,
            transcription_segments=transcription_segments
        )

        if result and 'segments' in result:
            return result['segments']
        else:
            return transcription_segments

    except Exception as e:
        logger.warning(f"Failed to combine transcription and diarization: {e}")
        return transcription_segments


#
# End of Diarization_Lib.py
######################################################################################################################
