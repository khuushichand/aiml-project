from typing import Any, Optional

from tldw_Server_API.app.core.testing import env_flag_enabled


def _debug_error_details_enabled() -> bool:
    """Return True when DEBUG_ERROR_DETAILS enables verbose error payloads."""
    return env_flag_enabled("DEBUG_ERROR_DETAILS")


def _maybe_debug_details(exc: Optional[Exception]) -> Optional[str]:
    """Return exception details when DEBUG_ERROR_DETAILS is enabled, else None."""
    if exc is None or not _debug_error_details_enabled():
        return None
    try:
        return str(exc)
    except Exception:
        return "Unprintable error"


def _http_error_detail(message: str, request_id: Optional[str], exc: Optional[Exception] = None) -> dict[str, Any]:
    """Build an HTTP error payload with optional request_id and debug details."""
    payload: dict[str, Any] = {"message": message}
    if request_id:
        payload["request_id"] = request_id
    details = _maybe_debug_details(exc)
    if details:
        payload["details"] = details
    return payload


def _ws_error_payload(
    message: str,
    *,
    request_id: Optional[str] = None,
    exc: Optional[Exception] = None,
    error_type: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a WebSocket error payload with optional debug details and extra fields."""
    payload: dict[str, Any] = {"type": "error", "message": message}
    if error_type:
        payload["error_type"] = error_type
    if request_id:
        payload["request_id"] = request_id
    details = _maybe_debug_details(exc)
    if details:
        payload["details"] = details
    if extra:
        reserved = {"type", "message", "error_type", "request_id", "details"}
        payload.update({key: value for key, value in extra.items() if key not in reserved})
    return payload
