"""
Dictation error taxonomy and fallback policy helpers.

This module centralizes deterministic classification of dictation/STT failure
conditions so API responses and client fallback logic can stay consistent.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class DictationErrorClass(str, Enum):
    """Canonical dictation failure classes used by fallback strategy logic."""

    PERMISSION_DENIED = "permission_denied"
    UNSUPPORTED_API = "unsupported_api"
    AUTH_ERROR = "auth_error"
    QUOTA_ERROR = "quota_error"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MODEL_UNAVAILABLE = "model_unavailable"
    TRANSIENT_FAILURE = "transient_failure"
    EMPTY_TRANSCRIPT = "empty_transcript"
    UNKNOWN_ERROR = "unknown_error"


_AUTO_FALLBACK_ALLOWED_CLASSES: frozenset[DictationErrorClass] = frozenset(
    {
        DictationErrorClass.UNSUPPORTED_API,
        DictationErrorClass.PROVIDER_UNAVAILABLE,
        DictationErrorClass.MODEL_UNAVAILABLE,
        DictationErrorClass.TRANSIENT_FAILURE,
    }
)

_STATUS_HINT_TO_CLASS: dict[str, DictationErrorClass] = {
    "permission_denied": DictationErrorClass.PERMISSION_DENIED,
    "mic_permission_denied": DictationErrorClass.PERMISSION_DENIED,
    "unsupported_api": DictationErrorClass.UNSUPPORTED_API,
    "unsupported_browser": DictationErrorClass.UNSUPPORTED_API,
    "auth_error": DictationErrorClass.AUTH_ERROR,
    "unauthorized": DictationErrorClass.AUTH_ERROR,
    "forbidden": DictationErrorClass.AUTH_ERROR,
    "quota_error": DictationErrorClass.QUOTA_ERROR,
    "quota_exceeded": DictationErrorClass.QUOTA_ERROR,
    "rate_limited": DictationErrorClass.QUOTA_ERROR,
    "provider_unavailable": DictationErrorClass.PROVIDER_UNAVAILABLE,
    "model_unavailable": DictationErrorClass.MODEL_UNAVAILABLE,
    "model_downloading": DictationErrorClass.MODEL_UNAVAILABLE,
    "empty_transcript": DictationErrorClass.EMPTY_TRANSCRIPT,
    "transient_failure": DictationErrorClass.TRANSIENT_FAILURE,
    "network_error": DictationErrorClass.TRANSIENT_FAILURE,
    "timeout": DictationErrorClass.TRANSIENT_FAILURE,
}


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:
        return ""


def _normalize_status_hint(detail: Any) -> str:
    if isinstance(detail, dict):
        for key in ("status", "error_code", "error_type", "code"):
            candidate = detail.get(key)
            normalized = _to_text(candidate).strip().lower()
            if normalized:
                return normalized
    return _to_text(detail).strip().lower()


def _detail_message(detail: Any, exc: BaseException | None = None) -> str:
    parts: list[str] = []
    if isinstance(detail, dict):
        for key in ("message", "detail", "error", "details", "status"):
            value = detail.get(key)
            text = _to_text(value).strip()
            if text:
                parts.append(text)
    else:
        text = _to_text(detail).strip()
        if text:
            parts.append(text)
    if exc is not None:
        text = _to_text(exc).strip()
        if text:
            parts.append(text)
    return " ".join(parts).lower()


def _class_from_status_hint(status_hint: str) -> DictationErrorClass | None:
    if not status_hint:
        return None
    direct = _STATUS_HINT_TO_CLASS.get(status_hint)
    if direct is not None:
        return direct
    if "provider_unavailable" in status_hint:
        return DictationErrorClass.PROVIDER_UNAVAILABLE
    if "model_downloading" in status_hint or "model_unavailable" in status_hint:
        return DictationErrorClass.MODEL_UNAVAILABLE
    if "quota" in status_hint or "rate_limit" in status_hint:
        return DictationErrorClass.QUOTA_ERROR
    if "permission" in status_hint:
        return DictationErrorClass.PERMISSION_DENIED
    if "unsupported" in status_hint:
        return DictationErrorClass.UNSUPPORTED_API
    if "auth" in status_hint or "unauthorized" in status_hint or "forbidden" in status_hint:
        return DictationErrorClass.AUTH_ERROR
    if "empty" in status_hint and "transcript" in status_hint:
        return DictationErrorClass.EMPTY_TRANSCRIPT
    if "timeout" in status_hint or "network" in status_hint or "transient" in status_hint:
        return DictationErrorClass.TRANSIENT_FAILURE
    return None


def classify_dictation_error(
    *,
    status_code: int | None = None,
    detail: Any = None,
    exc: BaseException | None = None,
) -> DictationErrorClass:
    """
    Classify a dictation failure into a deterministic class.
    """
    status_hint = _normalize_status_hint(detail)
    by_hint = _class_from_status_hint(status_hint)
    if by_hint is not None:
        return by_hint

    if status_code in {401, 403}:
        return DictationErrorClass.AUTH_ERROR
    if status_code in {402, 429}:
        return DictationErrorClass.QUOTA_ERROR

    message = _detail_message(detail, exc=exc)

    if (
        "permission denied" in message
        or "microphone permission" in message
        or "notallowederror" in message
        or "securityerror" in message
    ):
        return DictationErrorClass.PERMISSION_DENIED
    if (
        "unsupported api" in message
        or "speechrecognition" in message
        or "not supported" in message
        or "endpoint not found" in message
    ):
        return DictationErrorClass.UNSUPPORTED_API
    if (
        "unauthorized" in message
        or "forbidden" in message
        or "invalid api key" in message
        or "authentication" in message
        or "auth" in message
    ):
        return DictationErrorClass.AUTH_ERROR
    if (
        "quota" in message
        or "rate limit" in message
        or "too many requests" in message
        or "payment required" in message
    ):
        return DictationErrorClass.QUOTA_ERROR
    if "provider unavailable" in message or "stt provider" in message:
        return DictationErrorClass.PROVIDER_UNAVAILABLE
    if (
        "model downloading" in message
        or "model unavailable" in message
        or "not available locally" in message
    ):
        return DictationErrorClass.MODEL_UNAVAILABLE
    if (
        "empty transcript" in message
        or "did not return any text" in message
        or "no transcript" in message
    ):
        return DictationErrorClass.EMPTY_TRANSCRIPT

    if status_code in {408, 500, 502, 503, 504}:
        return DictationErrorClass.TRANSIENT_FAILURE
    if (
        "timeout" in message
        or "timed out" in message
        or "network error" in message
        or "connection" in message
        or "try again" in message
        or "temporar" in message
        or "internal server error" in message
    ):
        return DictationErrorClass.TRANSIENT_FAILURE

    return DictationErrorClass.UNKNOWN_ERROR


def dictation_error_allows_auto_fallback(error_class: DictationErrorClass | str) -> bool:
    """
    Return True when automatic fallback (`auto` strategy) is allowed.
    """
    try:
        normalized = (
            error_class
            if isinstance(error_class, DictationErrorClass)
            else DictationErrorClass(str(error_class).strip().lower())
        )
    except ValueError:
        return False
    return normalized in _AUTO_FALLBACK_ALLOWED_CLASSES


def build_dictation_error_payload(
    *,
    status_code: int | None,
    status: str | None = None,
    message: str | None = None,
    detail: Any = None,
    exc: BaseException | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a structured dictation error payload with taxonomy metadata.
    """
    payload: dict[str, Any] = {}
    if status:
        payload["status"] = status
    if message:
        payload["message"] = message
    if detail is not None:
        payload["detail"] = detail
    if extra:
        payload.update(extra)

    classification = classify_dictation_error(status_code=status_code, detail=payload, exc=exc)
    payload["dictation_error_class"] = classification.value
    payload["dictation_fallback_allowed"] = dictation_error_allows_auto_fallback(classification)
    return payload


__all__ = [
    "DictationErrorClass",
    "build_dictation_error_payload",
    "classify_dictation_error",
    "dictation_error_allows_auto_fallback",
]
