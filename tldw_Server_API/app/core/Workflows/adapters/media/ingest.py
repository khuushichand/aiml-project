"""Media ingestion adapters.

This module includes adapters for media ingestion:
- media_ingest: Ingest media files
- process_media: Process media files (web scraping, PDF, ebook, XML, etc.)

Note: These adapters are complex with many inline helper functions.
They delegate to the legacy implementations for full functionality.
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.media._config import (
    MediaIngestConfig,
    ProcessMediaConfig,
)


@registry.register(
    "media_ingest",
    category="media",
    description="Ingest media files",
    parallelizable=True,
    tags=["media", "ingest"],
    config_model=MediaIngestConfig,
)
async def run_media_ingest_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Media ingestion step (v0.1 minimal) with optional yt-dlp/ffmpeg integration.

    Config:
      - sources: [{uri, media_type?}]
      - download: {enabled: bool, ydl_format?, max_filesize_mb?, retries?}
      - limits: {max_download_mb?, max_duration_sec?}
      - safety: {allowed_domains?: [string]}
      - timeout_seconds: int (enforced internally)
    Output:
      - { media_ids: [], metadata: [...], transcripts: [], rag_indexed: False }
    """
    # This adapter is complex with many inline helpers. Delegate to legacy.
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_media_ingest_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "process_media",
    category="media",
    description="Process media files",
    parallelizable=False,
    tags=["media", "processing"],
    config_model=ProcessMediaConfig,
)
async def run_process_media_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Process media ephemerally using internal services (no persistence).

    Supports kinds:
      - web_scraping (existing)
      - pdf (file_uri)
      - ebook (file_uri)
      - xml (file_uri)
      - mediawiki_dump (file_uri)
      - podcast (url)

    For smoother chains, the adapter emits a best-effort `text` field in
    outputs (e.g., first article summary/content, or extracted text), so
    downstream steps like `prompt` and `tts` can use `last.text` directly.
    """
    # This adapter is complex with many processing branches. Delegate to legacy.
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_process_media_adapter as _legacy
    return await _legacy(config, context)
