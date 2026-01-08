# config_admin.py - Effective config diagnostics (admin-only)
"""Admin-only endpoints for effective configuration diagnostics."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit, require_roles
from tldw_Server_API.app.api.v1.schemas.config_schemas import (
    ConfigValue,
    EffectiveConfigResponse,
)
from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.config_paths import (
    resolve_config_file,
    resolve_config_root,
    resolve_module_yaml,
    resolve_prompts_dir,
)
from tldw_Server_API.app.core.Embeddings.simplified_config import (
    get_config as get_embeddings_config,
    get_config_sources as get_embeddings_sources,
)
from tldw_Server_API.app.core.Evaluations.config_manager import get_config_snapshot as get_evaluations_snapshot
from tldw_Server_API.app.core.TTS.tts_config import get_tts_config_manager

router = APIRouter(
    prefix="/admin/config",
    tags=["admin", "config"],
    dependencies=[Depends(check_rate_limit), Depends(require_roles("admin"))],
)

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(api[_-]?key|access[_-]?key|token|secret|password|private[_-]?key|signing[_-]?key|encryption[_-]?key)",
    re.IGNORECASE,
)
_ALLOWED_SOURCES = {"env", "config", "yaml", "default"}
_REDACTED_VALUE = "<redacted>"


def _is_sensitive(path: str) -> bool:
    return bool(_SENSITIVE_KEY_PATTERN.search(path))


def _normalize_source(raw: Optional[str]) -> str:
    if raw in _ALLOWED_SOURCES:
        return raw
    return "default"


def _flatten_values(
    data: Any,
    sources: Any,
    prefix: str,
    out: Dict[str, ConfigValue],
) -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            branch = sources.get(key) if isinstance(sources, dict) else sources
            _flatten_values(value, branch, path, out)
        return

    if isinstance(data, list):
        for idx, value in enumerate(data):
            path = f"{prefix}[{idx}]"
            _flatten_values(value, sources, path, out)
        return

    if not prefix:
        return

    source = _normalize_source(sources if isinstance(sources, str) else None)
    redacted = _is_sensitive(prefix)
    value = _REDACTED_VALUE if redacted else data
    out[prefix] = ConfigValue(value=value, source=source, redacted=redacted)


def _filter_defaults(
    values: Dict[str, ConfigValue],
    include_defaults: bool,
) -> Dict[str, ConfigValue]:
    if include_defaults:
        return values
    return {key: val for key, val in values.items() if val.source != "default"}


def _build_config_txt_values() -> Dict[str, ConfigValue]:
    values: Dict[str, ConfigValue] = {}
    config_parser = load_comprehensive_config()
    if not hasattr(config_parser, "sections"):
        return values

    try:
        sections = config_parser.sections()
    except Exception:
        logger.exception("Error reading config sections")
        sections = []

    for section in sections:
        try:
            items = config_parser.items(section)
        except Exception:
            logger.exception("Error reading items for section {}", section)
            items = []
        for key, raw_value in items:
            path = f"{section}.{key}"
            redacted = _is_sensitive(path)
            values[path] = ConfigValue(
                value=_REDACTED_VALUE if redacted else raw_value,
                source="config",
                redacted=redacted,
            )
    return values


def _build_tts_values() -> Dict[str, ConfigValue]:
    manager = get_tts_config_manager()
    data = manager.to_dict()
    sources = manager.get_sources()
    values: Dict[str, ConfigValue] = {}
    _flatten_values(data, sources, "", values)
    return values


def _build_embeddings_values() -> Dict[str, ConfigValue]:
    config = get_embeddings_config()
    data = config.to_dict()
    sources = get_embeddings_sources()
    values: Dict[str, ConfigValue] = {}
    _flatten_values(data, sources, "", values)
    return values


def _build_evaluations_values() -> Dict[str, ConfigValue]:
    snapshot = get_evaluations_snapshot()
    data = snapshot.get("config", {})
    sources = snapshot.get("sources", {})
    values: Dict[str, ConfigValue] = {}
    _flatten_values(data, sources, "", values)
    return values


def _normalize_sections(sections: Optional[Iterable[str]]) -> List[str]:
    if not sections:
        return ["config_txt", "tts", "embeddings", "evaluations"]
    normalized = []
    for section in sections:
        if not section:
            continue
        key = section.strip().lower()
        if key == "config":
            key = "config_txt"
        normalized.append(key)
    return normalized


@router.get(
    "/effective",
    response_model=EffectiveConfigResponse,
    summary="Get effective configuration with redaction",
)
async def get_effective_config(
    sections: Optional[List[str]] = Query(
        None,
        description="Limit response to specific config namespaces (e.g., tts, embeddings)",
    ),
    include_defaults: bool = Query(
        True,
        description="Include default values when true",
    ),
) -> EffectiveConfigResponse:
    """
    Return the effective configuration with sensitive fields redacted.

    Args:
        sections: Optional list of namespaces to include (e.g., tts, embeddings).
        include_defaults: Whether to include default values in the response.

    Returns:
        EffectiveConfigResponse containing the resolved configuration snapshot.

    Raises:
        HTTPException: If config resolution fails.
    """
    try:
        config_root = resolve_config_root()
        config_file = resolve_config_file()
        prompts_dir = resolve_prompts_dir()
    except FileNotFoundError as exc:
        logger.debug("Effective config resolution failed: {}", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    tts_yaml = resolve_module_yaml("tts")
    embeddings_yaml = resolve_module_yaml(
        "embeddings",
        filename_override=os.getenv("EMBEDDINGS_CONFIG_PATH"),
    )
    evaluations_yaml = resolve_module_yaml(
        "evaluations",
        filename_override=os.getenv("EVALUATIONS_CONFIG_PATH"),
    )
    module_yaml = {
        "tts": str(tts_yaml) if tts_yaml else None,
        "embeddings": str(embeddings_yaml) if embeddings_yaml else None,
        "evaluations": str(evaluations_yaml) if evaluations_yaml else None,
    }

    builders = {
        "config_txt": _build_config_txt_values,
        "tts": _build_tts_values,
        "embeddings": _build_embeddings_values,
        "evaluations": _build_evaluations_values,
    }
    selected_sections = _normalize_sections(sections)
    values: Dict[str, Dict[str, ConfigValue]] = {}

    for section in selected_sections:
        builder = builders.get(section)
        if not builder:
            continue
        section_values = builder()
        values[section] = _filter_defaults(section_values, include_defaults)

    return EffectiveConfigResponse(
        config_root=str(config_root),
        config_file=str(config_file) if config_file else None,
        prompts_dir=str(prompts_dir) if prompts_dir else None,
        module_yaml=module_yaml,
        values=values,
    )
