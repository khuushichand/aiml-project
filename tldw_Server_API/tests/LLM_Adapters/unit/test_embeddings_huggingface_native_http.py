import os
from unittest.mock import patch, MagicMock

import pytest


@pytest.mark.unit
def test_huggingface_embeddings_adapter_native_http_single(monkeypatch):
    monkeypatch.setenv("LLM_EMBEDDINGS_NATIVE_HTTP_HUGGINGFACE", "1")

    from tldw_Server_API.app.core.LLM_Calls.providers.huggingface_embeddings_adapter import (
        HuggingFaceEmbeddingsAdapter,
    )

    adapter = HuggingFaceEmbeddingsAdapter()

    class _Resp:
        status_code = 200

        def json(self):
            # HF may return [[...]] for single input
            return [[0.1, 0.2]]

    def _fake_post(self, url, headers=None, json=None, **kwargs):  # noqa: ANN001, ARG001
        return _Resp()

    with patch("httpx.Client.post", _fake_post):
        out = adapter.embed({"input": "hi", "model": "sentence-transformers/all-MiniLM-L6-v2", "api_key": "k"})
        assert isinstance(out, dict)
        assert out.get("data") and out["data"][0]["embedding"] == [0.1, 0.2]


@pytest.mark.unit
def test_huggingface_embeddings_adapter_native_http_multi(monkeypatch):
    monkeypatch.setenv("LLM_EMBEDDINGS_NATIVE_HTTP_HUGGINGFACE", "1")

    from tldw_Server_API.app.core.LLM_Calls.providers.huggingface_embeddings_adapter import (
        HuggingFaceEmbeddingsAdapter,
    )

    adapter = HuggingFaceEmbeddingsAdapter()

    class _Resp:
        status_code = 200

        def json(self):
            return [[0.1, 0.2], [0.3, 0.4]]

    def _fake_post(self, url, headers=None, json=None, **kwargs):  # noqa: ANN001, ARG001
        return _Resp()

    with patch("httpx.Client.post", _fake_post):
        out = adapter.embed(
            {"input": ["a", "b"], "model": "sentence-transformers/all-MiniLM-L6-v2", "api_key": "k"}
        )
        assert isinstance(out, dict)
        embs = [d["embedding"] for d in out.get("data", [])]
        assert embs == [[0.1, 0.2], [0.3, 0.4]]
