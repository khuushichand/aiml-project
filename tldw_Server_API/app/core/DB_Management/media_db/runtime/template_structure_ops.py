"""Runtime-owned wrappers for chunking-template and structure-index helpers."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.media_db import api as media_db_api


def list_chunking_templates(
    self,
    include_builtin: bool = True,
    include_custom: bool = True,
    tags: list[str] | None = None,
    user_id: str | None = None,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    return media_db_api.list_chunking_templates(
        self,
        include_builtin=include_builtin,
        include_custom=include_custom,
        tags=tags,
        user_id=user_id,
        include_deleted=include_deleted,
    )


def seed_builtin_templates(self, templates: list[dict[str, Any]]) -> int:
    return media_db_api.seed_builtin_templates(self, templates)


def lookup_section_for_offset(
    self,
    media_id: int,
    char_offset: int,
) -> dict[str, Any] | None:
    return media_db_api.lookup_section_for_offset(self, media_id, char_offset)


def lookup_section_by_heading(
    self,
    media_id: int,
    heading: str,
) -> tuple[int, int, str] | None:
    return media_db_api.lookup_section_by_heading(self, media_id, heading)


__all__ = [
    "list_chunking_templates",
    "seed_builtin_templates",
    "lookup_section_for_offset",
    "lookup_section_by_heading",
]
