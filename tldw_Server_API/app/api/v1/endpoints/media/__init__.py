from __future__ import annotations

import importlib

from fastapi import (
    APIRouter,
)
from loguru import logger

try:
    import aiofiles  # type: ignore  # pragma: no cover
except Exception:  # pragma: no cover - optional import
    aiofiles = None  # type: ignore[assignment]

_MEDIA_IMPORT_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    ImportError,
    ModuleNotFoundError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _optional_import_module(module_path: str):
    try:
        return importlib.import_module(module_path)
    except _MEDIA_IMPORT_EXCEPTIONS as exc:
        logger.warning("Media import skipped: {} ({})", module_path, exc)
        return None


def _optional_import_attr(module_path: str, attr_name: str):
    module = _optional_import_module(module_path)
    if module is None:
        return None
    return getattr(module, attr_name, None)


# Processing libraries re-exported for tests/monkeypatching
books = _optional_import_module(
    "tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib"
)  # type: ignore[assignment]
pdf_lib = _optional_import_module(
    "tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib"
)  # type: ignore[assignment]
docs = _optional_import_module(
    "tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files"
)  # type: ignore[assignment]
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user  # pragma: no cover
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_usage_event_logger  # pragma: no cover
from tldw_Server_API.app.api.v1.API_Deps.validations_deps import (
    file_validator_instance,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
TemplateClassifier = _optional_import_attr(
    "tldw_Server_API.app.core.Chunking.templates",
    "TemplateClassifier",
)  # type: ignore[assignment]
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (
    MediaDatabase,  # pragma: no cover
    get_document_version,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.download_utils import (
    download_url_async as _download_url_async,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import (
    TempDirManager as CoreTempDirManager,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import (
    save_uploaded_files as core_save_uploaded_files,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.persistence import (
    validate_add_media_inputs as _validate_inputs,
)
# Keep heavyweight processor imports lazy to avoid hard-abort side effects
# (e.g., OpenMP/torch initialization) during router import.
_process_audio_files_core = None
_process_videos_core = None
_smart_download = _optional_import_attr(
    "tldw_Server_API.app.core.Utils.Utils",
    "smart_download",
)  # type: ignore[assignment]


def _load_process_audio_files_core():
    global _process_audio_files_core
    if _process_audio_files_core is None:
        _process_audio_files_core = _optional_import_attr(
            "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Files",
            "process_audio_files",
        )
    return _process_audio_files_core


def _load_process_videos_core():
    global _process_videos_core
    if _process_videos_core is None:
        _process_videos_core = _optional_import_attr(
            "tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib",
            "process_videos",
        )
    return _process_videos_core

try:
    # Optional shim so tests can monkeypatch media.process_web_scraping_task
    from tldw_Server_API.app.services.web_scraping_service import process_web_scraping_task  # pragma: no cover
except ImportError:  # pragma: no cover - keep import failures isolated during minimal start
    process_web_scraping_task = None  # type: ignore[assignment]


# Router wiring (modular endpoints only) - import modules explicitly to avoid
# name collisions with core processing helpers that share similar names.
import contextlib

router = APIRouter()

# Load subrouters defensively so one optional import failure does not disable
# the full media route surface.
_MEDIA_ENDPOINT_MODULES: tuple[str, ...] = (
    "listing",
    "item",
    "versions",
    "file",
    "add",
    "debug",
    "ingest_web_content",
    "ingest_jobs",
    "process_code",
    "process_documents",
    "process_pdfs",
    "process_ebooks",
    "process_emails",
    "process_videos",
    "process_audios",
    "process_web_scraping",
    "process_mediawiki",
    "reprocess",
    "transcription_models",
    "navigation",
    "document_outline",
    "document_insights",
    "document_references",
    "document_figures",
    "document_annotations",
    "reading_progress",
)


def _append_router_from_module(module_name: str) -> None:
    endpoint_module = _optional_import_module(
        f"tldw_Server_API.app.api.v1.endpoints.media.{module_name}"
    )
    if endpoint_module is None:
        return
    subrouter = getattr(endpoint_module, "router", None)
    if subrouter is None:
        logger.warning(
            "Media endpoint module '{}' has no router attribute; skipping.",
            module_name,
        )
        return
    for route in subrouter.routes:
        router.routes.append(route)


for _module_name in _MEDIA_ENDPOINT_MODULES:
    _append_router_from_module(_module_name)


# Helpers/exported patch points
_save_uploaded_files = core_save_uploaded_files
_process_uploaded_files = _save_uploaded_files  # backward-compat alias for tests
TempDirManager = CoreTempDirManager


class _DummyCache(dict):
    """Simple in-memory cache shim (Redis-like API subset)."""

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


cache = _DummyCache()
_legacy_media = None  # Backwards-compat attribute for tests expecting it.
smart_download = _smart_download  # Backwards-compat for tests monkeypatching media.smart_download
MEDIA_CACHE_EXCEPTIONS = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    OSError,
)


def cache_response(key: str, response: dict) -> None:
    """Minimal cache impl so tests can monkeypatch `media.cache`."""
    if cache is None:
        return
    try:
        import hashlib as _hashlib
        import json as _json

        content = _json.dumps(response)
        etag = _hashlib.md5(content.encode()).hexdigest()
        cache.setex(key, 300, f"{etag}|{content}")
        parts = key.split(":", 2)
        if len(parts) >= 3:
            path = parts[1]
            if path.startswith("/api/v1/media/"):
                seg = path[len("/api/v1/media/"):].split("/", 1)[0]
                try:
                    media_id_int = int(seg)
                except (TypeError, ValueError):
                    media_id_int = None
                if media_id_int is not None:
                    idx_key = f"cacheidx:/api/v1/media/{media_id_int}"
                    try:
                        cache.sadd(idx_key, key)
                        cache.expire(idx_key, 300)
                    except MEDIA_CACHE_EXCEPTIONS:
                        pass
    except (ValueError, TypeError, AttributeError, RuntimeError, OSError):
        return


def invalidate_cache(media_id: int) -> None:
    """Delete cached entries keyed by media_id."""
    if cache is None:
        return
    idx_key = f"cacheidx:/api/v1/media/{media_id}"
    try:
        keys = set()
        try:
            keys = cache.smembers(idx_key)  # type: ignore[attr-defined]
        except MEDIA_CACHE_EXCEPTIONS:
            keys = set()
        for k in keys or []:
            cache.delete(k)
        with contextlib.suppress(MEDIA_CACHE_EXCEPTIONS):
            cache.delete(idx_key)
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
            except MEDIA_CACHE_EXCEPTIONS:
                pass
    except MEDIA_CACHE_EXCEPTIONS:
        return


# Core-backed document-like processor shim so tests can patch core helper via media.*
async def _process_document_like_item(*args, **kwargs):  # type: ignore[override]
    from tldw_Server_API.app.core.Ingestion_Media_Processing import (  # type: ignore
        persistence as _persistence_mod,
    )

    impl = _persistence_mod.process_document_like_item
    return await impl(*args, **kwargs)


# Convenience exports for tests/patching (legacy-compatible names)
process_document_content = getattr(docs, "process_document_content", None)
process_pdf_task = getattr(pdf_lib, "process_pdf_task", None)
process_epub = getattr(books, "process_epub", None)


def process_videos(*args, **kwargs):
    impl = _load_process_videos_core()
    if impl is None:
        raise RuntimeError("Video processing backend is unavailable")
    return impl(*args, **kwargs)


def process_audio_files(*args, **kwargs):
    impl = _load_process_audio_files_core()
    if impl is None:
        raise RuntimeError("Audio processing backend is unavailable")
    return impl(*args, **kwargs)


__all__ = [
    "router",
    "_download_url_async",
    "_save_uploaded_files",
    "_process_uploaded_files",
    "_process_document_like_item",
    "_validate_inputs",
    "TempDirManager",
    "cache",
    "cache_response",
    "invalidate_cache",
    "get_request_user",
    "get_media_db_for_user",
    "get_usage_event_logger",
    "MediaDatabase",
    "get_document_version",
    "file_validator_instance",
    "books",
    "pdf_lib",
    "docs",
    "process_document_content",
    "process_pdf_task",
    "process_epub",
    "process_videos",
    "process_audio_files",
    "process_web_scraping_task",
    "TemplateClassifier",
    "aiofiles",
]
