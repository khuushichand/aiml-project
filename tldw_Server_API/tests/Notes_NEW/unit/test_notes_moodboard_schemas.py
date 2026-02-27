from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.notes_moodboards import (
    MoodboardCreate,
    MoodboardSmartRule,
    MoodboardSmartRuleDateRange,
)


def test_moodboard_create_allows_hybrid_rule_payload():
    payload = MoodboardCreate(
        name="Research visuals",
        description="Design and writing references",
        smart_rule=MoodboardSmartRule(
            query="design system",
            keyword_tokens=["ux", "ui"],
            notebook_collection_ids=[1, 2],
            sources=["source:web:example.com"],
            updated=MoodboardSmartRuleDateRange(
                after=datetime(2026, 2, 1, tzinfo=timezone.utc),
                before=datetime(2026, 2, 26, tzinfo=timezone.utc),
            ),
        ),
    )
    assert payload.name == "Research visuals"
    assert payload.smart_rule is not None
    assert payload.smart_rule.keyword_tokens == ["ux", "ui"]


def test_moodboard_create_rejects_empty_name():
    with pytest.raises(ValidationError):
        MoodboardCreate(name="   ")
