"""
Shared OpenRouter model discovery helpers.

This module centralizes:
- OpenRouter /models URL resolution
- cached discovery with TTL
- model-id extraction from OpenRouter payload variants

Callers can choose whether to include extended aliases/canonical ids.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from typing import Any, Callable

from loguru import logger

from tldw_Server_API.app.core.exceptions import (
    EgressPolicyError,
    NetworkError,
    RetryExhaustedError,
)
from tldw_Server_API.app.core.http_client import RetryPolicy as _RetryPolicy
from tldw_Server_API.app.core.http_client import fetch as _http_fetch

_OPENROUTER_MODEL_DISCOVERY_TIMEOUT_DEFAULT_SECONDS = 5.0
_OPENROUTER_MODEL_DISCOVERY_TTL_DEFAULT_SECONDS = 600
_OPENROUTER_MODEL_CACHE: dict[str, tuple[float, list[str]]] = {}
_OPENROUTER_MODEL_CACHE_LOCK = threading.Lock()

_OPENROUTER_DISCOVERY_NONCRITICAL_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    ConnectionError,
    EgressPolicyError,
    KeyError,
    LookupError,
    NetworkError,
    OSError,
    PermissionError,
    RetryExhaustedError,
    RuntimeError,
    TimeoutError,
    TypeError,
    UnicodeDecodeError,
    ValueError,
)


def clear_openrouter_model_cache() -> None:
    """Clear cached OpenRouter discovery responses."""
    with _OPENROUTER_MODEL_CACHE_LOCK:
        _OPENROUTER_MODEL_CACHE.clear()


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for value in values:
        if not value:
            continue
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def openrouter_model_discovery_ttl_seconds(
    default_seconds: int = _OPENROUTER_MODEL_DISCOVERY_TTL_DEFAULT_SECONDS,
) -> int:
    """Resolve OpenRouter model discovery TTL from env."""
    raw = os.getenv("OPENROUTER_MODEL_DISCOVERY_TTL_SECONDS")
    if raw is None:
        return default_seconds
    try:
        parsed = int(str(raw).strip())
    except _OPENROUTER_DISCOVERY_NONCRITICAL_EXCEPTIONS:
        return default_seconds
    return max(30, parsed)


def resolve_openrouter_models_url(base_url: str | None = None) -> str:
    """Build the OpenRouter /models URL from base URL env or explicit value."""
    resolved_base = (base_url or os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip()
    if not resolved_base:
        resolved_base = "https://openrouter.ai/api/v1"
    resolved_base = resolved_base.rstrip("/")
    if resolved_base.lower().endswith("/models"):
        resolved_base = resolved_base[: -len("/models")]
    return f"{resolved_base}/models"


def extract_openrouter_model_identifiers(
    payload: Any,
    *,
    include_extended_aliases: bool = False,
) -> list[str]:
    """Extract model identifiers from OpenRouter /models payloads."""
    identifiers: list[str] = []

    def _append(value: Any) -> None:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                identifiers.append(normalized)

    def _append_alias_block(value: Any) -> None:
        if isinstance(value, str):
            _append(value)
            return
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    for key in (
                        "id",
                        "model",
                        "name",
                        "canonical_slug",
                        "canonicalSlug",
                        "slug",
                    ):
                        _append(entry.get(key))
                else:
                    _append(entry)

    def _append_item(item: Any) -> None:
        if isinstance(item, str):
            _append(item)
            return
        if not isinstance(item, dict):
            return

        for key in ("id", "model", "name"):
            _append(item.get(key))

        if include_extended_aliases:
            for key in ("canonical_slug", "canonicalSlug", "slug"):
                _append(item.get(key))
            for key in (
                "aliases",
                "alias",
                "alternate_ids",
                "alternateIds",
                "canonical_aliases",
                "canonicalAliases",
            ):
                _append_alias_block(item.get(key))

    sections: list[list[Any]] = []
    if isinstance(payload, dict):
        data_items = payload.get("data")
        if isinstance(data_items, list):
            sections.append(data_items)
        models_items = payload.get("models")
        if isinstance(models_items, list):
            sections.append(models_items)
        if not sections:
            sections.append([payload])
    elif isinstance(payload, list):
        sections.append(payload)

    for section in sections:
        for item in section:
            _append_item(item)
    return _dedupe_preserve_order(identifiers)


def discover_openrouter_models(
    api_key: str | None,
    *,
    force_refresh: bool = False,
    include_extended_aliases: bool = False,
    timeout_seconds: float = _OPENROUTER_MODEL_DISCOVERY_TIMEOUT_DEFAULT_SECONDS,
    log_prefix: str = "[OpenRouter model discovery]",
    fetch_fn: Callable[..., Any] | None = None,
) -> list[str]:
    """Discover OpenRouter model IDs from /models with short-lived caching."""
    resolved_key = (api_key or "").strip()
    if not resolved_key:
        return []

    models_url = resolve_openrouter_models_url()
    key_digest = hashlib.sha1(resolved_key.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
    cache_key = f"{models_url}|{key_digest}|extended={int(include_extended_aliases)}"
    now = time.time()
    ttl = openrouter_model_discovery_ttl_seconds()

    with _OPENROUTER_MODEL_CACHE_LOCK:
        cached = _OPENROUTER_MODEL_CACHE.get(cache_key)
    if cached and not force_refresh and (now - cached[0] < ttl):
        return list(cached[1])

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {resolved_key}",
    }
    referer = (os.getenv("OPENROUTER_SITE_URL") or "").strip()
    site_name = (os.getenv("OPENROUTER_SITE_NAME") or "").strip()
    if referer:
        headers["HTTP-Referer"] = referer
    if site_name:
        headers["X-Title"] = site_name

    fetcher = fetch_fn or _http_fetch
    try:
        resp = fetcher(
            method="GET",
            url=models_url,
            headers=headers,
            timeout=timeout_seconds,
            retry=_RetryPolicy(attempts=1),
        )
        try:
            if resp.status_code >= 400:
                logger.warning("{} {} responded with {}", log_prefix, models_url, resp.status_code)
                return list(cached[1]) if cached else []
            payload = resp.json()
        finally:
            close = getattr(resp, "close", None)
            if callable(close):
                close()

        discovered = extract_openrouter_model_identifiers(
            payload,
            include_extended_aliases=include_extended_aliases,
        )
        with _OPENROUTER_MODEL_CACHE_LOCK:
            _OPENROUTER_MODEL_CACHE[cache_key] = (time.time(), list(discovered))
        if discovered:
            logger.info("{} found {} models via {}", log_prefix, len(discovered), models_url)
        return discovered
    except _OPENROUTER_DISCOVERY_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug("{} {} failed: {}", log_prefix, models_url, exc)
        return list(cached[1]) if cached else []
    except Exception as exc:  # noqa: BLE001 - discovery should fail open
        logger.debug("{} unexpected failure via {}: {}", log_prefix, models_url, exc)
        return list(cached[1]) if cached else []

