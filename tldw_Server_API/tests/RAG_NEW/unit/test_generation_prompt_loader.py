"""Unit tests for RAG generation prompt-template loading behavior."""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from tldw_Server_API.app.core.RAG.rag_service import generation as generation_mod
from tldw_Server_API.app.core.RAG.rag_service.generation import PromptTemplates


pytestmark = pytest.mark.unit


def test_prompt_templates_load_switchable_profile_prompt_keys() -> None:
    text = PromptTemplates.get_template("instruction_tuned")

    assert "Use the provided context" in text
    assert "{context}" in text
    assert "{question}" in text


def test_prompt_templates_falls_back_to_default_for_unknown_key() -> None:
    unknown = PromptTemplates.get_template("does_not_exist")

    assert "Context:" in unknown
    assert "Question:" in unknown


@pytest.mark.asyncio
async def test_generate_streaming_response_warms_prompt_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warmed: list[str] = []

    async def _fake_warm(name: str) -> None:
        warmed.append(name)

    class _StubGenerator:
        async def generate_stream(self, context: Any, query: str) -> AsyncIterator[str]:
            if False:
                yield ""  # pragma: no cover

    monkeypatch.setattr(PromptTemplates, "warm_template_async", _fake_warm)
    monkeypatch.setattr(generation_mod, "create_generator", lambda _config: _StubGenerator())

    ctx = SimpleNamespace(
        config={"generation": {"prompt_template": "instruction_tuned"}},
        query="warm prompt",
        metadata={},
    )

    await generation_mod.generate_streaming_response(ctx)

    assert warmed == ["instruction_tuned"]
