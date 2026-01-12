import pytest


@pytest.mark.unit
def test_openai_embeddings_adapter_uses_batch_helper_for_list(monkeypatch):
    monkeypatch.delenv("LLM_EMBEDDINGS_NATIVE_HTTP_OPENAI", raising=False)

    from tldw_Server_API.app.core.LLM_Calls.providers.openai_embeddings_adapter import (
        OpenAIEmbeddingsAdapter,
    )

    def _fake_batch(texts, model, app_config=None, dimensions=None):  # noqa: ANN001, ARG001
        assert texts == ["a", "b"]
        return [[0.1], [0.2]]

    def _fail_single(*_args, **_kwargs):  # noqa: ANN001
        raise AssertionError("single helper should not be called for batch input")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.chat_calls.get_openai_embeddings_batch",
        _fake_batch,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.chat_calls.get_openai_embeddings",
        _fail_single,
    )

    adapter = OpenAIEmbeddingsAdapter()
    out = adapter.embed({"input": ["a", "b"], "model": "text-embedding-3-small", "app_config": {}})
    assert [item["embedding"] for item in out.get("data", [])] == [[0.1], [0.2]]


@pytest.mark.unit
def test_openai_embeddings_adapter_uses_single_helper_for_scalar(monkeypatch):
    monkeypatch.delenv("LLM_EMBEDDINGS_NATIVE_HTTP_OPENAI", raising=False)

    from tldw_Server_API.app.core.LLM_Calls.providers.openai_embeddings_adapter import (
        OpenAIEmbeddingsAdapter,
    )

    def _fail_batch(*_args, **_kwargs):  # noqa: ANN001
        raise AssertionError("batch helper should not be called for scalar input")

    def _fake_single(text, model, app_config=None, dimensions=None):  # noqa: ANN001, ARG001
        assert text == "hi"
        return [0.5, 0.6]

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.chat_calls.get_openai_embeddings_batch",
        _fail_batch,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.chat_calls.get_openai_embeddings",
        _fake_single,
    )

    adapter = OpenAIEmbeddingsAdapter()
    out = adapter.embed({"input": "hi", "model": "text-embedding-3-small", "app_config": {}})
    assert out.get("data", [])[0]["embedding"] == [0.5, 0.6]
