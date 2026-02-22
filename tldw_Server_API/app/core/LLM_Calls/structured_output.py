from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_THINK_TAG_RE = re.compile(r"<think>[\s\S]*?</think>\s*", re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


class StructuredOutputParseError(ValueError):
    """Base parse error for structured model output."""


class StructuredOutputNoPayloadError(StructuredOutputParseError):
    """Raised when no JSON payload can be extracted from model output."""


class StructuredOutputSchemaError(StructuredOutputParseError):
    """Raised when parsed JSON shape does not match expected structure."""


@dataclass(frozen=True)
class StructuredOutputOptions:
    parse_mode: str = "lenient"
    strip_think_tags: bool = True
    wrapper_key: str | None = None
    allow_top_level_list: bool = True
    max_fragments: int = 8

    @property
    def strict(self) -> bool:
        return str(self.parse_mode or "lenient").strip().lower() == "strict"


def _strip_think_tags(text: str) -> str:
    return _THINK_TAG_RE.sub("", text).strip()


def _extract_balanced_json_fragments(
    text: str,
    *,
    max_fragments: int,
) -> list[str]:
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


def _build_parse_candidates(text: str, *, options: StructuredOutputOptions) -> list[str]:
    raw = text.strip()
    if not raw:
        return []

    candidates: list[str] = []
    seen: set[str] = set()

    def _push(candidate: str | None) -> None:
        if not candidate:
            return
        value = candidate.strip()
        if not value or value in seen:
            return
        seen.add(value)
        candidates.append(value)

    for block in _FENCE_RE.findall(raw) or []:
        _push(block)
        if options.strip_think_tags and not options.strict:
            _push(_strip_think_tags(block))

    _push(raw)
    if options.strip_think_tags and not options.strict:
        _push(_strip_think_tags(raw))

    if not options.strict:
        for fragment in _extract_balanced_json_fragments(
            raw,
            max_fragments=max(1, int(options.max_fragments)),
        ):
            _push(fragment)
            if options.strip_think_tags:
                _push(_strip_think_tags(fragment))

    return candidates


def parse_structured_output(
    payload: Any,
    *,
    options: StructuredOutputOptions | None = None,
) -> Any:
    resolved = options or StructuredOutputOptions()
    if isinstance(payload, (dict, list)):
        return payload
    if payload is None:
        raise StructuredOutputNoPayloadError("Model output was empty.")

    text = str(payload).strip()
    if not text:
        raise StructuredOutputNoPayloadError("Model output was empty or whitespace-only.")

    candidates = _build_parse_candidates(text, options=resolved)
    if not candidates:
        raise StructuredOutputNoPayloadError("No candidate JSON payload found.")

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            last_error = exc

    raise StructuredOutputNoPayloadError(f"Unable to parse JSON payload: {last_error}")


def extract_items(
    payload: Any,
    *,
    wrapper_key: str | None = None,
    strict: bool = False,
    allow_top_level_list: bool = True,
    allow_string_items: bool = False,
    fallback_wrapper_keys: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    items: Any = payload
    selected_wrapper = wrapper_key

    if isinstance(payload, Mapping):
        if wrapper_key and wrapper_key in payload:
            items = payload.get(wrapper_key)
        else:
            matched_fallback = None
            if not strict:
                for alt_key in fallback_wrapper_keys:
                    if alt_key and alt_key in payload:
                        matched_fallback = alt_key
                        break
            if matched_fallback is not None:
                items = payload.get(matched_fallback)
                selected_wrapper = matched_fallback
            elif strict and wrapper_key:
                raise StructuredOutputSchemaError(
                    f"Expected wrapper key '{wrapper_key}' in strict mode."
                )
            else:
                items = [payload]
    elif isinstance(payload, list):
        if strict and wrapper_key and not allow_top_level_list:
            raise StructuredOutputSchemaError(
                f"Expected wrapper key '{wrapper_key}' in strict mode."
            )
        if not allow_top_level_list and wrapper_key:
            raise StructuredOutputSchemaError(
                f"Content must be wrapped under '{wrapper_key}'."
            )
        items = payload
    else:
        if selected_wrapper:
            raise StructuredOutputSchemaError(
                f"Content must be a list or wrapped object under '{selected_wrapper}'."
            )
        raise StructuredOutputSchemaError("Content must be a list or object.")

    if not isinstance(items, list):
        target = selected_wrapper or wrapper_key
        if target:
            raise StructuredOutputSchemaError(f"Wrapper '{target}' must contain a list.")
        raise StructuredOutputSchemaError("Expected a list.")

    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, Mapping):
            normalized.append(dict(item))
            continue
        if allow_string_items and isinstance(item, str) and not strict:
            normalized.append({"text": item})
            continue
        raise StructuredOutputSchemaError(
            "Each item must be an object."
            if strict
            else "Each item must be an object (or string in lenient mode)."
        )
    return normalized


__all__ = [
    "StructuredOutputOptions",
    "StructuredOutputParseError",
    "StructuredOutputNoPayloadError",
    "StructuredOutputSchemaError",
    "extract_items",
    "parse_structured_output",
]
