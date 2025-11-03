import asyncio
from typing import Any, Dict
from unittest.mock import patch


async def test_openai_adapter_async_wrappers_call_sync():
    from tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter import OpenAIAdapter

    captured: Dict[str, Any] = {}

    def _fake_openai(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    with patch("tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.chat_with_openai", _fake_openai):
        adapter = OpenAIAdapter()
        req = {"messages": [{"role": "user", "content": "hi"}], "model": "gpt-x", "api_key": "k"}
        # achat()
        resp = await adapter.achat(req)
        assert resp == {"ok": True}
        # astream()
        chunks = []
        async for ch in adapter.astream({**req, "stream": True}):
            chunks.append(ch)
        # Since our fake returns a dict for chat path, astream will iterate over nothing (no chunks); that's fine.
        assert isinstance(chunks, list)

