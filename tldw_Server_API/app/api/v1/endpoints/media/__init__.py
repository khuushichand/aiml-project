from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.validations_deps import (
    file_validator_instance,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from tldw_Server_API.app.core.Ingestion_Media_Processing.download_utils import (
    download_url_async as _download_url_async,
)
from tldw_Server_API.app.core.http_client import adownload as _m_adownload
from tldw_Server_API.app.core.Utils.Utils import smart_download as _smart_download
from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import (
    TempDirManager as CoreTempDirManager,
    save_uploaded_files as core_save_uploaded_files,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.persistence import (
    validate_add_media_inputs as _validate_inputs,
)
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import get_document_version

# Processing libraries re-exported for tests/monkeypatching
import tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib as books  # type: ignore  # pragma: no cover
import tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib as pdf_lib  # type: ignore  # pragma: no cover
import tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files as docs  # type: ignore  # pragma: no cover
from tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib import (
    process_videos as _process_videos_core,  # type: ignore  # pragma: no cover
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Files import (
    process_audio_files as _process_audio_files_core,  # type: ignore  # pragma: no cover
)
from tldw_Server_API.app.core.Chunking.templates import TemplateClassifier  # pragma: no cover
import aiofiles  # type: ignore  # pragma: no cover
from fastapi import Depends  # pragma: no cover
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user  # pragma: no cover
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_usage_event_logger  # pragma: no cover
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase  # pragma: no cover
try:
    # Optional shim so tests can monkeypatch media.process_web_scraping_task
    from tldw_Server_API.app.services.web_scraping_service import process_web_scraping_task  # pragma: no cover
except Exception:  # pragma: no cover - keep import failures isolated during minimal start
    process_web_scraping_task = None  # type: ignore[assignment]


# Router wiring (modular endpoints only) - import modules explicitly to avoid
# name collisions with core processing helpers that share similar names.
from tldw_Server_API.app.api.v1.endpoints.media import add as add_endpoint  # noqa: E402
from tldw_Server_API.app.api.v1.endpoints.media import debug as debug_endpoint  # noqa: E402
from tldw_Server_API.app.api.v1.endpoints.media import (
    ingest_web_content as ingest_web_content_endpoint,  # noqa: E402
)
from tldw_Server_API.app.api.v1.endpoints.media import (
    ingest_jobs as ingest_jobs_endpoint,  # noqa: E402
)
from tldw_Server_API.app.api.v1.endpoints.media import item as item_endpoint  # noqa: E402
from tldw_Server_API.app.api.v1.endpoints.media import listing as listing_endpoint  # noqa: E402
from tldw_Server_API.app.api.v1.endpoints.media import versions as versions_endpoint  # noqa: E402
from tldw_Server_API.app.api.v1.endpoints.media import (
    process_code as process_code_endpoint,  # noqa: E402
)
from tldw_Server_API.app.api.v1.endpoints.media import (
    process_documents as process_documents_endpoint,  # noqa: E402
)
from tldw_Server_API.app.api.v1.endpoints.media import (
    process_pdfs as process_pdfs_endpoint,  # noqa: E402
)
from tldw_Server_API.app.api.v1.endpoints.media import (
    process_ebooks as process_ebooks_endpoint,  # noqa: E402
)
from tldw_Server_API.app.api.v1.endpoints.media import (
    process_emails as process_emails_endpoint,  # noqa: E402
)
from tldw_Server_API.app.api.v1.endpoints.media import (
    process_videos as process_videos_endpoint,  # noqa: E402
)
from tldw_Server_API.app.api.v1.endpoints.media import (
    process_audios as process_audios_endpoint,  # noqa: E402
)
from tldw_Server_API.app.api.v1.endpoints.media import (
    process_web_scraping as process_web_scraping_endpoint,  # noqa: E402
)
from tldw_Server_API.app.api.v1.endpoints.media import (
    process_mediawiki as process_mediawiki_endpoint,  # noqa: E402
)
from tldw_Server_API.app.api.v1.endpoints.media import (
    reprocess as reprocess_endpoint,  # noqa: E402
)
from tldw_Server_API.app.api.v1.endpoints.media import (
    transcription_models as transcription_models_endpoint,  # noqa: E402
)
from tldw_Server_API.app.api.v1.endpoints.media import file as file_endpoint  # noqa: E402


router = APIRouter()
for _router in (
    listing_endpoint.router,
    item_endpoint.router,
    versions_endpoint.router,
    file_endpoint.router,
    add_endpoint.router,
    debug_endpoint.router,
    ingest_web_content_endpoint.router,
    ingest_jobs_endpoint.router,
    process_code_endpoint.router,
    process_documents_endpoint.router,
    process_pdfs_endpoint.router,
    process_ebooks_endpoint.router,
    process_emails_endpoint.router,
    process_videos_endpoint.router,
    process_audios_endpoint.router,
    process_web_scraping_endpoint.router,
    process_mediawiki_endpoint.router,
    reprocess_endpoint.router,
    transcription_models_endpoint.router,
):
    for route in _router.routes:
        router.routes.append(route)


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


def cache_response(key: str, response: Dict) -> None:
    """Minimal cache impl so tests can monkeypatch `media.cache`."""
    if cache is None:
        return
    try:
        import json as _json
        import hashlib as _hashlib

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
        except Exception:
            keys = set()
        for k in keys or []:
            cache.delete(k)
        try:
            cache.delete(idx_key)
        except Exception:
            pass
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


# Core-backed document-like processor shim so tests can patch core helper via media.*
async def _process_document_like_item(*args, **kwargs):  # type: ignore[override]
    from tldw_Server_API.app.core.Ingestion_Media_Processing import (  # type: ignore
        persistence as _persistence_mod,
    )

    impl = getattr(_persistence_mod, "process_document_like_item")
    return await impl(*args, **kwargs)


# Convenience exports for tests/patching (legacy-compatible names)
process_document_content = getattr(docs, "process_document_content", None)
process_pdf_task = getattr(pdf_lib, "process_pdf_task", None)
process_epub = getattr(books, "process_epub", None)
process_videos = _process_videos_core
process_audio_files = _process_audio_files_core


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
