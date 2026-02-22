from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from typing import Any


def _resolve_settings(settings_obj: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    if settings_obj is not None:
        return settings_obj
    try:
        from tldw_Server_API.app.core.config import settings as _settings  # type: ignore
    except Exception:
        return {}
    if isinstance(_settings, Mapping):
        return _settings
    return {}


def _get_str(
    settings_obj: Mapping[str, Any],
    key: str,
    *,
    default: str | None = None,
) -> str | None:
    with suppress(Exception):
        value = settings_obj.get(key, default)
        text = str(value).strip() if value is not None else ""
        return text or default
    return default


def _get_float(
    settings_obj: Mapping[str, Any],
    key: str,
    *,
    default: float,
) -> float:
    with suppress(Exception):
        value = settings_obj.get(key, default)
        return float(value)
    return default


def _get_int(
    settings_obj: Mapping[str, Any],
    key: str,
    *,
    default: int,
) -> int:
    with suppress(Exception):
        value = settings_obj.get(key, default)
        return int(value)
    return default


def _get_bool(
    settings_obj: Mapping[str, Any],
    key: str,
    *,
    default: bool,
) -> bool:
    with suppress(Exception):
        value = settings_obj.get(key, default)
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "on", "enabled"}:
            return True
        if text in {"0", "false", "no", "off", "disabled"}:
            return False
    return default


def resolve_claims_llm_config(
    settings_obj: Mapping[str, Any] | None = None,
    *,
    default_provider: str = "openai",
    default_temperature: float = 0.1,
) -> tuple[str, str | None, float]:
    settings_map = _resolve_settings(settings_obj)

    provider = _get_str(settings_map, "CLAIMS_LLM_PROVIDER", default=None)
    model_override = _get_str(settings_map, "CLAIMS_LLM_MODEL", default=None)
    temperature = _get_float(settings_map, "CLAIMS_LLM_TEMPERATURE", default=default_temperature)

    rag_cfg: Mapping[str, Any] = {}
    with suppress(Exception):
        maybe_rag = settings_map.get("RAG", {})  # type: ignore[arg-type]
        if isinstance(maybe_rag, Mapping):
            rag_cfg = maybe_rag

    if provider is None:
        provider = _get_str(rag_cfg, "default_llm_provider", default=None)
    if provider is None:
        provider = _get_str(settings_map, "default_api", default=default_provider) or default_provider
    if model_override is None:
        model_override = _get_str(rag_cfg, "default_llm_model", default=None)

    return provider or default_provider, model_override, temperature


def resolve_claims_json_parse_mode(
    settings_obj: Mapping[str, Any] | None = None,
    *,
    default_mode: str = "lenient",
) -> str:
    settings_map = _resolve_settings(settings_obj)
    mode = _get_str(settings_map, "CLAIMS_JSON_PARSE_MODE", default=default_mode) or default_mode
    resolved = mode.strip().lower()
    if resolved not in {"lenient", "strict"}:
        return default_mode
    return resolved


def resolve_claims_alignment_config(
    settings_obj: Mapping[str, Any] | None = None,
    *,
    default_mode: str = "fuzzy",
    default_threshold: float = 0.75,
) -> tuple[str, float]:
    settings_map = _resolve_settings(settings_obj)
    mode = _get_str(settings_map, "CLAIMS_ALIGNMENT_MODE", default=default_mode) or default_mode
    resolved_mode = mode.strip().lower()
    if resolved_mode not in {"off", "exact", "fuzzy"}:
        resolved_mode = default_mode

    threshold = _get_float(settings_map, "CLAIMS_ALIGNMENT_THRESHOLD", default=default_threshold)
    threshold = max(0.0, min(1.0, threshold))
    return resolved_mode, threshold


def resolve_claims_prompt_validation_config(
    settings_obj: Mapping[str, Any] | None = None,
    *,
    default_mode: str = "warning",
    default_strict: bool = False,
) -> tuple[str, bool]:
    settings_map = _resolve_settings(settings_obj)
    mode = _get_str(settings_map, "CLAIMS_PROMPT_VALIDATION_MODE", default=default_mode) or default_mode
    resolved_mode = mode.strip().lower()
    if resolved_mode not in {"off", "warning", "error"}:
        resolved_mode = default_mode
    strict = _get_bool(
        settings_map,
        "CLAIMS_PROMPT_VALIDATION_STRICT",
        default=default_strict,
    )
    return resolved_mode, strict


def resolve_claims_context_window_chars(
    settings_obj: Mapping[str, Any] | None = None,
    *,
    default: int = 0,
) -> int:
    settings_map = _resolve_settings(settings_obj)
    value = _get_int(settings_map, "CLAIMS_CONTEXT_WINDOW_CHARS", default=default)
    return max(0, value)


def resolve_claims_extraction_passes(
    settings_obj: Mapping[str, Any] | None = None,
    *,
    default: int = 1,
) -> int:
    settings_map = _resolve_settings(settings_obj)
    value = _get_int(settings_map, "CLAIMS_EXTRACTION_PASSES", default=default)
    return max(1, value)


__all__ = [
    "resolve_claims_alignment_config",
    "resolve_claims_context_window_chars",
    "resolve_claims_extraction_passes",
    "resolve_claims_json_parse_mode",
    "resolve_claims_llm_config",
    "resolve_claims_prompt_validation_config",
]
