import pytest

from tldw_Server_API.app.core.Claims_Extraction.output_parser import (
    ClaimsOutputNoJsonError,
    ClaimsOutputParseError,
    ClaimsOutputSchemaError,
    coerce_llm_response_text,
    extract_claim_texts,
    parse_claims_llm_output,
    resolve_claims_response_format,
)
from tldw_Server_API.app.core.exceptions import BadRequestError


@pytest.mark.unit
def test_claims_output_exceptions_inherit_core_base():
    assert issubclass(ClaimsOutputParseError, BadRequestError)
    assert issubclass(ClaimsOutputNoJsonError, BadRequestError)
    assert issubclass(ClaimsOutputSchemaError, BadRequestError)


@pytest.mark.unit
def test_parse_fenced_json_with_prose_lenient():
    raw = 'preface\n```json\n{"claims":[{"text":"Claim A"}]}\n```\npostface'
    payload = parse_claims_llm_output(raw, parse_mode="lenient")
    texts = extract_claim_texts(payload, wrapper_key="claims", parse_mode="lenient")
    assert texts == ["Claim A"]


@pytest.mark.unit
def test_parse_raw_json_and_think_tag_lenient():
    raw = "<think>reasoning</think>\n{\"claims\":[{\"text\":\"Claim B\"}]}"
    payload = parse_claims_llm_output(raw, parse_mode="lenient", strip_think_tags=True)
    texts = extract_claim_texts(payload, wrapper_key="claims", parse_mode="lenient")
    assert texts == ["Claim B"]


@pytest.mark.unit
def test_parse_raw_json_and_think_tag_strict_rejects():
    raw = "<think>reasoning</think>\n{\"claims\":[{\"text\":\"Claim B\"}]}"
    with pytest.raises(ClaimsOutputNoJsonError):
        parse_claims_llm_output(raw, parse_mode="strict", strip_think_tags=True)


@pytest.mark.unit
def test_parse_malformed_json_strict_raises():
    raw = "```json\n{\"claims\":[{\"text\":\"Missing brace\"}\n```"
    with pytest.raises(ClaimsOutputNoJsonError):
        parse_claims_llm_output(raw, parse_mode="strict")


@pytest.mark.unit
def test_parse_multi_block_uses_first_valid_block():
    raw = (
        "```json\n{not valid}\n```\n"
        "```json\n{\"claims\":[{\"text\":\"Claim C\"}]}\n```"
    )
    payload = parse_claims_llm_output(raw, parse_mode="lenient")
    texts = extract_claim_texts(payload, wrapper_key="claims", parse_mode="lenient")
    assert texts == ["Claim C"]


@pytest.mark.unit
def test_wrapper_optional_list_compatibility():
    payload = parse_claims_llm_output('[{"text":"Claim D"}]', parse_mode="lenient")
    texts = extract_claim_texts(payload, wrapper_key="claims", parse_mode="lenient")
    assert texts == ["Claim D"]


@pytest.mark.unit
def test_strict_mode_requires_wrapper_key_when_payload_is_object():
    payload = parse_claims_llm_output('{"text":"standalone"}', parse_mode="strict")
    with pytest.raises(ClaimsOutputSchemaError):
        extract_claim_texts(payload, wrapper_key="claims", parse_mode="strict")


class _Adapter:
    def __init__(self, capabilities):
        self._capabilities = capabilities

    def capabilities(self):
        return self._capabilities


class _Registry:
    def __init__(self, adapter):
        self._adapter = adapter

    def get_adapter(self, _name):
        return self._adapter


@pytest.mark.unit
def test_response_format_prefers_json_schema_when_supported(monkeypatch):
    import tldw_Server_API.app.core.LLM_Calls.adapter_registry as adapter_registry
    import tldw_Server_API.app.core.LLM_Calls.adapter_utils as adapter_utils
    import tldw_Server_API.app.core.LLM_Calls.capability_registry as capability_registry

    monkeypatch.setattr(capability_registry, "get_allowed_fields", lambda _provider: {"response_format"})
    monkeypatch.setattr(adapter_utils, "normalize_provider", lambda provider: provider)
    monkeypatch.setattr(
        adapter_registry,
        "get_registry",
        lambda: _Registry(_Adapter({"response_format_types": ["json_object", "json_schema"]})),
    )

    response_format = resolve_claims_response_format(
        "openai",
        schema_name="claims_schema",
        json_schema={"type": "object"},
    )
    assert isinstance(response_format, dict)
    assert response_format.get("type") == "json_schema"


@pytest.mark.unit
def test_response_format_uses_json_object_when_schema_not_supported(monkeypatch):
    import tldw_Server_API.app.core.LLM_Calls.adapter_registry as adapter_registry
    import tldw_Server_API.app.core.LLM_Calls.adapter_utils as adapter_utils
    import tldw_Server_API.app.core.LLM_Calls.capability_registry as capability_registry

    monkeypatch.setattr(capability_registry, "get_allowed_fields", lambda _provider: {"response_format"})
    monkeypatch.setattr(adapter_utils, "normalize_provider", lambda provider: provider)
    monkeypatch.setattr(
        adapter_registry,
        "get_registry",
        lambda: _Registry(_Adapter({"response_format_types": ["json_object"]})),
    )

    response_format = resolve_claims_response_format(
        "openai",
        schema_name="claims_schema",
        json_schema={"type": "object"},
    )
    assert response_format == {"type": "json_object"}


@pytest.mark.unit
def test_response_format_none_when_provider_blocks_field(monkeypatch):
    import tldw_Server_API.app.core.LLM_Calls.capability_registry as capability_registry

    monkeypatch.setattr(capability_registry, "get_allowed_fields", lambda _provider: {"messages"})
    response_format = resolve_claims_response_format(
        "provider-without-response-format",
        schema_name="claims_schema",
        json_schema={"type": "object"},
    )
    assert response_format is None


@pytest.mark.unit
def test_coerce_llm_response_text_prefers_choices_content():
    payload = {"choices": [{"message": {"content": "from-choices"}}]}
    assert coerce_llm_response_text(payload) == "from-choices"


@pytest.mark.unit
def test_coerce_llm_response_text_uses_response_fallback():
    payload = {"response": "fallback-text"}
    assert coerce_llm_response_text(payload) == "fallback-text"


@pytest.mark.unit
def test_coerce_llm_response_text_joins_iterables():
    assert coerce_llm_response_text(["a", "b", "c"]) == "abc"
