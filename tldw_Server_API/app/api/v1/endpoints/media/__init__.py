from __future__ import annotations

from importlib import import_module
from typing import Any, Dict

from fastapi import APIRouter
from loguru import logger

from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import (  # type: ignore  # noqa: E501
    TempDirManager as CoreTempDirManager,
    save_uploaded_files as core_save_uploaded_files,
)

# NOTE: This package currently acts as a compatibility shim
# over the legacy monolithic implementation in `_legacy_media.py`.
# All existing imports of
# `tldw_Server_API.app.api.v1.endpoints.media` continue to work,
# and selected internals are re-exported for tests.

disable_legacy = (
    str(__import__("os").environ.get("TLDW_DISABLE_LEGACY_MEDIA", "")).lower()
    in {"1", "true", "yes", "on"}
)

if not disable_legacy:
    try:
        _legacy_media = import_module(
            "tldw_Server_API.app.api.v1.endpoints._legacy_media"
        )
        legacy_router: APIRouter = getattr(_legacy_media, "router")
    except Exception as _legacy_import_err:  # noqa: BLE001
        # In ultra-minimal or dependency-stubbed test profiles (e.g. torch/dill
        # stubs), the legacy media module may fail to import due to optional
        # audio/ML dependencies. In that case, fall back to a read-only router
        # that still exposes the modularized endpoints (list/detail/versions,
        # metadata search, etc.) so focused tests can run.
        logger.warning(
            "Legacy media module unavailable; falling back to read-only media "
            "router subset only: {}",
            _legacy_import_err,
        )
        _legacy_media = None  # type: ignore[assignment]
        legacy_router = APIRouter()
else:
    logger.info("TLDW_DISABLE_LEGACY_MEDIA=1 set; using modular media router only.")
    _legacy_media = None  # type: ignore[assignment]
    legacy_router = APIRouter()

# New modular routers take precedence for overlapping paths by
# prepending their routes ahead of the legacy ones. This keeps
# the effective router object compatible with existing imports
# while allowing gradual extraction into submodules.
from . import (
    add,
    debug,
    ingest_web_content,
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
    transcription_models,
)

if legacy_router.routes:
    original_legacy_router = legacy_router
    combined_router = APIRouter()

    # Manually merge route objects to avoid FastAPI's restriction on
    # include_router with empty prefixes and empty paths. This keeps
    # modular routes ahead of legacy ones without changing behavior.
    for _router in (
        listing.router,
        item.router,
        versions.router,
        add.router,
        debug.router,
        ingest_web_content.router,
        process_code.router,
        process_documents.router,
        process_pdfs.router,
        process_ebooks.router,
        process_emails.router,
        process_videos.router,
        process_audios.router,
        process_web_scraping.router,
        process_mediawiki.router,
        transcription_models.router,
        original_legacy_router,
    ):
        for route in _router.routes:
            combined_router.routes.append(route)

    router: APIRouter = combined_router
else:
    # Fallback: expose only the modular endpoints when legacy media cannot
    # be imported (ultra-minimal test profiles).
    router = APIRouter()
    for _router in (
        listing.router,
        item.router,
        versions.router,
        add.router,
        debug.router,
        ingest_web_content.router,
        process_code.router,
        process_documents.router,
        process_pdfs.router,
        process_ebooks.router,
        process_emails.router,
        process_videos.router,
        process_audios.router,
        process_web_scraping.router,
        process_mediawiki.router,
        transcription_models.router,
    ):
        for route in _router.routes:
            router.routes.append(route)

# Commonly imported helpers (kept explicit for type checkers).
if _legacy_media is not None:
    _download_url_async = getattr(_legacy_media, "_download_url_async", None)
    _save_uploaded_files = getattr(
        _legacy_media,
        "_save_uploaded_files",
        core_save_uploaded_files,
    )
    TempDirManager = getattr(
        _legacy_media,
        "TempDirManager",
        CoreTempDirManager,
    )
    from tldw_Server_API.app.api.v1.API_Deps.validations_deps import (  # type: ignore  # noqa: E501
        file_validator_instance as core_file_validator_instance,
    )
    file_validator_instance = getattr(  # type: ignore[assignment]
        _legacy_media,
        "file_validator_instance",
        core_file_validator_instance,
    )
    # Shared cache reference; tests monkeypatch `media.cache` and we
    # propagate that into the legacy module on each call that uses it.
    cache = getattr(_legacy_media, "cache", None)
else:  # pragma: no cover - only used in ultra-minimal test profiles
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.download_utils import (  # type: ignore  # noqa: E501
            download_url_async as _core_download_url_async,
        )
    except Exception:  # pragma: no cover - ultra-minimal profiles
        _core_download_url_async = None  # type: ignore[assignment]
    _download_url_async = _core_download_url_async  # type: ignore[assignment]
    _save_uploaded_files = core_save_uploaded_files  # type: ignore[assignment]
    TempDirManager = CoreTempDirManager  # type: ignore[assignment]
    # When legacy media is disabled, expose a simple in-memory cache-like
    # object so tests that monkeypatch `media.cache` still see their calls.
    class _DummyCache(dict):  # pragma: no cover - behaviour exercised via tests
        def setex(self, key, ttl, value):
            self[key] = value

        def get(self, key):
            return super().get(key)

        def delete(self, *keys):
            deleted = 0
            for k in keys:
                k = k.decode() if isinstance(k, (bytes, bytearray)) else k
                if k in self:
                    del self[k]
                    deleted += 1
            return deleted

        def sadd(self, key, member):
            s = self.setdefault(key, set())
            s.add(member)

        def smembers(self, key):
            v = self.get(key)
            return set(v) if isinstance(v, set) else set()

        def expire(self, key, ttl):
            return True

        def scan(self, cursor=0, match=None, count=None):
            return 0, []

    cache = _DummyCache()  # type: ignore[assignment]
    try:
        from tldw_Server_API.app.api.v1.API_Deps.validations_deps import (  # type: ignore  # noqa: E501
            file_validator_instance as core_file_validator_instance,
        )

        file_validator_instance = core_file_validator_instance  # type: ignore[assignment]
    except Exception:  # pragma: no cover - ultra-minimal profiles
        file_validator_instance = None  # type: ignore[assignment]

