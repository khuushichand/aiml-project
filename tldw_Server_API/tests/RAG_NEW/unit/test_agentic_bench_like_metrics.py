import pytest

import tldw_Server_API.app.core.RAG.rag_service.agentic_chunker as ac
from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource


def _make_doc() -> Document:
    return Document(
        id="bm_doc",
        content=(
            "# Residuals\nResidual connections help gradient flow in deep networks.\n\n"
            "# Results\nWe ran 42 experiments and observed consistent results."
        ),
        metadata={"title": "Paper"},
        source=DataSource.MEDIA_DB,
        score=0.9,
    )


@pytest.mark.asyncio
async def test_agentic_tool_steps_and_bytes_logged(monkeypatch):
    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass
        async def retrieve(self, *args, **kwargs):
            return [_make_doc()]

    monkeypatch.setattr(ac, "MultiDatabaseRetriever", FakeRetriever)

    cfg = ac.AgenticConfig(
        top_k_docs=1,
        enable_tools=True,
        max_tool_calls=3,
        time_budget_sec=2.0,
        enable_semantic_within=True,
        enable_section_index=True,
        debug_trace=True,
    )

    res = await ac.agentic_rag_pipeline(
        query="What do residual connections do and how many experiments?",
        sources=["media_db"],
        search_mode="fts",
        agentic=cfg,
        enable_generation=False,
        debug_mode=True,
    )

    md = res.metadata or {}
    trace = md.get("tool_trace") or []
    assert isinstance(trace, list) and len(trace) >= 1
    # Each expand_window entry should carry a bytes field
    bytes_total = sum(int(t.get("bytes", 0)) for t in trace if t.get("tool") == "expand_window")
    assert bytes_total >= 0
