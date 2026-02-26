import pytest

from tldw_Server_API.app.api.v1.endpoints.rag_unified import list_features


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_features_endpoint_includes_clarification_and_action_dedup():
    payload = await list_features()
    generation_params = payload["features"]["generation"]["parameters"]
    assert "enable_pre_retrieval_clarification" in generation_params
    assert "clarification_timeout_sec" in generation_params
    assert "enable_research_action_dedup" in payload["features"]["resilience"]["parameters"]
