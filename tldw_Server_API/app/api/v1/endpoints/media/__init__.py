from __future__ import annotations

from importlib import import_module
from typing import Any, Dict

from fastapi import APIRouter

# NOTE: This package currently acts as a thin compatibility
# shim over the legacy monolithic implementation in
# `_legacy_media.py`. All existing imports of
# `tldw_Server_API.app.api.v1.endpoints.media` continue to
# work, and selected internals are re-exported for tests.

_legacy_media = import_module("tldw_Server_API.app.api.v1.endpoints._legacy_media")

# Public router used by main application.
router: APIRouter = getattr(_legacy_media, "router")

# Commonly imported helpers (kept explicit for type checkers).
_download_url_async = getattr(_legacy_media, "_download_url_async")
_save_uploaded_files = getattr(_legacy_media, "_save_uploaded_files")

# Shared cache reference; tests monkeypatch `media.cache` and we
# propagate that into the legacy module on each call that uses it.
cache = getattr(_legacy_media, "cache", None)


def cache_response(key: str, response: Dict) -> None:
    """
    Delegate cache_response to the legacy module while honoring
    monkeypatches of `media.cache` in tests.
    """
    setattr(_legacy_media, "cache", cache)
    legacy_cache_response = getattr(_legacy_media, "cache_response")
    legacy_cache_response(key, response)


def invalidate_cache(media_id: int) -> None:
    """
    Delegate invalidate_cache to the legacy module while honoring
    monkeypatches of `media.cache` in tests.
    """
    setattr(_legacy_media, "cache", cache)
    legacy_invalidate = getattr(_legacy_media, "invalidate_cache")
    legacy_invalidate(media_id)


def __getattr__(name: str) -> Any:
    """
    Delegate attribute access to the legacy module.

    This preserves behavior for tests and any external
    integrations that import internal helpers directly
    from `endpoints.media`.
    """
    return getattr(_legacy_media, name)


__all__ = [
    "router",
    "_download_url_async",
    "_save_uploaded_files",
    "cache",
    "cache_response",
    "invalidate_cache",
]

