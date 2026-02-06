"""Helpers for exposing image generation backends in model catalogs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Image_Generation.adapter_registry import get_registry
from tldw_Server_API.app.core.Image_Generation.config import get_image_generation_config

_IMAGE_LISTING_NONCRITICAL_EXCEPTIONS = (
    AttributeError,
    KeyError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _path_exists(raw: str | None) -> bool:
    if not raw:
        return False
    try:
        return Path(str(raw)).expanduser().exists()
    except (OSError, RuntimeError, TypeError, ValueError):
        return False


def _is_sd_cpp_configured(cfg, enabled: bool) -> bool:
    if not enabled:
        return False
    if not _path_exists(cfg.sd_cpp_binary_path):
        return False
    if _path_exists(cfg.sd_cpp_diffusion_model_path) or _path_exists(cfg.sd_cpp_model_path):
        return True
    return False


def _is_swarmui_configured(cfg, enabled: bool) -> bool:
    if not enabled:
        return False
    return bool(getattr(cfg, "swarmui_base_url", None))


def _resolve_supported_formats(name: str) -> list[str] | None:
    registry = get_registry()
    try:
        adapter_cls = registry.get_adapter_class(name)
    except _IMAGE_LISTING_NONCRITICAL_EXCEPTIONS:
        adapter_cls = None
    if adapter_cls is None:
        return None
    try:
        formats = getattr(adapter_cls, "supported_formats", None)
    except _IMAGE_LISTING_NONCRITICAL_EXCEPTIONS:
        formats = None
    if not isinstance(formats, (list, set, tuple)):
        return None
    cleaned = {str(v).strip() for v in formats if v and str(v).strip()}
    return sorted(cleaned) if cleaned else None


def list_image_models_for_catalog() -> list[dict[str, Any]]:
    cfg = get_image_generation_config()
    registry = get_registry()
    enabled_backends = set(cfg.enabled_backends or [])
    names = registry.list_backend_names(include_disabled=False)
    if not names:
        return []

    entries: list[dict[str, Any]] = []
    for name in names:
        enabled = name in enabled_backends
        is_configured = enabled
        if name == "stable_diffusion_cpp":
            try:
                is_configured = _is_sd_cpp_configured(cfg, enabled)
            except _IMAGE_LISTING_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug("Image backend config check failed for %s: %s", name, exc)
                is_configured = False
        if name == "swarmui":
            try:
                is_configured = _is_swarmui_configured(cfg, enabled)
            except _IMAGE_LISTING_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug("Image backend config check failed for %s: %s", name, exc)
                is_configured = False

        entry: dict[str, Any] = {
            "provider": "image",
            "id": f"image/{name}",
            "name": name,
            "type": "image",
            "capabilities": {"image_generation": True},
            "modalities": {"input": ["text"], "output": ["image"]},
            "is_configured": bool(is_configured),
        }

        supported_formats = _resolve_supported_formats(name)
        if supported_formats:
            entry["supported_formats"] = supported_formats

        entries.append(entry)

    return entries
