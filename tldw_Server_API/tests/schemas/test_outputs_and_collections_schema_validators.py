from __future__ import annotations

import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.collections_feeds_schemas import (
    CollectionsFeedCreateRequest,
    CollectionsFeedUpdateRequest,
)
from tldw_Server_API.app.api.v1.schemas.outputs_templates_schemas import (
    OutputTemplateCreate,
    TemplatePreviewRequest,
)


def test_output_template_create_accepts_matching_markdown_type_and_format() -> None:
    payload = {
        "name": "briefing-template",
        "type": "briefing_markdown",
        "format": "md",
        "body": "# Briefing\n",
    }
    model = OutputTemplateCreate.model_validate(payload)
    assert model.type == "briefing_markdown"
    assert model.format == "md"


@pytest.mark.parametrize(
    ("template_type", "template_format", "expected_message"),
    [
        ("newsletter_markdown", "html", "Markdown-type templates must use format 'md'."),
        ("newsletter_html", "md", "newsletter_html templates must use format 'html'."),
        ("tts_audio", "html", "tts_audio templates must use format 'mp3'."),
    ],
)
def test_output_template_create_rejects_format_type_mismatch(
    template_type: str,
    template_format: str,
    expected_message: str,
) -> None:
    payload = {
        "name": "invalid-template",
        "type": template_type,
        "format": template_format,
        "body": "body",
    }
    with pytest.raises(ValidationError, match=expected_message):
        OutputTemplateCreate.model_validate(payload)


def test_template_preview_request_requires_one_preview_source() -> None:
    with pytest.raises(ValidationError, match="Provide item_ids, run_id, or inline data for preview."):
        TemplatePreviewRequest.model_validate({"template_id": 1})


def test_template_preview_request_accepts_inline_data_without_item_ids_or_run_id() -> None:
    model = TemplatePreviewRequest.model_validate(
        {
            "template_id": 1,
            "data": {"items": [{"title": "A"}]},
        }
    )
    assert model.template_id == 1
    assert model.data == {"items": [{"title": "A"}]}


def test_collections_feed_create_request_strips_tag_whitespace() -> None:
    model = CollectionsFeedCreateRequest.model_validate(
        {
            "url": "https://example.com/feed.xml",
            "tags": ["  news ", "tech  ", "  ai  "],
        }
    )
    assert model.tags == ["news", "tech", "ai"]


def test_collections_feed_update_request_strips_tag_whitespace_and_keeps_none() -> None:
    update_model = CollectionsFeedUpdateRequest.model_validate({"tags": ["  alpha ", " beta"]})
    assert update_model.tags == ["alpha", "beta"]

    none_model = CollectionsFeedUpdateRequest.model_validate({"name": "no-tags-change"})
    assert none_model.tags is None
