from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from tldw_Server_API.app.core.LLM_Calls.structured_output import (
    StructuredOutputNoPayloadError,
    StructuredOutputOptions,
    StructuredOutputParseError,
    StructuredOutputSchemaError,
    extract_items,
    parse_structured_output,
)


class ClaimsOutputParseError(StructuredOutputParseError):
    """Base parse error for claims-oriented model outputs."""


class ClaimsOutputNoJsonError(StructuredOutputNoPayloadError, ClaimsOutputParseError):
    """No parseable JSON payload could be extracted."""


class ClaimsOutputSchemaError(StructuredOutputSchemaError, ClaimsOutputParseError):
    """Parsed JSON shape is not compatible with expected schema."""


@dataclass(frozen=True)
class ClaimsParserOptions:
    parse_mode: str = "lenient"
    strip_think_tags: bool = True
    wrapper_key: str | None = "claims"

    @property
    def strict(self) -> bool:
        return str(self.parse_mode or "lenient").strip().lower() == "strict"


def parse_claims_llm_output(
    text: str,
    *,
    parse_mode: str = "lenient",
    strip_think_tags: bool = True,
) -> Any:
    """Parse raw model text into JSON with strict/lenient handling."""
    try:
        return parse_structured_output(
            text,
            options=StructuredOutputOptions(
                parse_mode=parse_mode,
                strip_think_tags=strip_think_tags,
            ),
        )
    except StructuredOutputNoPayloadError as exc:
        raise ClaimsOutputNoJsonError(str(exc)) from exc
    except StructuredOutputParseError as exc:
        raise ClaimsOutputParseError(str(exc)) from exc


def coerce_llm_response_text(response: Any) -> str:
    """Best-effort normalization of provider response shapes to plain text."""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        with suppress(Exception):
            choices = response.get("choices") or []
            if isinstance(choices, list) and choices:
                msg = choices[0].get("message") if isinstance(choices[0], dict) else None
                content = msg.get("content") if isinstance(msg, dict) else None
                if isinstance(content, str):
                    return content
        with suppress(Exception):
            alt = response.get("response") or response.get("text")
            if isinstance(alt, str):
                return alt
    with suppress(Exception):
        return "".join(list(response))
    return str(response)


def extract_claim_items(
    payload: Any,
    *,
    wrapper_key: str | None = "claims",
    parse_mode: str = "lenient",
) -> list[dict[str, Any]]:
    """Normalize payload into claim objects with optional wrapper support."""
    strict = str(parse_mode or "lenient").strip().lower() == "strict"
    try:
        return extract_items(
            payload,
            wrapper_key=wrapper_key,
            strict=strict,
            allow_top_level_list=not strict,
            allow_string_items=not strict,
            fallback_wrapper_keys=("claims",) if wrapper_key and wrapper_key != "claims" else (),
        )
    except StructuredOutputSchemaError as exc:
        raise ClaimsOutputSchemaError(str(exc)) from exc


def extract_claim_texts(
    payload: Any,
    *,
    wrapper_key: str | None = "claims",
    parse_mode: str = "lenient",
    max_claims: int | None = None,
) -> list[str]:
    strict = str(parse_mode or "lenient").strip().lower() == "strict"
    items = extract_claim_items(payload, wrapper_key=wrapper_key, parse_mode=parse_mode)
    out: list[str] = []
    limit = max_claims if isinstance(max_claims, int) and max_claims > 0 else None
    for item in items:
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            out.append(text.strip())
        elif strict:
            raise ClaimsOutputSchemaError("Each claim object must include a non-empty 'text' field.")
        if limit is not None and len(out) >= limit:
            break
    return out


def resolve_claims_response_format(
    provider: str,
    *,
    schema_name: str,
    json_schema: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Choose response_format using capability validation with safe fallback."""
    try:
        from tldw_Server_API.app.core.LLM_Calls.capability_registry import get_allowed_fields

        if "response_format" not in get_allowed_fields(provider):
            return None
    except Exception:
        return None

    capabilities: dict[str, Any] = {}
    try:
        from tldw_Server_API.app.core.LLM_Calls.adapter_registry import get_registry
        from tldw_Server_API.app.core.LLM_Calls.adapter_utils import normalize_provider

        adapter = get_registry().get_adapter(normalize_provider(provider))
        if adapter is not None:
            caps = adapter.capabilities() or {}
            if isinstance(caps, dict):
                capabilities = caps
    except Exception:
        capabilities = {}

    supported_types: set[str] = set()
    for key in ("response_format_types", "supported_response_format_types"):
        value = capabilities.get(key)
        if isinstance(value, (list, tuple, set)):
            supported_types |= {str(v).strip().lower() for v in value if str(v).strip()}
    if capabilities.get("supports_json_object") is True:
        supported_types.add("json_object")
    if capabilities.get("supports_json_schema") is True:
        supported_types.add("json_schema")
    if not supported_types:
        supported_types = {"json_object"}

    if "json_schema" in supported_types and isinstance(json_schema, dict):
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "schema": json_schema,
            },
        }
    if "json_object" in supported_types:
        return {"type": "json_object"}
    return None


__all__ = [
    "ClaimsOutputParseError",
    "ClaimsOutputNoJsonError",
    "ClaimsOutputSchemaError",
    "ClaimsParserOptions",
    "coerce_llm_response_text",
    "extract_claim_items",
    "extract_claim_texts",
    "parse_claims_llm_output",
    "resolve_claims_response_format",
]
