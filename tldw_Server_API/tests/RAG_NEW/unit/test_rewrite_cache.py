import os
from pathlib import Path

from tldw_Server_API.app.core.RAG.rag_service.rewrite_cache import RewriteCache


def test_rewrite_cache_put_get(tmp_path, monkeypatch):
    p = tmp_path / "rc.jsonl"
    monkeypatch.setenv("RAG_REWRITE_CACHE_PATH", str(p))
    rc = RewriteCache()

    q = "What is CUDA?"
    rewrites = ["compute unified device architecture", "nvidia cuda"]
    rc.put(q, rewrites, intent="FACTUAL", corpus="ml")

    out = rc.get(q, intent="FACTUAL", corpus="ml")
    assert out is not None
    assert any("compute unified" in r for r in out)
