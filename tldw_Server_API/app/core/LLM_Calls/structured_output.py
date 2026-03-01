"""Parse and normalize structured JSON output returned by LLM calls.

The module accepts raw model payloads (for example plain text, fenced JSON, or
already-parsed dict/list objects), extracts candidate JSON, and returns
JSON-compatible Python values. In lenient mode it may strip ``<think>`` tags,
inspect fenced blocks, and probe balanced JSON fragments; strict mode limits
recovery and enforces tighter schema expectations.

Behavior is controlled by :class:`StructuredOutputOptions`, and parsing/schema
failures are reported through the centralized structured-output exceptions
imported from ``app.core.exceptions``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from tldw_Server_API.app.core.exceptions import (
    StructuredOutputNoPayloadError,
    StructuredOutputParseError,
    StructuredOutputSchemaError,
)

_THINK_TAG_RE = re.compile(r"<think>[\s\S]*?</think>\s*", re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


@dataclass(frozen=True)
class StructuredOutputOptions:
    """Configuration for structured-output parsing and item extraction.

    Attributes:
        parse_mode: Parsing mode. ``"lenient"`` (default) enables recovery
            heuristics; ``"strict"`` minimizes candidate rewriting/probing.
        strip_think_tags: Whether lenient candidate building strips
            ``<think>...</think>`` segments before JSON parsing attempts.
        wrapper_key: Preferred container key expected to hold extracted item
            lists when normalizing object payloads.
        allow_top_level_list: Whether a top-level list is accepted without
            requiring ``wrapper_key`` wrapping.
        max_fragments: Maximum number of balanced JSON fragments to probe from
            free-form text in lenient mode.

    Notes:
        ``strict`` behavior is derived from ``parse_mode`` via the ``strict``
        property.
    """

    parse_mode: str = "lenient"
    strip_think_tags: bool = True
    wrapper_key: str | None = None
    allow_top_level_list: bool = True
    max_fragments: int = 8

    @property
    def strict(self) -> bool:
        """Return whether strict parsing behavior should be applied.

        Returns:
            bool: ``True`` when ``parse_mode`` resolves to ``"strict"``,
            otherwise ``False`` for lenient behavior.
        """
        return str(self.parse_mode or "lenient").strip().lower() == "strict"


def _strip_think_tags(text: str) -> str:
    """Remove `<think>...</think>` spans and surrounding whitespace."""
    return _THINK_TAG_RE.sub("", text).strip()


def _extract_balanced_json_fragments(
    text: str,
    *,
    max_fragments: int,
) -> list[str]:
    """Extract up to `max_fragments` balanced JSON object/array slices from text.

    This is a tolerant scanner used in lenient mode. It tracks braces/brackets and
    JSON string boundaries so braces inside string literals do not terminate a
    fragment early.
    """

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
    """Build ordered, de-duplicated JSON candidates from model output text.

    Candidate order is intentional:
    1. JSON fenced blocks.
    2. Raw full text.
    3. In lenient mode only: balanced JSON fragments from raw text.

    For each candidate, lenient mode may also try a think-tag-stripped version.
    """

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
    """Parse a model payload into a JSON-compatible Python value.

    Args:
        payload: Raw model output (text, dict, list, or None).
        options: Optional parser configuration. Defaults to lenient mode.

    Returns:
        Parsed JSON as native Python structures.

    Raises:
        StructuredOutputNoPayloadError: No parseable JSON candidate was found.
    """

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
    """Normalize parsed output into a list of item objects.

    Behavior differs by mode:
    - Strict mode enforces exact wrapper/list expectations and rejects fallback keys.
    - Lenient mode may fall back to alternate wrapper keys, wrap a top-level object
      as a single-item list, and optionally coerce string items to `{"text": ...}`.

    Args:
        payload: Parsed JSON value (usually from `parse_structured_output`).
        wrapper_key: Preferred key that should contain the list of items.
        strict: If `True`, enforce strict structure checks.
        allow_top_level_list: Whether list payloads are accepted without a wrapper.
        allow_string_items: Whether lenient mode should coerce string list items.
        fallback_wrapper_keys: Alternate keys to probe in lenient mode.
    """

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
    "StructuredOutputNoPayloadError",
    "StructuredOutputOptions",
    "StructuredOutputParseError",
    "StructuredOutputSchemaError",
    "extract_items",
    "parse_structured_output",
]
