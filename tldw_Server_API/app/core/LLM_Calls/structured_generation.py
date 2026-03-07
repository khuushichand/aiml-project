"""Shared structured-output negotiation and validation helpers.

This module centralizes provider response-format negotiation and schema
validation for structured generation flows used by chat and claims paths.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError as JsonSchemaSchemaError
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from tldw_Server_API.app.core.LLM_Calls.structured_output import (
    StructuredOutputOptions,
    StructuredOutputParseError,
    parse_structured_output,
)


class StructuredGenerationError(ValueError):
    """Base error for structured generation orchestration failures."""

    code: str = "structured_output_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        attempts: int | None = None,
        internal_detail: str | None = None,
    ) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.attempts = attempts
        self.internal_detail = internal_detail


class StructuredGenerationCapabilityError(StructuredGenerationError):
    """Raised when provider/request capabilities cannot satisfy structured mode."""

    code = "structured_output_capability_error"


class StructuredGenerationParseError(StructuredGenerationError):
    """Raised when model output cannot be parsed as structured JSON."""

    code = "structured_output_parse_error"


class StructuredGenerationSchemaError(StructuredGenerationError):
    """Raised when parsed JSON fails JSON-schema validation."""

    code = "structured_output_schema_error"


@dataclass(frozen=True)
class StructuredModeDecision:
    """Result of negotiating requested structured response mode for a provider."""

    mode_used: str
    fallback_used: bool
    response_format: dict[str, Any] | None


def _load_provider_capabilities(provider: str) -> dict[str, Any]:
    """Return adapter capabilities for `provider` when the registry is available."""

    try:
        from tldw_Server_API.app.core.LLM_Calls.adapter_registry import get_registry
        from tldw_Server_API.app.core.LLM_Calls.adapter_utils import normalize_provider

        adapter = get_registry().get_adapter(normalize_provider(provider))
        if adapter is None:
            return {}
        capabilities = adapter.capabilities() or {}
        if isinstance(capabilities, dict):
            return capabilities
    except ImportError:
        return {}
    return {}


def _extract_supported_response_format_types(provider_capabilities: Mapping[str, Any]) -> set[str]:
    """Collect normalized structured-output modes from provider capabilities."""

    supported_types: set[str] = set()
    for key in ("response_format_types", "supported_response_format_types"):
        raw_value = provider_capabilities.get(key)
        if isinstance(raw_value, (list, tuple, set)):
            supported_types |= {str(item).strip().lower() for item in raw_value if str(item).strip()}
    if provider_capabilities.get("supports_json_object") is True:
        supported_types.add("json_object")
    if provider_capabilities.get("supports_json_schema") is True:
        supported_types.add("json_schema")
    if not supported_types:
        supported_types = {"json_object"}
    return supported_types


def _normalize_requested_response_format(requested: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a structured `response_format` request payload."""

    requested_type = str(requested.get("type") or "").strip().lower()
    if requested_type not in {"json_schema", "json_object"}:
        raise StructuredGenerationCapabilityError(
            "Structured response_format.type must be 'json_schema' or 'json_object'."
        )

    normalized: dict[str, Any] = {"type": requested_type}
    if requested_type == "json_schema":
        json_schema = requested.get("json_schema")
        if not isinstance(json_schema, Mapping):
            raise StructuredGenerationCapabilityError(
                "response_format.json_schema must be an object when type is 'json_schema'."
            )
        schema_name = json_schema.get("name")
        schema_object = json_schema.get("schema")
        if not isinstance(schema_name, str) or not schema_name.strip():
            raise StructuredGenerationCapabilityError("response_format.json_schema.name must be a non-empty string.")
        if not isinstance(schema_object, Mapping):
            raise StructuredGenerationCapabilityError("response_format.json_schema.schema must be an object.")
        normalized["json_schema"] = dict(json_schema)
    return normalized


