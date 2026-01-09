from __future__ import annotations

import re
from typing import Any, Optional

from tldw_Server_API.app.core.exceptions import NetworkError, RetryExhaustedError


def get_http_status_from_exception(exc: Exception) -> Optional[int]:
    """Best-effort extraction of an HTTP status code from common exception shapes."""
    response = getattr(exc, "response", None)
    if response is not None:
        for attr in ("status_code", "status"):
            status = getattr(response, attr, None)
            if status is not None:
                try:
                    return int(status)
                except (TypeError, ValueError):
                    pass
    for attr in ("status_code", "status"):
        status = getattr(exc, attr, None)
        if status is not None:
            try:
                return int(status)
            except (TypeError, ValueError):
                pass
    if isinstance(exc, NetworkError):
        match = re.search(r"HTTP\\s+(\\d{3})", str(exc))
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
    return None


def get_http_error_text(exc: Exception) -> str:
    """Return an error detail string from common response/exception shapes."""
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            text = getattr(response, "text", None)
        except Exception as response_exc:
            text = None
            if getattr(response_exc.__class__, "__name__", "") == "ResponseNotRead":
                try:
                    response.read()
                    text = getattr(response, "text", None)
                except Exception:
                    text = None
        if text is None:
            try:
                text = getattr(response, "content", None)
            except Exception as response_exc:
                text = None
                if getattr(response_exc.__class__, "__name__", "") == "ResponseNotRead":
                    try:
                        response.read()
                        text = getattr(response, "content", None)
                    except Exception:
                        text = None
            if isinstance(text, (bytes, bytearray)):
                try:
                    text = text.decode("utf-8", errors="replace")
                except Exception:
                    text = None
        if text is not None:
            return str(text)
    response_text = getattr(exc, "response_text", None)
    if response_text:
        return str(response_text)
    return str(exc)


def is_network_error(exc: Exception) -> bool:
    if isinstance(exc, (NetworkError, RetryExhaustedError)):
        return True
    module = getattr(exc.__class__, "__module__", "")
    name = exc.__class__.__name__
    if module.startswith("requests"):
        return "RequestException" in name or "ConnectionError" in name or "Timeout" in name
    if module.startswith("httpx"):
        return "RequestError" in name or "Connect" in name or "Timeout" in name
    return False


def is_http_status_error(exc: Exception) -> bool:
    module = getattr(exc.__class__, "__module__", "")
    name = exc.__class__.__name__
    if module.startswith("httpx"):
        return name == "HTTPStatusError"
    if module.startswith("requests"):
        return name == "HTTPError"
    return False


def is_chunked_encoding_error(exc: Exception) -> bool:
    module = getattr(exc.__class__, "__module__", "")
    name = exc.__class__.__name__
    return module.startswith("requests") and name == "ChunkedEncodingError"
