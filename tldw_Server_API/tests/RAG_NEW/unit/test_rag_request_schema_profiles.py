import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGRequest


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("profile", ["fast", "balanced", "accuracy"])
def test_rag_profile_accepts_switchable_values(profile: str) -> None:
    req = UnifiedRAGRequest(query="q", rag_profile=profile)
    assert req.rag_profile == profile


def test_rag_profile_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        UnifiedRAGRequest(query="q", rag_profile="production")


def test_max_generation_tokens_allows_2200_but_rejects_4001() -> None:
    ok_req = UnifiedRAGRequest(query="q", max_generation_tokens=2200)
    assert ok_req.max_generation_tokens == 2200

    with pytest.raises(ValidationError):
        UnifiedRAGRequest(query="q", max_generation_tokens=4001)
