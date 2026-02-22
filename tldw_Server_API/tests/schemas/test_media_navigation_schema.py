from __future__ import annotations

import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.media_navigation_schemas import (
    MediaNavigationContentQueryParams,
    MediaNavigationNode,
    coerce_media_navigation_format,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("auto", "auto"),
        ("AUTO", "auto"),
        (" markdown ", "markdown"),
        ("HTML", "html"),
        (None, "auto"),
        ("", "auto"),
    ],
)
def test_coerce_media_navigation_format_normalizes_known_values(raw, expected) -> None:
    assert coerce_media_navigation_format(raw) == expected


@pytest.mark.parametrize("raw", ["rich", "text", "json", "md", "plain_text"])
def test_coerce_media_navigation_format_rejects_unknown_values(raw) -> None:
    with pytest.raises(ValueError):
        coerce_media_navigation_format(raw)


def test_content_query_params_coerces_format_case_insensitively() -> None:
    params = MediaNavigationContentQueryParams.model_validate(
        {"format": "MARKDOWN", "include_alternates": True}
    )
    assert params.format == "markdown"
    assert params.include_alternates is True


def test_content_query_params_rejects_invalid_format() -> None:
    with pytest.raises(ValidationError):
        MediaNavigationContentQueryParams.model_validate({"format": "rich"})


def test_navigation_node_target_type_is_case_insensitive() -> None:
    node = MediaNavigationNode.model_validate(
        {
            "id": "sec_1_2",
            "parent_id": "sec_1",
            "level": 2,
            "title": "Section 1.2",
            "order": 2,
            "path_label": "1.2",
            "target_type": "CHAR_RANGE",
            "target_start": 100,
            "target_end": 250,
            "target_href": None,
            "source": "document_structure_index",
            "confidence": 0.9,
        }
    )
    assert node.target_type == "char_range"
    assert node.target_start == 100
    assert node.target_end == 250


def test_navigation_node_rejects_external_href_targets() -> None:
    with pytest.raises(ValidationError):
        MediaNavigationNode.model_validate(
            {
                "id": "sec_2",
                "parent_id": None,
                "level": 1,
                "title": "External Link",
                "order": 1,
                "target_type": "href",
                "target_start": None,
                "target_end": None,
                "target_href": "https://example.com",
                "source": "pdf_outline",
                "confidence": 0.8,
            }
        )
