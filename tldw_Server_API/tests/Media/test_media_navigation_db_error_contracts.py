from __future__ import annotations

import pytest

from tldw_Server_API.app.api.v1.endpoints.media import navigation as navigation_mod
from tldw_Server_API.app.api.v1.schemas.media_navigation_schemas import MediaNavigationNode
from tldw_Server_API.app.core.DB_Management.media_db.errors import DatabaseError


class _DatabaseErrorDb:
    def lookup_section_by_heading(self, media_id: int, heading: str):
        raise DatabaseError("lookup failed")


class _ProgrammerErrorDb:
    def lookup_section_by_heading(self, media_id: int, heading: str):
        raise ValueError("bad lookup state")


def test_derive_content_span_swallows_typed_database_errors() -> None:
    node = MediaNavigationNode(
        id="node-1",
        parent_id=None,
        level=1,
        title="Results",
        order=0,
        path_label="1",
        target_type="href",
        target_href="#results",
        source="generated_toc",
        confidence=0.5,
    )

    result = navigation_mod._derive_content_span(
        node=node,
        all_nodes=[node],
        media={"type": "document"},
        db=_DatabaseErrorDb(),
        media_id=7,
        content_length=500,
    )

    if result is not None:
        pytest.fail(f"expected None fallback for DatabaseError, got {result!r}")


def test_derive_content_span_does_not_hide_non_database_failures() -> None:
    node = MediaNavigationNode(
        id="node-1",
        parent_id=None,
        level=1,
        title="Results",
        order=0,
        path_label="1",
        target_type="href",
        target_href="#results",
        source="generated_toc",
        confidence=0.5,
    )

    with pytest.raises(ValueError):
        navigation_mod._derive_content_span(
            node=node,
            all_nodes=[node],
            media={"type": "document"},
            db=_ProgrammerErrorDb(),
            media_id=7,
            content_length=500,
        )
