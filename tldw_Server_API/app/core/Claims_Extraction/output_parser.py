from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


_THINK_TAG_RE = re.compile(r"<think>[\s\S]*?</think>\s*", re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


class ClaimsOutputParseError(ValueError):
    """Base parse error for claims-oriented model outputs."""


class ClaimsOutputNoJsonError(ClaimsOutputParseError):
    """No parseable JSON payload could be extracted."""


class ClaimsOutputSchemaError(ClaimsOutputParseError):
    """Parsed JSON shape is not compatible with expected schema."""


@dataclass(frozen=True)
class ClaimsParserOptions:
    parse_mode: str = "lenient"
    strip_think_tags: bool = True
    wrapper_key: str | None = "claims"

    @property
    def strict(self) -> bool:
        return str(self.parse_mode or "lenient").strip().lower() == "strict"


def _strip_think_tags(text: str) -> str:
    return _THINK_TAG_RE.sub("", text).strip()


def _extract_balanced_json_fragments(text: str, *, max_fragments: int = 6) -> list[str]:
    fragments: list[str] = []
    if not text:
        return fragments

    pairs = {"{": "}", "[": "]"}
    starts = [idx for idx, ch in enumerate(text) if ch in pairs]
    for start in starts:
        stack: list[str] = []
        in_string = False
        escaped = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch in pairs:
                stack.append(pairs[ch])
                continue
            if ch in {"}", "]"}:
                if not stack or stack[-1] != ch:
                    break
                stack.pop()
                if not stack:
                    fragment = text[start : idx + 1].strip()
                    if fragment:
                        fragments.append(fragment)
                    break
        if len(fragments) >= max_fragments:
            break
    return fragments


def _build_parse_candidates(text: str, *, options: ClaimsParserOptions) -> list[str]:
    body = text if isinstance(text, str) else str(text)
    raw = body.strip()
    if not raw:
        return []

    candidates: list[str] = []
    seen: set[str] = set()

    def _push(value: str | None) -> None:
        if not value:
            return
        candidate = value.strip()
        if not candidate or candidate in seen:
            return
        seen.add(candidate)
        candidates.append(candidate)

    fences = _FENCE_RE.findall(raw) or []
    for block in fences:
        _push(block)
        if options.strip_think_tags:
            _push(_strip_think_tags(block))

    _push(raw)
    if options.strip_think_tags:
        _push(_strip_think_tags(raw))

    if not options.strict:
        for fragment in _extract_balanced_json_fragments(raw):
            _push(fragment)
            if options.strip_think_tags:
                _push(_strip_think_tags(fragment))

    return candidates


def parse_claims_llm_output(
    text: str,
    *,
    parse_mode: str = "lenient",
    strip_think_tags: bool = True,
) -> Any:
    """Parse raw model text into JSON with strict/lenient handling."""
    options = ClaimsParserOptions(parse_mode=parse_mode, strip_think_tags=strip_think_tags)
    candidates = _build_parse_candidates(text, options=options)
    if not candidates:
        raise ClaimsOutputNoJsonError("Model output was empty or whitespace-only.")

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            last_error = exc
            continue
    raise ClaimsOutputNoJsonError(f"Unable to parse JSON from model output: {last_error}")


def extract_claim_items(
    payload: Any,
    *,
    wrapper_key: str | None = "claims",
    parse_mode: str = "lenient",
) -> list[dict[str, Any]]:
    """Normalize payload into claim objects with optional wrapper support."""
    strict = str(parse_mode or "lenient").strip().lower() == "strict"
    items: Any = payload

    if isinstance(payload, Mapping):
        if wrapper_key and wrapper_key in payload:
            items = payload.get(wrapper_key)
        elif not strict and wrapper_key and wrapper_key != "claims" and "claims" in payload:
            items = payload.get("claims")
        elif strict and wrapper_key:
            raise ClaimsOutputSchemaError(f"Expected wrapper key '{wrapper_key}' in strict mode.")
        else:
            items = [payload]

    if not isinstance(items, list):
        raise ClaimsOutputSchemaError("Expected a list of claims.")

    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, Mapping):
            normalized.append(dict(item))
            continue
        if isinstance(item, str) and not strict:
            normalized.append({"text": item})
            continue
        raise ClaimsOutputSchemaError("Each claim must be an object (or string in lenient mode).")
    return normalized


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
    "extract_claim_items",
    "extract_claim_texts",
    "parse_claims_llm_output",
    "resolve_claims_response_format",
]
