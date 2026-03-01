from unittest.mock import AsyncMock, patch

import pytest

import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as up


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_pre_retrieval_clarification_short_circuits_retrieval():
    with patch.object(
        up,
        "assess_query_for_clarification",
        new=AsyncMock(
            return_value=up.ClarificationDecision(
                required=True,
                question="Could you clarify which document you mean?",
                reason="ambiguous",
                confidence=0.9,
                detector="heuristic",
            )
        ),
    ), patch.object(up, "MultiDatabaseRetriever") as mock_retriever:
        res = await up.unified_rag_pipeline(
            query="What about that one?",
            enable_generation=True,
        )
        assert res.generated_answer == "Could you clarify which document you mean?"
        assert res.metadata["clarification"]["required"] is True
        assert res.metadata["retrieval_bypassed"]["reason"] == "pre_retrieval_clarification"
        mock_retriever.assert_not_called()
