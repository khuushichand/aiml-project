from __future__ import annotations

"""
Centralized HTTP client factory with safe defaults.

Features:
- trust_env=False (ignore system proxies by default)
- Sensible timeouts
- Optional SSRF/egress policy validation via Security.egress
"""

from typing import Optional, Dict, Any, TypedDict

try:
    import httpx
except Exception:  # pragma: no cover - optional dependency
    httpx = None  # type: ignore


DEFAULT_TIMEOUT_SEC = 10.0


def create_async_client(timeout: Optional[float] = None) -> "httpx.AsyncClient":
    if httpx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available")
    to = httpx.Timeout(timeout or DEFAULT_TIMEOUT_SEC)
    # trust_env=False avoids proxy capture unless explicitly desired
    return httpx.AsyncClient(timeout=to, trust_env=False)


def create_client(timeout: Optional[float] = None) -> "httpx.Client":
    if httpx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available")
    to = httpx.Timeout(timeout or DEFAULT_TIMEOUT_SEC)
    return httpx.Client(timeout=to, trust_env=False)


def _is_url_allowed(url: str) -> bool:
    try:
        from tldw_Server_API.app.core.Security.egress import evaluate_url_policy
        res = evaluate_url_policy(url)
        return bool(getattr(res, "allowed", False))
    except Exception:
        # Fail closed on policy evaluation errors
        return False


async def safe_post_json_async(client: "httpx.AsyncClient", url: str, payload: Dict[str, Any], *, timeout: Optional[float] = None):
    if not _is_url_allowed(url):
        raise ValueError("URL not allowed by egress policy")
    return await client.post(url, json=payload, timeout=timeout)


def safe_post_json(client: "httpx.Client", url: str, payload: Dict[str, Any], *, timeout: Optional[float] = None):
    if not _is_url_allowed(url):
        raise ValueError("URL not allowed by egress policy")
    return client.post(url, json=payload, timeout=timeout)


__all__ = [
    "create_async_client",
    "create_client",
    "safe_post_json_async",
    "safe_post_json",
]


# --- Optional curl backend support ----------------------------------------------------

class HttpResponse(TypedDict):
    status: int
    headers: Dict[str, str]
    text: str
    url: str
    backend: str  # 'curl' or 'httpx'


_SENSITIVE_HEADER_KEYS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
    "x-auth-token",
}


def _redact_headers(h: Optional[Dict[str, str]]) -> Dict[str, str]:
    safe: Dict[str, str] = {}
    if not h:
        return safe
    for k, v in h.items():
        if k.lower() in _SENSITIVE_HEADER_KEYS:
            safe[k] = "<redacted>"
        else:
            safe[k] = v
    return safe


def fetch(
    url: str,
    *,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None,
    backend: str = "auto",  # auto|curl|httpx
    impersonate: Optional[str] = None,  # chrome120|safari17|firefox120
    http2: bool = True,
    timeout: float = DEFAULT_TIMEOUT_SEC,
    allow_redirects: bool = True,
    proxies: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    """Lightweight HTTP fetch with optional curl_cffi backend.

    - Enforces centralized egress policy before any network call.
    - Redacts sensitive headers if logging in callers is desired.
    - Returns a normalized response mapping.
    """
    if not _is_url_allowed(url):
        raise ValueError("URL not allowed by egress policy")

    b = backend.lower().strip() if backend else "auto"
    b_eff = b

    # Prefer curl if requested/available, otherwise fall back to httpx
    if b in ("auto", "curl"):
        try:
            from curl_cffi import requests as cfr  # type: ignore

            resp = cfr.request(
                method.upper(),
                url,
                headers=headers,
                cookies=cookies,
                impersonate=impersonate,
                http2=http2,
                timeout=timeout,
                allow_redirects=allow_redirects,
                proxies=proxies,
            )
            return HttpResponse(
                status=resp.status_code,
                headers=dict(resp.headers or {}),
                text=resp.text,
                url=str(resp.url),
                backend="curl",
            )
        except Exception:
            # If curl requested explicitly, bubble up; if auto, fall back to httpx
            if b == "curl":
                raise
            b_eff = "httpx"

    # httpx fallback (sync)
    if httpx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available for fallback backend")

    # Sanitize Accept-Encoding for httpx: drop zstd (unsupported)
    hdrs = dict(headers) if headers else None
    if hdrs and "Accept-Encoding" in hdrs and "zstd" in hdrs["Accept-Encoding"].lower():
        # Keep gzip/deflate/br where possible
        hdrs["Accept-Encoding"] = "gzip, deflate, br"

    to = httpx.Timeout(timeout)
    with httpx.Client(timeout=to, trust_env=False, proxies=proxies) as client:
        r = client.request(
            method.upper(),
            url,
            headers=hdrs,
            cookies=cookies,
            follow_redirects=allow_redirects,
        )
        return HttpResponse(
            status=r.status_code,
            headers=dict(r.headers),
            text=r.text,
            url=str(r.url),
            backend="httpx",
        )


__all__.extend([
    "HttpResponse",
    "fetch",
])
