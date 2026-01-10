from __future__ import annotations

import json
import re
from typing import Any, Optional

from loguru import logger

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


def _redact_sensitive_text(text: str) -> str:
    if not text:
        return text
    try:
        text = re.sub(r"(?i)(authorization\s*:\s*bearer)\s+[^\s,;]+", r"\1 [REDACTED]", text)
        text = re.sub(r"(?i)(bearer)\s+[^\s,;]+", r"\1 [REDACTED]", text)
        text = re.sub(r'(?i)("api[_ -]?key"\s*:\s*)"[^"]+"', r'\1"[REDACTED]"', text)
        text = re.sub(r"(?i)(api[_ -]?key\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED]", text)
    except Exception:
        return text
    return text


def log_http_400_body(provider: str, exc: Exception, parsed_body: Any = None, max_chars: int = 2000) -> None:
    try:
        status = get_http_status_from_exception(exc)
    except Exception:
        status = None
    if status != 400:
        return
    body_json = None
    body_text = None
    if parsed_body is not None:
        body_json = parsed_body
    else:
        resp = getattr(exc, "response", None)
        if resp is not None:
            try:
                body_json = resp.json()
            except Exception:
                body_json = None
    if body_json is not None:
        try:
            body_text = json.dumps(body_json, ensure_ascii=True)
        except Exception:
            body_text = str(body_json)
    else:
        try:
            body_text = get_http_error_text(exc)
        except Exception:
            body_text = None
    if not body_text:
        return
    body_text = _redact_sensitive_text(str(body_text))
    if max_chars is not None and len(body_text) > max_chars:
        body_text = body_text[:max_chars] + "...(truncated)"
    logger.warning(f"{provider or 'unknown'}: upstream 400 response body: {body_text}")


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
