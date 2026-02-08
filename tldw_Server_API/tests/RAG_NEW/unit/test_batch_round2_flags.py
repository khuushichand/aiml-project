import pytest

from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedBatchRequest
import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as up


pytestmark = pytest.mark.unit


def test_unified_batch_request_accepts_round2_fields():
    req = UnifiedBatchRequest(
        queries=["q1", "q2"],
        enable_suggestions=True,
        num_suggestions=7,
        enable_structured_response=True,
        enable_image_search=True,
        enable_video_search=False,
    )

    assert req.enable_suggestions is True
    assert req.num_suggestions == 7
    assert req.enable_structured_response is True
    assert req.enable_image_search is True
    assert req.enable_video_search is False


@pytest.mark.asyncio
async def test_unified_batch_pipeline_forwards_round2_flags(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")

    captured: list[dict[str, object]] = []

    async def _fake_pipeline(query: str, **kwargs):  # noqa: ANN001
        captured.append({"query": query, **kwargs})
        return up.UnifiedSearchResult(documents=[], query=query, errors=[])

    monkeypatch.setattr(up, "unified_rag_pipeline", _fake_pipeline)

    results = await up.unified_batch_pipeline(
        queries=["round2 forwarding check"],
        max_concurrent=1,
        enable_suggestions=True,
        num_suggestions=6,
        enable_structured_response=True,
        enable_image_search=True,
        enable_video_search=True,
    )

    assert len(results) == 1
    assert len(captured) == 1
    assert captured[0]["query"] == "round2 forwarding check"
    assert captured[0]["enable_suggestions"] is True
    assert captured[0]["num_suggestions"] == 6
    assert captured[0]["enable_structured_response"] is True
    assert captured[0]["enable_image_search"] is True
    assert captured[0]["enable_video_search"] is True
