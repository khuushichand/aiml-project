from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError


class _FailingRegistry:
    def get_adapter(self, name: str):
        return None

    def register_adapter(self, name: str, adapter: object) -> None:
        return None


@pytest.mark.asyncio
async def test_openrouter_async_adapter_unavailable(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import legacy_chat_calls as llm

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.adapter_registry.get_registry",
        lambda: _FailingRegistry(),
        raising=True,
    )

    with pytest.raises(ChatProviderError):
        await llm.chat_with_openrouter_async(
            input_data=[{"role": "user", "content": "hi"}],
            model="m",
            api_key="k",
            app_config={},
        )


def test_anthropic_adapter_unavailable(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import legacy_chat_calls as llm

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.adapter_registry.get_registry",
        lambda: _FailingRegistry(),
        raising=True,
    )

    with pytest.raises(ChatProviderError):
        llm.chat_with_anthropic(
            input_data=[{"role": "user", "content": "hi"}],
            model="m",
            api_key="k",
        )
