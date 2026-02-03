"""
Shared Silero VAD helpers used by both diarization and streaming turn detection.

This module centralizes loading of the Silero VAD model and its utilities so that
offline diarization and the unified streaming WebSocket path can depend on a
single implementation rather than importing functionality from each other.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from loguru import logger

_silero_vad_model: Any = None
_silero_vad_utils: Any = None


@lru_cache(maxsize=1)
def _module_spec_available(module_name: str) -> bool:
    """Best-effort probe for a module without importing heavy dependencies."""
    import importlib.util

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
    """Return True when torch is importable."""
    if not _module_spec_available("torch"):
        logger.debug("PyTorch not installed or not discoverable for Silero VAD.")
        return False
    try:
        import torch  # type: ignore  # noqa: F401

        return True
    except Exception as exc:  # pragma: no cover - import error surfaces once
        logger.debug(f"PyTorch import failed for Silero VAD: {exc}")
        return False


def _lazy_import_torch():
    """Lazy import torch for Silero VAD."""
    if not _torch_available():
        return None
    try:
        import torch  # type: ignore

        return torch
    except ImportError as e:  # pragma: no cover - defensive
        logger.warning(f"Failed to import torch for Silero VAD: {e}")
        return None


def _repo_root_with_models() -> Path | None:
    """
    Best-effort discovery of the repo root that contains a models/ directory.

    Preference order:
      1. A parent that has both `models/` AND a repo marker (pyproject.toml or .git).
      2. Otherwise, the outermost parent that has `models/`.
    """
    here = Path(__file__).resolve()
    parents = [here.parent] + list(here.parents)
    fallback: Path | None = None
    for parent in parents:
        models_dir = parent / "models"
        if not models_dir.exists():
            continue
        # Prefer a true repo root when detectable
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
        fallback = parent
    return fallback


def _find_local_silero_repo(models_dir: Path) -> Path | None:
    """
    Discover a locally checked-out Silero VAD repo under models/.

    Prefers common directory names containing hubconf.py, then falls back to any
    directory with hubconf.py whose name/path includes 'silero'.
    """
    candidates = [
        models_dir / "snakers4_silero-vad_master",
        models_dir / "snakers4_silero-vad",
        models_dir / "silero-vad",
        models_dir / "silero_vad",
        models_dir / "silero",
    ]
    for cand in candidates:
        if (cand / "hubconf.py").exists():
            return cand
    for hubconf in models_dir.glob("**/hubconf.py"):
        if "silero" in hubconf.parent.name.lower() or "silero" in str(hubconf).lower():
            return hubconf.parent
    return None


def _lazy_import_silero_vad() -> tuple[Any | None, Any | None]:
    """
    Load and cache the Silero VAD model and its utility functions from torch.hub.

    This helper first checks for a local Silero VAD repo under the project's models/
    directory (to support fully offline setups). When no local repo is present, it
    falls back to `torch.hub.load('snakers4/silero-vad', 'silero_vad', ...)`, saving
    weights under a torch hub cache directory rooted at either TORCH_HOME or
    `<repo_root>/models/torch_home`.

    Returns:
        tuple: `(model, utils)` on success where `utils` is a sequence whose first
        five items are, in order, `get_speech_timestamps`, `save_audio`,
        `read_audio`, `VADIterator`, and `collect_chunks`; `(None, None)` if loading
        or validation fails.
    """
    global _silero_vad_model, _silero_vad_utils

    # Reuse cached model when already loaded
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
        repo_root = _repo_root_with_models()
        default_home_dir = (
            (repo_root / "models" / "torch_home") if repo_root else (Path.home() / ".cache" / "torch")
        )
        torch_home = Path(os.environ.get("TORCH_HOME", str(default_home_dir)))
        hub_dir = torch_home / "hub"
        hub_dir.mkdir(parents=True, exist_ok=True)
        try:
            if hasattr(torch, "hub") and hasattr(torch.hub, "set_dir"):
                torch.hub.set_dir(str(hub_dir))
        except Exception as _hub_dir_err:  # pragma: no cover - best-effort
            logger.debug(f"torch.hub.set_dir failed for Silero VAD: {_hub_dir_err}")

        local_repo = None
        if repo_root:
            local_repo = _find_local_silero_repo(repo_root / "models")
            if local_repo:
                logger.info(f"Using local Silero VAD repo at {local_repo}")
            else:
                logger.debug(
                    "No local Silero VAD repo found under models/. "
                    "Place a snakers4_silero-vad checkout with hubconf.py there to avoid torch.hub fetch."
                )

        # Load model with explicit parameters
        result = torch.hub.load(
            repo_or_dir=(str(local_repo) if local_repo else "snakers4/silero-vad"),
            model="silero_vad",
            force_reload=False,  # Use cached version if available
            trust_repo=True,  # Required for loading
            verbose=False,  # Reduce output noise
        )

        # Accept (model, utils) or (model, utils, config...) shapes
        if not isinstance(result, (tuple, list)) or len(result) < 2:
            logger.error(
                f"Unexpected Silero VAD return format. Expected (model, utils) tuple, "
                f"got {type(result).__name__} with length {len(result) if hasattr(result, '__len__') else 'unknown'}"
            )
            return None, None

        model, utils = result[0], result[1]

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

        _silero_vad_model = model
        _silero_vad_utils = utils

        logger.info("Silero VAD loaded successfully")
        logger.debug(f"Silero VAD utils count: {len(utils)}")

        return model, utils

    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to load Silero VAD: {type(e).__name__}: {e}")
        logger.debug("Full error while loading Silero VAD:", exc_info=True)
        _silero_vad_model = None
        _silero_vad_utils = None
        return None, None


__all__ = ["_lazy_import_silero_vad"]
