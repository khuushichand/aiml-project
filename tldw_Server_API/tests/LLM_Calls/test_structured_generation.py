import pytest

from tldw_Server_API.app.core.LLM_Calls.structured_generation import (
    StructuredGenerationSchemaError,
    negotiate_structured_response_mode,
    parse_and_validate_structured_output,
    validate_structured_payload,
)


@pytest.mark.unit
def test_negotiates_json_schema_when_supported():
    decision = negotiate_structured_response_mode(
        provider="openai",
        requested={
            "type": "json_schema",
            "json_schema": {"name": "answer_schema", "schema": {"type": "object"}},
        },
        provider_capabilities={"response_format_types": ["json_object", "json_schema"]},
        allowed_fields={"response_format"},
    )

    assert decision.mode_used == "json_schema"
    assert decision.fallback_used is False
    assert decision.response_format.get("type") == "json_schema"


@pytest.mark.unit
def test_falls_back_to_json_object_when_json_schema_unsupported():
    decision = negotiate_structured_response_mode(
        provider="openai",
        requested={
            "type": "json_schema",
            "json_schema": {"name": "answer_schema", "schema": {"type": "object"}},
        },
        provider_capabilities={"response_format_types": ["json_object"]},
        allowed_fields={"response_format"},
    )

    assert decision.mode_used == "json_object"
    assert decision.fallback_used is True
    assert decision.response_format == {"type": "json_object"}


@pytest.mark.unit
def test_validate_structured_payload_raises_on_schema_mismatch():
    with pytest.raises(StructuredGenerationSchemaError):
        validate_structured_payload(
            payload={"answer": 123},
            schema={
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
            },
        )


@pytest.mark.unit
def test_parse_and_validate_structured_output_accepts_valid_payload():
    payload = parse_and_validate_structured_output(
        raw_text='{"answer":"ok"}',
        schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
    )

    assert payload == {"answer": "ok"}
