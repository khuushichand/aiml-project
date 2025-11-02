import json
import pytest


@pytest.mark.asyncio
async def test_llamacpp_reranker_scores_all_docs_and_returns_topk(monkeypatch):
    from tldw_Server_API.app.core.RAG.rag_service.advanced_reranking import LlamaCppReranker, RerankingConfig
    from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource

    # Build > top_k documents
    N = 7
    top_k = 3
    docs = [
        Document(id=f"d{i}", content=f"doc {i}", metadata={}, source=DataSource.MEDIA_DB, score=0.0)
        for i in range(N)
    ]

    # Prepare deterministic embeddings: query then docs with decreasing similarity
    # Query vector
    emb = [[1.0, 0.0]]
    # Doc vectors with cos sim 1.0, 0.9, 0.8, ..., 0.1
    for i in range(N):
        emb.append([1.0 - 0.1 * i, 0.0])

    # Capture subprocess creation args
    captured_cmd = {"args": None}

    class _FakeProc:
        def __init__(self, out):
            self._out = out
            self.returncode = 0

        async def communicate(self):
            return (self._out, b"")

    async def _fake_cpe(*args, **kwargs):  # noqa: ANN001
        captured_cmd["args"] = list(args)
        out = json.dumps({"embeddings": emb}).encode("utf-8")
        return _FakeProc(out)

    # Patch the module-local asyncio reference used in reranker
    import tldw_Server_API.app.core.RAG.rag_service.advanced_reranking as ar
    monkeypatch.setattr(ar.asyncio, "create_subprocess_exec", _fake_cpe)

    # Configure reranker with a dummy model and top_k
    cfg = RerankingConfig(top_k=top_k, model_name="dummy.gguf")
    rr = LlamaCppReranker(cfg)

    # Run
    result = await rr.rerank("query", docs)

    # Assert we returned exactly top_k
    assert len(result) == top_k

    # Assert the subprocess prompt included all documents (count separators equals N)
    assert captured_cmd["args"] is not None
    args_list = captured_cmd["args"]
    # Locate prompt in args (after '-p')
    p_idx = args_list.index("-p")
    prompt = args_list[p_idx + 1]
    sep = rr.sep
    assert prompt.count(sep) == N, f"Expected {N} separators for {N} docs"

    # Assert ranking corresponds to highest similarity first -> first top_k docs
    ranked_ids = [sd.document.id for sd in result]
    assert ranked_ids == [f"d{i}" for i in range(top_k)]
