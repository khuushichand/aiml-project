from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from tldw_Server_API.app.core.Claims_Extraction.claims_engine import ClaimsEngine
from tldw_Server_API.app.core.Claims_Extraction.ingestion_claims import extract_claims_for_chunks
from tldw_Server_API.app.core.config import settings


class _Doc:
    def __init__(self, id: str, content: str, score: float = 0.0):
        self.id = id
        self.content = content
        self.score = score


class _Adapter:
    def __init__(self, capabilities: dict[str, Any]):
        self._capabilities = capabilities

    def capabilities(self) -> dict[str, Any]:
        return self._capabilities


class _Registry:
    def __init__(self, adapter: _Adapter):
        self._adapter = adapter

    def get_adapter(self, _name: str) -> _Adapter:
        return self._adapter


@pytest.mark.unit
@pytest.mark.parametrize(
    ("allowed_fields", "response_format_types", "expected_type"),
    [
        ({"response_format"}, ["json_schema", "json_object"], "json_schema"),
        ({"response_format"}, ["json_object"], "json_object"),
        ({"messages"}, ["json_schema", "json_object"], None),
    ],
)
def test_claims_engine_response_format_contract(monkeypatch, allowed_fields, response_format_types, expected_type):
    import tldw_Server_API.app.core.LLM_Calls.adapter_registry as adapter_registry
    import tldw_Server_API.app.core.LLM_Calls.adapter_utils as adapter_utils
    import tldw_Server_API.app.core.LLM_Calls.capability_registry as capability_registry

    monkeypatch.setattr(capability_registry, "get_allowed_fields", lambda _provider: allowed_fields)
    monkeypatch.setattr(adapter_utils, "normalize_provider", lambda provider: provider)
    monkeypatch.setattr(
        adapter_registry,
        "get_registry",
        lambda: _Registry(_Adapter({"response_format_types": response_format_types})),
    )
    monkeypatch.setitem(settings, "CLAIMS_LLM_PROVIDER", "openai")

    observed: list[Any] = []

    def _analyze(
        api_name: str,
        input_data: Any,
        custom_prompt_arg: str | None = None,
        api_key: str | None = None,
        system_message: str | None = None,
        temp: float | None = None,
        **kwargs: Any,
    ) -> str:
        observed.append(kwargs.get("response_format"))
        if system_message and "fact-checking judge" in system_message:
            return '{"label":"nei","confidence":0.4,"rationale":"contract"}'
        return '{"claims":[{"text":"Contract claim"}]}'

    engine = ClaimsEngine(_analyze)

    async def _run() -> None:
        result = await engine.run(
            answer="Contract claim.",
            query="Q",
            documents=[_Doc("d1", "Contract claim context.", 0.8)],
            claim_extractor="llm",
            claim_verifier="llm",
            claims_max=2,
        )
        assert result.get("claims")

    asyncio.run(_run())

    if expected_type is None:
        assert observed and all(fmt is None for fmt in observed)
    else:
        assert any(isinstance(fmt, dict) and fmt.get("type") == expected_type for fmt in observed)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("allowed_fields", "response_format_types", "expected_type"),
    [
        ({"response_format"}, ["json_schema", "json_object"], "json_schema"),
        ({"response_format"}, ["json_object"], "json_object"),
        ({"messages"}, ["json_schema", "json_object"], None),
    ],
)
def test_ingestion_response_format_contract(monkeypatch, allowed_fields, response_format_types, expected_type):
    import tldw_Server_API.app.core.Claims_Extraction.ingestion_claims as ingestion_mod
    import tldw_Server_API.app.core.LLM_Calls.adapter_registry as adapter_registry
    import tldw_Server_API.app.core.LLM_Calls.adapter_utils as adapter_utils
    import tldw_Server_API.app.core.LLM_Calls.capability_registry as capability_registry

    monkeypatch.setattr(capability_registry, "get_allowed_fields", lambda _provider: allowed_fields)
    monkeypatch.setattr(adapter_utils, "normalize_provider", lambda provider: provider)
    monkeypatch.setattr(
        adapter_registry,
        "get_registry",
        lambda: _Registry(_Adapter({"response_format_types": response_format_types})),
    )
    monkeypatch.setitem(settings, "CLAIMS_JSON_PARSE_MODE", "lenient")

    observed: dict[str, Any] = {}

    def _fake_chat_api_call(
        api_endpoint,
        messages_payload,
        api_key=None,
        temp=None,
        system_message=None,
        streaming=False,
        model=None,
        response_format=None,
        **kwargs,
    ):
        observed["response_format"] = response_format
        payload = {"claims": [{"text": "Ingestion contract claim."}]}
        return f"```json\n{json.dumps(payload)}\n```"

    monkeypatch.setattr(ingestion_mod, "chat_api_call", _fake_chat_api_call, raising=False)

    claims = extract_claims_for_chunks(
        [{"text": "irrelevant", "metadata": {"chunk_index": 0}}],
        extractor_mode="openai",
        max_per_chunk=3,
    )
    assert claims
    if expected_type is None:
        assert observed.get("response_format") is None
    else:
        response_format = observed.get("response_format")
        assert isinstance(response_format, dict)
        assert response_format.get("type") == expected_type