# Core-backed document-like processor shim so tests and orchestration
# can refer to a stable name without depending directly on the legacy
# module. This wrapper imports the core helper at call time so that
# tests which monkeypatch `persistence.process_document_like_item`
# continue to see their patches when callers go through
# `media._process_document_like_item`.
async def _process_document_like_item(*args, **kwargs):  # type: ignore[override]
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing import (  # type: ignore  # noqa: E501
            persistence as _persistence_mod,
        )
        impl = getattr(_persistence_mod, "process_document_like_item")
    except Exception as exc:  # pragma: no cover - ultra-minimal profiles
        raise RuntimeError(
            "process_document_like_item is not available in persistence module",
        ) from exc
    return await impl(*args, **kwargs)

import aiofiles as _aiofiles  # type: ignore

# Expose processing libraries and aiofiles at module level so tests can patch
# them via `endpoints.media` regardless of legacy media availability.
try:  # pragma: no cover - exercised via tests
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib as books  # type: ignore[assignment]
except Exception:  # pragma: no cover - defensive fallback
    books = None  # type: ignore[assignment]

try:  # pragma: no cover - exercised via tests
    import tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib as pdf_lib  # type: ignore[assignment]
except Exception:  # pragma: no cover
    pdf_lib = None  # type: ignore[assignment]

try:  # pragma: no cover - exercised via tests
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files as docs  # type: ignore[assignment]
except Exception:  # pragma: no cover
    docs = None  # type: ignore[assignment]

# Ensure aiofiles module used by core upload helpers is patchable via
# `endpoints.media.aiofiles` in tests.
aiofiles = getattr(_legacy_media, "aiofiles", _aiofiles) if _legacy_media is not None else _aiofiles  # type: ignore[assignment]


def cache_response(key: str, response: Dict) -> None:
    """
    Delegate cache_response to the legacy module when available while
    honoring monkeypatches of `media.cache` in tests.

    When legacy media is disabled, implement a minimal in-memory
    cache/indexing behaviour so unit tests can still observe the
    expected Redis-like calls on the `cache` object.
    """
    if _legacy_media is None:
        # Minimal reimplementation of the legacy behaviour using the
        # local `cache` object (which tests may monkeypatch).
        if cache is None:
            return
        try:
            import json as _json
            import hashlib as _hashlib

            content = _json.dumps(response)
            etag = _hashlib.md5(content.encode()).hexdigest()
            # Tests only assert that setex is called; TTL value is not
            # significant here, so use a fixed, reasonable default.
            cache.setex(key, 300, f"{etag}|{content}")
            # Index cache keys by media ID for invalidate_cache
            try:
                parts = key.split(":", 2)
                if len(parts) >= 3:
                    path = parts[1]
                    if path.startswith("/api/v1/media/"):
                        seg = path[len("/api/v1/media/"):].split("/", 1)[0]
                        try:
                            media_id_int = int(seg)
                        except Exception:
                            media_id_int = None
                        if media_id_int is not None:
                            idx_key = f"cacheidx:/api/v1/media/{media_id_int}"
                            try:
                                cache.sadd(idx_key, key)
                                cache.expire(idx_key, 300)
                            except Exception:
                                pass
            except Exception:
                pass
        except Exception:
            return
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
    Delegate invalidate_cache to the legacy module when available while
    honoring monkeypatches of `media.cache` in tests.

    When legacy media is disabled, provide a simplified invalidation
    that mirrors the original index + SCAN fallback logic closely
    enough for unit tests.
    """
    if _legacy_media is None:
        if cache is None:
            return
        idx_key = f"cacheidx:/api/v1/media/{media_id}"
        try:
            # Preferred path: use the indexed keys set.
            keys = set()
            try:
                keys = cache.smembers(idx_key)  # type: ignore[attr-defined]
            except Exception:
                keys = set()
            for k in keys or []:
                cache.delete(k)
            # Best-effort: delete the index itself.
            try:
                cache.delete(idx_key)
            except Exception:
                pass
            # Fallback: SCAN for matching keys when index missing.
            if not keys:
                try:
                    cursor = 0
                    pattern = f"cache:/api/v1/media/{media_id}:*"
                    while True:
                        cursor, found = cache.scan(cursor=cursor, match=pattern, count=100)  # type: ignore[attr-defined]
                        for k in found or []:
                            cache.delete(k)
                        if not cursor:
                            break
                except Exception:
                    pass
        except Exception:
            return
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
    "_process_document_like_item",
    "TempDirManager",
    "cache",
    "cache_response",
    "invalidate_cache",
    "file_validator_instance",
]
