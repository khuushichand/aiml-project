from __future__ import annotations

import os
import platform

import pytest

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
from tldw_Server_API.app.core.LLM_Calls.providers import mlx_provider as mp
from tldw_Server_API.app.core.LLM_Calls import adapter_shims


IS_APPLE = platform.system() == "Darwin"


def _require_mlx_model_path() -> str:
    if not IS_APPLE:
        pytest.skip("MLX integration tests run only on Apple hosts", allow_module_level=False)
    try:
        import mlx_lm  # type: ignore[import]
    except Exception:
        pytest.skip("mlx-lm is not installed; skipping MLX integration tests", allow_module_level=False)
    # Prefer explicit env overrides but default to a small, public MLX model.
    # This assumes the environment has access to the Hugging Face hub.
    model_path = (
        os.getenv("MLX_INTEGRATION_MODEL")
        or os.getenv("MLX_MODEL_PATH")
        or "Qwen/Qwen3-0.6B-MLX-4bit"
    )
    return model_path


@pytest.mark.integration
@pytest.mark.local_llm_service
def test_mlx_chat_and_stream_with_real_model():
    model_path = _require_mlx_model_path()
    reg = mp.get_mlx_registry()
    try:
        status = reg.load(model_path=model_path, overrides={"max_concurrent": 1, "warmup": False})
    except ChatProviderError as exc:
        pytest.skip(f"MLX model unavailable for integration test: {exc}", allow_module_level=False)
    assert status["active"] is True
    assert status["model"] == model_path

    chat_adapter = mp.MLXChatAdapter()
    chat_resp = chat_adapter.chat(
        {
            "messages": [{"role": "user", "content": "hello from test"}],
            "model": model_path,
            "max_tokens": 16,
        }
    )
    content = chat_resp["choices"][0]["message"]["content"]
    assert isinstance(content, str)
    assert content.strip() != ""

    stream_chunks = list(
        chat_adapter.stream(
            {
                "messages": [{"role": "user", "content": "hello from test"}],
                "model": model_path,
                "stream": True,
                "max_tokens": 16,
            }
        )
    )
    assert stream_chunks
    assert stream_chunks[-1].strip() == "data: [DONE]"
    assert any("data:" in c for c in stream_chunks[:-1])

    status_after = reg.status()
    if status_after.get("supports_embeddings"):
        emb_adapter = mp.MLXEmbeddingsAdapter()
        emb_resp = emb_adapter.embed({"input": "vector me", "model": model_path})
        assert emb_resp["data"]
        first_vec = emb_resp["data"][0]["embedding"]
        assert isinstance(first_vec, list)
        assert first_vec


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.local_llm_service
async def test_mlx_async_handler_with_real_model():
    model_path = _require_mlx_model_path()
    reg = mp.get_mlx_registry()
    try:
        reg.load(model_path=model_path, overrides={"max_concurrent": 1, "warmup": False})
    except ChatProviderError as exc:
        pytest.skip(f"MLX model unavailable for integration test: {exc}", allow_module_level=False)

    stream = await adapter_shims.mlx_chat_handler_async(
        input_data=[{"role": "user", "content": "hi from async test"}],
        model=model_path,
        streaming=True,
        max_tokens=16,
    )
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)
    assert chunks
    assert chunks[-1].strip() == "data: [DONE]"
    assert any("data:" in c for c in chunks[:-1])
