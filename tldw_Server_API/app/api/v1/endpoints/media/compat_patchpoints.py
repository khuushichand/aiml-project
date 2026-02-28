"""Compatibility patch points for media endpoint tests and shims."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.services.web_scraping_service import (
    process_web_scraping_task,
)


def _resolve_media_module(media_module: Any | None = None) -> Any:
    if media_module is not None:
        return media_module
    from tldw_Server_API.app.api.v1.endpoints import media as media_mod

    return media_mod


def get_download_url_async(media_module: Any | None = None):
    media_mod = _resolve_media_module(media_module)
    return media_mod._download_url_async


def get_save_uploaded_files(media_module: Any | None = None):
    media_mod = _resolve_media_module(media_module)
    return media_mod._save_uploaded_files


def get_process_web_scraping_task(media_module: Any | None = None):
    media_mod = _resolve_media_module(media_module)
    return getattr(media_mod, "process_web_scraping_task", process_web_scraping_task)

