import asyncio
from typing import Any, Dict
from unittest.mock import patch


async def test_openai_adapter_async_wrappers_call_sync():
    from tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter import OpenAIAdapter

    # Patch the adapter's sync methods directly so no network is attempted.
    with patch(
        "tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter.OpenAIAdapter.chat",
        return_value={"ok": True},
    ) as mock_chat, patch(
        "tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter.OpenAIAdapter.stream",
        return_value=iter([]),
    ) as mock_stream:
        adapter = OpenAIAdapter()
        req = {"messages": [{"role": "user", "content": "hi"}], "model": "gpt-x", "api_key": "k"}
        # achat() should call the sync chat() under the hood
        resp = await adapter.achat(req)
        assert resp == {"ok": True}

        # astream() should wrap the sync stream() generator
        chunks = []
        async for ch in adapter.astream({**req, "stream": True}):
            chunks.append(ch)
        # Our patched stream yields nothing; just ensure iteration worked
        assert isinstance(chunks, list)