def negotiate_structured_response_mode(
    *,
    provider: str,
    requested: Mapping[str, Any],
    provider_capabilities: Mapping[str, Any] | None = None,
    allowed_fields: set[str] | None = None,
) -> StructuredModeDecision:
    """Negotiate the structured response mode to send to the provider."""

    normalized_request = _normalize_requested_response_format(requested)

    if allowed_fields is None:
        try:
            from tldw_Server_API.app.core.LLM_Calls.capability_registry import get_allowed_fields

            allowed_fields = get_allowed_fields(provider)
        except ImportError:
            allowed_fields = {"response_format"}
    if "response_format" not in set(allowed_fields):
        raise StructuredGenerationCapabilityError(
            f"Provider '{provider}' does not allow response_format in requests."
        )

    capabilities = dict(provider_capabilities or _load_provider_capabilities(provider))
    supported_types = _extract_supported_response_format_types(capabilities)
    requested_type = normalized_request["type"]

    if requested_type == "json_schema":
        if "json_schema" in supported_types:
            return StructuredModeDecision(
                mode_used="json_schema",
                fallback_used=False,
                response_format=normalized_request,
            )
        if "json_object" in supported_types:
            return StructuredModeDecision(
                mode_used="json_object",
                fallback_used=True,
                response_format={"type": "json_object"},
            )
        raise StructuredGenerationCapabilityError(
            f"Provider '{provider}' does not support json_schema or json_object response formats."
        )

    if "json_object" not in supported_types:
        raise StructuredGenerationCapabilityError(
            f"Provider '{provider}' does not support json_object response format."
        )
    return StructuredModeDecision(
        mode_used="json_object",
        fallback_used=False,
        response_format={"type": "json_object"},
    )


def resolve_structured_response_format(
    provider: str,
    *,
    schema_name: str,
    json_schema: Mapping[str, Any] | None = None,
    provider_capabilities: Mapping[str, Any] | None = None,
    allowed_fields: set[str] | None = None,
) -> dict[str, Any] | None:
    """Resolve provider response_format with safe fallback for structured mode."""

    if not isinstance(json_schema, Mapping):
        requested = {"type": "json_object"}
    else:
        requested = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "schema": dict(json_schema),
            },
        }

    try:
        decision = negotiate_structured_response_mode(
            provider=provider,
            requested=requested,
            provider_capabilities=provider_capabilities,
            allowed_fields=allowed_fields,
        )
    except StructuredGenerationCapabilityError:
        return None
    return decision.response_format


def validate_structured_payload(*, payload: Any, schema: Mapping[str, Any]) -> None:
    """Validate parsed JSON payload against JSON Schema."""

    try:
        Draft202012Validator(dict(schema)).validate(payload)
    except (JsonSchemaValidationError, JsonSchemaSchemaError) as exc:
        raise StructuredGenerationSchemaError(
            "Model output did not match the requested JSON schema.",
            internal_detail=str(exc),
        ) from exc


def parse_and_validate_structured_output(
    *,
    raw_text: Any,
    schema: Mapping[str, Any],
    parse_mode: str = "lenient",
    strip_think_tags: bool = True,
) -> Any:
    """Parse raw model output as JSON and validate against schema."""

    try:
        parsed = parse_structured_output(
            raw_text,
            options=StructuredOutputOptions(
                parse_mode=parse_mode,
                strip_think_tags=strip_think_tags,
            ),
        )
    except StructuredOutputParseError as exc:
        raise StructuredGenerationParseError(
            "Model output could not be parsed as JSON.",
            internal_detail=str(exc),
        ) from exc

    validate_structured_payload(payload=parsed, schema=schema)
    return parsed


def parse_and_validate_with_retries(
    *,
    candidate_outputs: Sequence[Any],
    schema: Mapping[str, Any],
    max_attempts: int = 2,
    parse_mode: str = "lenient",
    strip_think_tags: bool = True,
) -> tuple[Any, int]:
    """Bounded retry helper for parse+validate over candidate model outputs."""

    if max_attempts < 1:
        raise StructuredGenerationCapabilityError("max_attempts must be at least 1")

    attempts_limit = min(max_attempts, len(candidate_outputs))
    if attempts_limit < 1:
        raise StructuredGenerationParseError("No candidate outputs provided for validation.", attempts=0)

    last_error: StructuredGenerationError | None = None
    for idx in range(attempts_limit):
        try:
            parsed = parse_and_validate_structured_output(
                raw_text=candidate_outputs[idx],
                schema=schema,
                parse_mode=parse_mode,
                strip_think_tags=strip_think_tags,
            )
            return parsed, idx + 1
        except StructuredGenerationError as exc:
            last_error = exc

    message = str(last_error) if last_error is not None else "Structured output validation failed."
    if isinstance(last_error, StructuredGenerationSchemaError):
        raise StructuredGenerationSchemaError(message, attempts=attempts_limit) from last_error
    raise StructuredGenerationParseError(message, attempts=attempts_limit) from last_error


__all__ = [
    "StructuredGenerationError",
    "StructuredGenerationCapabilityError",
    "StructuredGenerationParseError",
    "StructuredGenerationSchemaError",
    "StructuredModeDecision",
    "negotiate_structured_response_mode",
    "resolve_structured_response_format",
    "validate_structured_payload",
    "parse_and_validate_structured_output",
    "parse_and_validate_with_retries",
]
