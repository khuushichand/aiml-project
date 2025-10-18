from __future__ import annotations

"""
Centralized HTTP client factory with safe defaults.

Features:
- trust_env=False (ignore system proxies by default)
- Sensible timeouts
- Optional SSRF/egress policy validation via Security.egress
"""

from typing import Optional, Dict, Any

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

