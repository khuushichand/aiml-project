import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.watchlists_schemas import (
    TemplateComposerFlowCheckRequest,
    TemplateComposerFlowSection,
    TemplateComposerSectionRequest,
    WatchlistTemplateCreateRequest,
    WatchlistTemplateDetail,
)


pytestmark = pytest.mark.unit


def test_template_create_request_accepts_composer_metadata():
    model = WatchlistTemplateCreateRequest(
        name="composer_contract",
        format="md",
        content="# {{ title }}",
        overwrite=True,
        composer_ast={"nodes": [{"id": "header-1", "type": "HeaderBlock"}]},
        composer_schema_version="1.0.0",
        composer_sync_hash="abc123",
        composer_sync_status="in_sync",
    )

    payload = model.model_dump()
    assert payload["composer_ast"]["nodes"][0]["type"] == "HeaderBlock"
    assert payload["composer_schema_version"] == "1.0.0"
    assert payload["composer_sync_hash"] == "abc123"
    assert payload["composer_sync_status"] == "in_sync"


def test_template_detail_exposes_composer_metadata_fields():
    model = WatchlistTemplateDetail(
        name="composer_contract",
        format="md",
        description="test",
        updated_at="2026-02-23T12:00:00Z",
        version=2,
        history_count=1,
        content="# {{ title }}",
        available_versions=[1, 2],
        composer_ast={"nodes": [{"id": "raw-1", "type": "RawCodeBlock", "source": "{% macro x() %}"}]},
        composer_schema_version="1.0.0",
        composer_sync_hash="def456",
        composer_sync_status="recovered_from_code",
    )

    payload = model.model_dump()
    assert payload["composer_ast"]["nodes"][0]["type"] == "RawCodeBlock"
    assert payload["composer_schema_version"] == "1.0.0"
    assert payload["composer_sync_hash"] == "def456"
    assert payload["composer_sync_status"] == "recovered_from_code"


def test_template_composer_section_request_rejects_whitespace_fields():
    with pytest.raises(ValidationError):
        TemplateComposerSectionRequest(
            run_id=1,
            block_id="   ",
            prompt="Write summary.",
            input_scope="all_items",
            length_target="medium",
        )

    with pytest.raises(ValidationError):
        TemplateComposerSectionRequest(
            run_id=1,
            block_id="intro",
            prompt="   ",
            input_scope="all_items",
            length_target="medium",
        )


def test_template_composer_flow_section_rejects_whitespace_id():
    with pytest.raises(ValidationError):
        TemplateComposerFlowSection(id="   ", content="Section content.")


def test_template_composer_flow_check_request_rejects_oversized_total_content():
    oversized_section = ("x" * 19999) + "."
    with pytest.raises(ValidationError):
        TemplateComposerFlowCheckRequest(
            run_id=1,
            mode="suggest_only",
            sections=[
                TemplateComposerFlowSection(id=f"sec-{index}", content=oversized_section)
                for index in range(1, 8)
            ],
        )
