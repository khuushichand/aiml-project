import os
from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_google_embeddings_adapter_native_http_single(monkeypatch):
    monkeypatch.setenv("LLM_EMBEDDINGS_NATIVE_HTTP_GOOGLE", "1")

    from tldw_Server_API.app.core.LLM_Calls.providers.google_embeddings_adapter import (
        GoogleEmbeddingsAdapter,
    )

    adapter = GoogleEmbeddingsAdapter()

    class _Resp:
        status_code = 200

        def json(self):
            return {"embedding": {"values": [0.5, 0.6]}}

    def _fake_post(self, url, params=None, json=None, headers=None, **kwargs):  # noqa: ANN001, ARG001
        return _Resp()

    with patch("httpx.Client.post", _fake_post):
        out = adapter.embed({"input": "hello", "model": "text-embedding-004", "api_key": "g"})
        assert isinstance(out, dict)
        assert out.get("data") and out["data"][0]["embedding"] == [0.5, 0.6]


@pytest.mark.unit
def test_google_embeddings_adapter_native_http_multi(monkeypatch):
    monkeypatch.setenv("LLM_EMBEDDINGS_NATIVE_HTTP_GOOGLE", "1")

    from tldw_Server_API.app.core.LLM_Calls.providers.google_embeddings_adapter import (
        GoogleEmbeddingsAdapter,
    )

    adapter = GoogleEmbeddingsAdapter()

    seq = [
        {"embedding": {"values": [0.1, 0.2]}},
        {"embedding": {"values": [0.3, 0.4]}},
    ]
    calls = {"i": 0}

    class _Resp:
        status_code = 200

        def json(self):
            i = calls["i"]
            calls["i"] += 1
            return seq[i]

    def _fake_post(self, url, params=None, json=None, headers=None, **kwargs):  # noqa: ANN001, ARG001
        return _Resp()

    with patch("httpx.Client.post", _fake_post):
        out = adapter.embed({"input": ["a", "b"], "model": "text-embedding-004", "api_key": "g"})
        assert isinstance(out, dict)
        embs = [d["embedding"] for d in out.get("data", [])]
        assert embs == [[0.1, 0.2], [0.3, 0.4]]
