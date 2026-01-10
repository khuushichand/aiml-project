from unittest.mock import patch

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

        def raise_for_status(self):
            return None

        def json(self):
            # HF may return [[...]] for single input
            return [[0.1, 0.2]]

    def _fake_post(url, headers=None, json=None, **kwargs):  # noqa: ANN001, ARG001
        return _Resp()

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def post(self, url, headers=None, json=None, **kwargs):  # noqa: ANN001, ARG001
            return _fake_post(url, headers=headers, json=json, **kwargs)

    def _fake_create_client(*args, **kwargs):  # noqa: ANN001, ARG001
        return _FakeClient()

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.providers.huggingface_embeddings_adapter.create_client",
        _fake_create_client,
    ):
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

        def raise_for_status(self):
            return None

        def json(self):
            return [[0.1, 0.2], [0.3, 0.4]]

    def _fake_post(url, headers=None, json=None, **kwargs):  # noqa: ANN001, ARG001
        return _Resp()

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def post(self, url, headers=None, json=None, **kwargs):  # noqa: ANN001, ARG001
            return _fake_post(url, headers=headers, json=json, **kwargs)

    def _fake_create_client(*args, **kwargs):  # noqa: ANN001, ARG001
        return _FakeClient()

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.providers.huggingface_embeddings_adapter.create_client",
        _fake_create_client,
    ):
        out = adapter.embed(
            {"input": ["a", "b"], "model": "sentence-transformers/all-MiniLM-L6-v2", "api_key": "k"}
        )
        assert isinstance(out, dict)
        embs = [d["embedding"] for d in out.get("data", [])]
        assert embs == [[0.1, 0.2], [0.3, 0.4]]
