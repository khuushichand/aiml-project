from __future__ import annotations

from importlib import import_module
from typing import Any, Dict

from fastapi import APIRouter
from loguru import logger

# NOTE: This package currently acts as a compatibility shim
# over the legacy monolithic implementation in `_legacy_media.py`.
# All existing imports of
# `tldw_Server_API.app.api.v1.endpoints.media` continue to work,
# and selected internals are re-exported for tests.

try:
    _legacy_media = import_module("tldw_Server_API.app.api.v1.endpoints._legacy_media")
    legacy_router: APIRouter = getattr(_legacy_media, "router")
except Exception as _legacy_import_err:  # noqa: BLE001
    # In ultra-minimal or dependency-stubbed test profiles (e.g. torch/dill
    # stubs), the legacy media module may fail to import due to optional
    # audio/ML dependencies. In that case, fall back to a read-only router
    # that still exposes the modularized endpoints (list/detail/versions,
    # metadata search, etc.) so focused tests can run.
    logger.warning(
        "Legacy media module unavailable; falling back to read-only media router "
        "subset only: {}",
        _legacy_import_err,
    )
    _legacy_media = None  # type: ignore[assignment]
    legacy_router = APIRouter()

# New modular routers take precedence for overlapping paths by
# prepending their routes ahead of the legacy ones. This keeps
# the effective router object compatible with existing imports
# while allowing gradual extraction into submodules.
from . import (
    add,
    item,
    listing,
    versions,
    process_code,
    process_documents,
    process_pdfs,
    process_ebooks,
    process_emails,
    process_videos,
    process_audios,
    process_web_scraping,
    process_mediawiki,
)

if legacy_router.routes:
    original_legacy_router = legacy_router
    legacy_router = APIRouter()

    # Manually merge route objects instead of using include_router with an
    # empty prefix, to avoid FastAPI's restriction on (prefix="", path="").
    for _router in (
        listing.router,
        item.router,
        versions.router,
        add.router,
        process_code.router,
        process_documents.router,
        process_pdfs.router,
        process_ebooks.router,
        process_emails.router,
        process_videos.router,
        process_audios.router,
        process_web_scraping.router,
        process_mediawiki.router,
        original_legacy_router,
    ):
        for route in _router.routes:
            legacy_router.routes.append(route)

    # Public router used by main application when legacy module is available.
    router: APIRouter = legacy_router
else:
    # Fallback: expose only the modular endpoints when legacy media cannot
    # be imported (ultra-minimal test profiles).
    router = APIRouter()
    for _router in (
        listing.router,
        item.router,
        versions.router,
        add.router,
        process_code.router,
        process_documents.router,
        process_pdfs.router,
        process_ebooks.router,
        process_emails.router,
        process_videos.router,
        process_audios.router,
        process_web_scraping.router,
        process_mediawiki.router,
    ):
        for route in _router.routes:
            router.routes.append(route)

# Commonly imported helpers (kept explicit for type checkers).
if _legacy_media is not None:
    _download_url_async = getattr(_legacy_media, "_download_url_async")
    _save_uploaded_files = getattr(_legacy_media, "_save_uploaded_files")
    # Shared cache reference; tests monkeypatch `media.cache` and we
    # propagate that into the legacy module on each call that uses it.
    cache = getattr(_legacy_media, "cache", None)
else:  # pragma: no cover - only used in ultra-minimal test profiles
    _download_url_async = None  # type: ignore[assignment]
    _save_uploaded_files = None  # type: ignore[assignment]
    cache = None


def cache_response(key: str, response: Dict) -> None:
    """
    Delegate cache_response to the legacy module while honoring
    monkeypatches of `media.cache` in tests.
    """
    if _legacy_media is None:
        return
    legacy_cache_response = getattr(_legacy_media, "cache_response", None)
    if legacy_cache_response is None:
        return
    # Avoid leaving shared state mutated across calls: temporarily
    # override the legacy module's cache and restore it afterwards.
    old_cache = getattr(_legacy_media, "cache", None)
    try:
        setattr(_legacy_media, "cache", cache)
        legacy_cache_response(key, response)
    finally:
        setattr(_legacy_media, "cache", old_cache)


def invalidate_cache(media_id: int) -> None:
    """
    Delegate invalidate_cache to the legacy module while honoring
    monkeypatches of `media.cache` in tests.
    """
    if _legacy_media is None:
        return
    legacy_invalidate = getattr(_legacy_media, "invalidate_cache", None)
    if legacy_invalidate is None:
        return
    old_cache = getattr(_legacy_media, "cache", None)
    try:
        setattr(_legacy_media, "cache", cache)
        legacy_invalidate(media_id)
    finally:
        setattr(_legacy_media, "cache", old_cache)


def __getattr__(name: str) -> Any:
    """
    Delegate attribute access to the legacy module.

    This preserves behavior for tests and any external
    integrations that import internal helpers directly
    from `endpoints.media`.
    """
    if _legacy_media is None:
        raise AttributeError(name)
    return getattr(_legacy_media, name)


__all__ = [
    "router",
    "_download_url_async",
    "_save_uploaded_files",
    "cache",
    "cache_response",
    "invalidate_cache",
]
