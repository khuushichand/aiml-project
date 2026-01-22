"""Configuration helpers for image generation backends."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.config import get_config_section


DEFAULT_BACKEND = "stable_diffusion_cpp"
DEFAULT_MAX_WIDTH = 1024
DEFAULT_MAX_HEIGHT = 1024
DEFAULT_MAX_PIXELS = 1024 * 1024
DEFAULT_MAX_STEPS = 50
DEFAULT_MAX_PROMPT_LENGTH = 1000
DEFAULT_INLINE_MAX_BYTES = 4_000_000

DEFAULT_SD_CPP_STEPS = 25
DEFAULT_SD_CPP_CFG_SCALE = 7.5
DEFAULT_SD_CPP_SAMPLER = "euler_a"
DEFAULT_SD_CPP_DEVICE = "auto"
DEFAULT_SD_CPP_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class ImageGenerationConfig:
    default_backend: Optional[str]
    enabled_backends: List[str]
    max_width: int
    max_height: int
    max_pixels: int
    max_steps: int
    max_prompt_length: int
    inline_max_bytes: Optional[int]
    sd_cpp_diffusion_model_path: Optional[str]
    sd_cpp_llm_path: Optional[str]
    sd_cpp_binary_path: Optional[str]
    sd_cpp_model_path: Optional[str]
    sd_cpp_vae_path: Optional[str]
    sd_cpp_lora_paths: List[str]
    sd_cpp_allowed_extra_params: List[str]
    sd_cpp_default_steps: int
    sd_cpp_default_cfg_scale: float
    sd_cpp_default_sampler: str
    sd_cpp_device: str
    sd_cpp_timeout_seconds: int


_config_cache: Optional[ImageGenerationConfig] = None


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _parse_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raw = str(value).strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in raw.split(",") if item.strip()]


def _get_config_value(section: Dict[str, str], key: str) -> Optional[str]:
    raw = section.get(key)
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def get_image_generation_config(*, reload: bool = False) -> ImageGenerationConfig:
    global _config_cache
    if _config_cache is not None and not reload:
        return _config_cache

    section = get_config_section("Image-Generation", reload=reload)

    default_backend = _get_config_value(section, "default_backend") or DEFAULT_BACKEND
    enabled_backends = _parse_list(section.get("enabled_backends"))
    if not enabled_backends:
        enabled_backends = []

    inline_max_bytes_raw = _get_config_value(section, "inline_max_bytes")
    inline_max_bytes = None
    if inline_max_bytes_raw is not None:
        inline_max_bytes = _coerce_int(inline_max_bytes_raw, DEFAULT_INLINE_MAX_BYTES)

    config = ImageGenerationConfig(
        default_backend=default_backend,
        enabled_backends=enabled_backends,
        max_width=_coerce_int(section.get("max_width"), DEFAULT_MAX_WIDTH),
        max_height=_coerce_int(section.get("max_height"), DEFAULT_MAX_HEIGHT),
        max_pixels=_coerce_int(section.get("max_pixels"), DEFAULT_MAX_PIXELS),
        max_steps=_coerce_int(section.get("max_steps"), DEFAULT_MAX_STEPS),
        max_prompt_length=_coerce_int(section.get("max_prompt_length"), DEFAULT_MAX_PROMPT_LENGTH),
        inline_max_bytes=inline_max_bytes,
        sd_cpp_diffusion_model_path=_get_config_value(section, "sd_cpp_diffusion_model_path"),
        sd_cpp_llm_path=_get_config_value(section, "sd_cpp_llm_path"),
        sd_cpp_binary_path=_get_config_value(section, "sd_cpp_binary_path"),
        sd_cpp_model_path=_get_config_value(section, "sd_cpp_model_path"),
        sd_cpp_vae_path=_get_config_value(section, "sd_cpp_vae_path"),
        sd_cpp_lora_paths=_parse_list(section.get("sd_cpp_lora_paths")),
        sd_cpp_allowed_extra_params=_parse_list(section.get("sd_cpp_allowed_extra_params")),
        sd_cpp_default_steps=_coerce_int(section.get("sd_cpp_default_steps"), DEFAULT_SD_CPP_STEPS),
        sd_cpp_default_cfg_scale=_coerce_float(section.get("sd_cpp_default_cfg_scale"), DEFAULT_SD_CPP_CFG_SCALE),
        sd_cpp_default_sampler=_get_config_value(section, "sd_cpp_default_sampler") or DEFAULT_SD_CPP_SAMPLER,
        sd_cpp_device=_get_config_value(section, "sd_cpp_device") or DEFAULT_SD_CPP_DEVICE,
        sd_cpp_timeout_seconds=_coerce_int(section.get("sd_cpp_timeout_seconds"), DEFAULT_SD_CPP_TIMEOUT_SECONDS),
    )

    _config_cache = config
    return config


def reset_image_generation_config_cache() -> None:
    global _config_cache
    _config_cache = None
