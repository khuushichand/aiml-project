from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Tuple, Mapping


def _summarize_message_content(content: Any) -> Tuple[int, bool]:
    """Return (text_char_count, has_attachments) for a message content payload."""
    text_chars = 0
    has_attachments = False

    if content is None:
        return text_chars, has_attachments

    if isinstance(content, str):
        return len(content), has_attachments

    if isinstance(content, dict):
        # Handle single-part dicts (e.g., Gemini parts or Cohere history entries)
        possible_text = content.get("text") or content.get("message")
        if isinstance(possible_text, str):
            text_chars += len(possible_text)
        if any(key in content for key in ("image_url", "inline_data", "data", "file_id")):
            has_attachments = True
        if "parts" in content:
            extra_chars, extra_attach = _summarize_message_content(content.get("parts"))
            text_chars += extra_chars
            has_attachments = has_attachments or extra_attach
        return text_chars, has_attachments

    if isinstance(content, (list, tuple)):
        for part in content:
            if isinstance(part, dict):
                part_type = (part.get("type") or "").lower()
                if part_type in {"text", "input_text"} and isinstance(part.get("text"), str):
                    text_chars += len(part.get("text") or "")
                elif part_type in {"image_url", "input_image", "image"}:
                    has_attachments = True
                elif part_type in {"tool_use"}:
                    continue
                if "inline_data" in part or "image_url" in part:
                    has_attachments = True
                if "functionCall" in part and isinstance(part.get("functionCall", {}).get("args"), str):
                    text_chars += len(part["functionCall"]["args"])
            elif isinstance(part, str):
                text_chars += len(part)
    return text_chars, has_attachments


def _summarize_messages(messages: Any, key: str) -> Dict[str, Any]:
    """Summarize a messages-like payload without logging raw content."""
    if messages is None:
        return {f"{key}_count": 0, f"{key}_text_chars": 0}

    if not isinstance(messages, list):
        messages_iterable = [messages]
    else:
        messages_iterable = messages

    role_counts: Dict[str, int] = {}
    total_text_chars = 0
    has_attachments = False

    for entry in messages_iterable:
        if isinstance(entry, dict):
            role = entry.get("role")
            if isinstance(role, str):
                role_counts[role] = role_counts.get(role, 0) + 1
            entry_content = None
            if "content" in entry:
                entry_content = entry.get("content")
            elif "parts" in entry:
                entry_content = entry.get("parts")
            elif "message" in entry:
                entry_content = entry.get("message")
            elif "text" in entry:
                entry_content = entry.get("text")
            text_chars, attachments = _summarize_message_content(entry_content)
            total_text_chars += text_chars
            has_attachments = has_attachments or attachments
        elif isinstance(entry, str):
            total_text_chars += len(entry)

    summary: Dict[str, Any] = {
        f"{key}_count": len(messages_iterable),
        f"{key}_text_chars": total_text_chars,
    }
    if role_counts:
        summary[f"{key}_roles"] = role_counts
    if has_attachments:
        summary[f"{key}_has_attachments"] = True
    return summary


def _summarize_dict_field(key: str, value: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize dict values without exposing raw content."""
    if key == "response_format":
        summary: Dict[str, Any] = {f"{key}_keys_count": len(value)}
        response_type = value.get("type")
        if isinstance(response_type, str):
            summary["response_format_type"] = response_type
        return summary

    if key == "generationConfig":
        summary = {f"{key}_keys_count": len(value)}
        for numeric_key in ("temperature", "topP", "topK", "maxOutputTokens", "candidateCount"):
            numeric_val = value.get(numeric_key)
            if isinstance(numeric_val, (int, float)):
                summary[f"{key}_{numeric_key}"] = numeric_val
        if isinstance(value.get("responseMimeType"), str):
            summary["response_mime_type"] = value["responseMimeType"]
        if isinstance(value.get("stopSequences"), (list, tuple)):
            summary[f"{key}_stop_sequences_count"] = len(value["stopSequences"])
        return summary

    if key == "logit_bias":
        return {f"{key}_size": len(value)}

    if key == "system_instruction":
        parts = value.get("parts")
        text_chars, attachments = _summarize_message_content(parts)
        summary = {
            f"{key}_parts_count": len(parts or []),
            f"{key}_text_chars": text_chars,
        }
        if attachments:
            summary[f"{key}_has_attachments"] = True
        return summary

    return {f"{key}_keys_count": len(value)}


def _summarize_list_field(key: str, value: Iterable[Any]) -> Dict[str, Any]:
    """Summarize list/tuple values."""
    items = list(value)
    summary: Dict[str, Any] = {f"{key}_count": len(items)}
    if key in {"stop", "stop_sequences", "stopSequences"}:
        summary[f"{key}_total_chars"] = sum(len(item) for item in items if isinstance(item, str))
    return summary


def _sanitize_payload_for_logging(
    payload: Optional[Dict[str, Any]],
    *,
    message_keys: Tuple[str, ...] = ("messages",),
    text_keys: Tuple[str, ...] = (),
) -> Dict[str, Any]:
    """Build a metadata dict safe for logging, omitting raw prompts or filenames."""
    if not isinstance(payload, dict):
        return {}

    metadata: Dict[str, Any] = {}

    model = payload.get("model")
    if isinstance(model, str):
        metadata["model"] = model

    if "stream" in payload:
        metadata["stream"] = bool(payload.get("stream"))

    for key in message_keys:
        if key in payload:
            metadata.update(_summarize_messages(payload.get(key), key))

    for key, value in payload.items():
        if key in message_keys or key in {"model", "stream"}:
            continue
        if value is None:
            continue
        if isinstance(value, (int, float, bool)):
            metadata[key] = value
        elif isinstance(value, str):
            if key in text_keys or key in {"stop"}:
                metadata[f"{key}_chars"] = len(value)
            elif key in {"tool_choice"}:
                metadata[key] = value
            else:
                metadata[f"{key}_present"] = True
        elif isinstance(value, dict):
            metadata.update(_summarize_dict_field(key, value))
        elif isinstance(value, (list, tuple, set)):
            metadata.update(_summarize_list_field(key, value))
        else:
            metadata[f"{key}_present"] = True

    return metadata


def merge_extra_body(payload: Dict[str, Any], request: Mapping[str, Any]) -> Dict[str, Any]:
    """Merge extra_body into payload without overriding existing payload keys."""
    extra = request.get("extra_body")
    if not isinstance(extra, Mapping) or not extra:
        return payload
    merged = dict(extra)
    merged.update(payload)
    return merged


def merge_extra_headers(headers: Dict[str, str], request: Mapping[str, Any]) -> Dict[str, str]:
    """Merge extra_headers into headers without overriding existing header keys."""
    extra = request.get("extra_headers")
    if not isinstance(extra, Mapping) or not extra:
        return headers
    merged = dict(headers or {})
    existing_lower = {str(k).lower() for k in merged.keys()}
    for key, value in extra.items():
        if not isinstance(key, str):
            continue
        if key.lower() in existing_lower:
            continue
        merged[key] = str(value) if value is not None else ""
    return merged


__all__ = ["_sanitize_payload_for_logging", "merge_extra_body", "merge_extra_headers"]
