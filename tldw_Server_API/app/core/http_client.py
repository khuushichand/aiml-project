from __future__ import annotations

"""
Centralized HTTP client factories and helpers with safe defaults.

Implements:
- Client factories (sync/async) with HTTP/2 by default and trust_env=False
- Egress policy enforcement for original URL, redirects, and proxies
- Retry policy with decorrelated jitter and Retry-After handling
- JSON helpers with content-type validation and max_bytes guard
- Streaming helpers: bytes and SSE, with no auto-retry after first byte
- Download helpers with atomic rename and optional checksum/length validation
- Structured logging and metrics hooks; optional trace header injection
"""

import asyncio
import os
import time
import random
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, TypedDict, Iterator, AsyncIterator, Tuple, Callable, Union
from urllib.parse import urlparse

from loguru import logger

try:
    import httpx
except Exception:  # pragma: no cover - optional dependency
    httpx = None  # type: ignore

try:  # Optional OpenTelemetry traceparent injection
    from opentelemetry import trace as _otel_trace  # type: ignore
    _OTEL_AVAILABLE = True
except Exception:  # pragma: no cover
    _OTEL_AVAILABLE = False
    _otel_trace = None  # type: ignore

from tldw_Server_API.app.core.exceptions import (
    EgressPolicyError,
    NetworkError,
    RetryExhaustedError,
    JSONDecodeError,
    StreamingProtocolError,
    DownloadError,
)

from tldw_Server_API.app.core.Metrics import (
    get_metrics_registry,
    MetricDefinition,
    MetricType,
)


# --------------------------------------------------------------------------------------
# Defaults & env config
# --------------------------------------------------------------------------------------

DEFAULT_CONNECT_TIMEOUT = float(os.getenv("HTTP_CONNECT_TIMEOUT", "5"))
DEFAULT_READ_TIMEOUT = float(os.getenv("HTTP_READ_TIMEOUT", "30"))
DEFAULT_WRITE_TIMEOUT = float(os.getenv("HTTP_WRITE_TIMEOUT", "30"))
DEFAULT_POOL_TIMEOUT = float(os.getenv("HTTP_POOL_TIMEOUT", "30"))
DEFAULT_ATTEMPTS = int(os.getenv("HTTP_RETRY_ATTEMPTS", "3"))
DEFAULT_BACKOFF_BASE_MS = int(os.getenv("HTTP_BACKOFF_BASE_MS", "250"))
DEFAULT_BACKOFF_CAP_S = int(os.getenv("HTTP_BACKOFF_CAP_S", "30"))
DEFAULT_MAX_REDIRECTS = int(os.getenv("HTTP_MAX_REDIRECTS", "5"))
DEFAULT_TRUST_ENV = (os.getenv("HTTP_TRUST_ENV", "false").lower() in {"1", "true", "yes", "on"})
DEFAULT_USER_AGENT = os.getenv("HTTP_DEFAULT_USER_AGENT", "tldw_server httpx")
PROXY_ALLOWLIST = {h.strip().lower() for h in (os.getenv("PROXY_ALLOWLIST", "").split(",")) if h.strip()}


def _httpx_timeout_from_defaults() -> "httpx.Timeout":
    return httpx.Timeout(
        connect=DEFAULT_CONNECT_TIMEOUT,
        read=DEFAULT_READ_TIMEOUT,
        write=DEFAULT_WRITE_TIMEOUT,
        pool=DEFAULT_POOL_TIMEOUT,
    )


def _register_http_client_metrics_once() -> None:
    reg = get_metrics_registry()
    # Register http-client-specific metrics if not present
    try:
        reg.register_metric(
            MetricDefinition(
                name="http_client_requests_total",
                type=MetricType.COUNTER,
                description="Total number of outbound HTTP client requests",
                labels=["method", "host", "status"],
            )
        )
    except Exception:
        pass
    try:
        reg.register_metric(
            MetricDefinition(
                name="http_client_request_duration_seconds",
                type=MetricType.HISTOGRAM,
                description="Outbound HTTP client request duration (seconds)",
                unit="s",
                labels=["method", "host"],
                buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30],
            )
        )
    except Exception:
        pass
    try:
        reg.register_metric(
            MetricDefinition(
                name="http_client_retries_total",
                type=MetricType.COUNTER,
                description="Total retries attempted by HTTP client",
                labels=["reason"],
            )
        )
    except Exception:
        pass
    try:
        reg.register_metric(
            MetricDefinition(
                name="http_client_egress_denials_total",
                type=MetricType.COUNTER,
                description="Total egress policy denials for outbound requests",
                labels=["reason"],
            )
        )
    except Exception:
        pass


_register_http_client_metrics_once()


# --------------------------------------------------------------------------------------
# Types
# --------------------------------------------------------------------------------------

class HttpResponse(TypedDict):
    status: int
    headers: Dict[str, str]
    text: str
    url: str
    backend: str  # 'curl' or 'httpx'


@dataclass
class RetryPolicy:
    attempts: int = DEFAULT_ATTEMPTS
    backoff_base_ms: int = DEFAULT_BACKOFF_BASE_MS
    backoff_cap_s: int = DEFAULT_BACKOFF_CAP_S
    retry_on_status: Tuple[int, ...] = (408, 429, 500, 502, 503, 504)
    retry_on_methods: Tuple[str, ...] = ("GET", "HEAD", "OPTIONS")
    respect_retry_after: bool = True
    retry_on_unsafe: bool = False


@dataclass
class SSEEvent:
    event: str = "message"
    data: str = ""
    id: Optional[str] = None
    retry: Optional[int] = None


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

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


def _parse_host_from_url(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _inject_trace_headers(headers: Optional[Dict[str, str]]) -> Dict[str, str]:
    out = dict(headers or {})
    if _OTEL_AVAILABLE:
        try:  # best-effort injection
            span = _otel_trace.get_current_span()
            if span is not None:
                ctx = span.get_span_context()
                if ctx and getattr(ctx, "trace_id", 0):
                    trace_id = format(ctx.trace_id, "032x")
                    span_id = format(ctx.span_id, "016x")
                    out.setdefault("traceparent", f"00-{trace_id}-{span_id}-01")
        except Exception:
            pass
    return out


def _validate_egress_or_raise(url: str) -> None:
    from tldw_Server_API.app.core.Security.egress import evaluate_url_policy

    res = evaluate_url_policy(url)
    if not getattr(res, "allowed", False):
        # metrics
        try:
            get_metrics_registry().increment(
                "http_client_egress_denials_total", 1, labels={"reason": (res.reason or "denied")}
            )
        except Exception:
            pass
        raise EgressPolicyError(res.reason or "URL not allowed by egress policy")


def _validate_proxies_or_raise(proxies: Optional[Union[str, Dict[str, str]]]) -> None:
    if not proxies:
        return
    hosts: set[str] = set()
    if isinstance(proxies, str):
        hosts.add(_parse_host_from_url(proxies))
    elif isinstance(proxies, dict):
        for v in proxies.values():
            hosts.add(_parse_host_from_url(v))
    # Deny by default: if allowlist is empty, proxies are disabled
    if not PROXY_ALLOWLIST:
        raise EgressPolicyError("Proxies not allowed (no allowlist configured)")
    for h in hosts:
        if not h:
            continue
        if h not in PROXY_ALLOWLIST:
            raise EgressPolicyError(f"Proxy host not in allowlist: {h}")


def _decorrelated_jitter_sleep(prev: float, base_ms: int, cap_s: int) -> float:
    base = max(0.001, base_ms / 1000.0)
    cap = max(base, float(cap_s))
    if prev <= 0:
        sleep = base
    else:
        sleep = min(cap, random.uniform(base, prev * 3))
    return sleep


def _should_retry(method: str, status: Optional[int], exc: Optional[Exception], policy: RetryPolicy) -> Tuple[bool, str]:
    m = method.upper()
    if exc is not None:
        # Network-level exceptions always retriable
        return True, exc.__class__.__name__
    if status is None:
        return False, "no_status"
    if status in policy.retry_on_status:
        if m in policy.retry_on_methods or policy.retry_on_unsafe:
            return True, f"{status}"
    return False, "status_not_retriable"


def _build_default_headers(component: Optional[str] = None) -> Dict[str, str]:
    ua = DEFAULT_USER_AGENT
    if component:
        ua = f"tldw_server/{component} httpx"
    return {"User-Agent": ua}


def _httpx_limits_default() -> "httpx.Limits":
    return httpx.Limits(max_connections=int(os.getenv("HTTP_MAX_CONNECTIONS", "100")),
                        max_keepalive_connections=int(os.getenv("HTTP_MAX_KEEPALIVE_CONNECTIONS", "20")))


# --------------------------------------------------------------------------------------
# Client factories
# --------------------------------------------------------------------------------------

def _instantiate_client(factory, kwargs: Dict[str, Any]):  # type: ignore[no-untyped-def]
    """Instantiate httpx client tolerating version differences in kwargs.

    Removes unsupported keyword arguments on TypeError and retries.
    """
    unsupported = {"proxies", "http2", "limits"}
    while True:
        try:
            return factory(**kwargs)
        except TypeError as e:
            msg = str(e)
            removed = False
            for k in list(unsupported):
                if f"unexpected keyword argument '{k}'" in msg or f"unexpected keyword argument \"{k}\"" in msg:
                    kwargs.pop(k, None)
                    unsupported.remove(k)
                    removed = True
                    break
            if not removed:
                raise
        except ImportError as e:
            # Gracefully disable http2 if h2 not installed
            if "Using http2=True" in str(e) and kwargs.get("http2"):
                kwargs["http2"] = False
                continue
            raise


def create_async_client(
    *,
    timeout: Optional[Union[float, "httpx.Timeout"]] = None,
    limits: Optional["httpx.Limits"] = None,
    base_url: Optional[str] = None,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    trust_env: bool = DEFAULT_TRUST_ENV,
    http2: bool = True,
    http3: bool = False,  # placeholder for future
    headers: Optional[Dict[str, str]] = None,
    transport: Optional["httpx.BaseTransport"] = None,
) -> "httpx.AsyncClient":
    if httpx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available")
    _validate_proxies_or_raise(proxies)
    to = timeout if isinstance(timeout, httpx.Timeout) else (timeout or _httpx_timeout_from_defaults())
    if not isinstance(to, httpx.Timeout):
        to = httpx.Timeout(float(to))
    hdrs = _build_default_headers()
    if headers:
        hdrs.update(headers)
    kwargs: Dict[str, Any] = dict(
        timeout=to,
        trust_env=trust_env,
        http2=http2,
        proxies=proxies,
        headers=hdrs,
        transport=transport,
        limits=limits or _httpx_limits_default(),
    )
    if base_url is not None:
        kwargs["base_url"] = base_url
    return _instantiate_client(httpx.AsyncClient, kwargs)


def create_client(
    *,
    timeout: Optional[Union[float, "httpx.Timeout"]] = None,
    limits: Optional["httpx.Limits"] = None,
    base_url: Optional[str] = None,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    trust_env: bool = DEFAULT_TRUST_ENV,
    http2: bool = True,
    http3: bool = False,  # placeholder for future
    headers: Optional[Dict[str, str]] = None,
    transport: Optional["httpx.BaseTransport"] = None,
) -> "httpx.Client":
    if httpx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available")
    _validate_proxies_or_raise(proxies)
    to = timeout if isinstance(timeout, httpx.Timeout) else (timeout or _httpx_timeout_from_defaults())
    if not isinstance(to, httpx.Timeout):
        to = httpx.Timeout(float(to))
    hdrs = _build_default_headers()
    if headers:
        hdrs.update(headers)
    kwargs: Dict[str, Any] = dict(
        timeout=to,
        trust_env=trust_env,
        http2=http2,
        proxies=proxies,
        headers=hdrs,
        transport=transport,
        limits=limits or _httpx_limits_default(),
    )
    if base_url is not None:
        kwargs["base_url"] = base_url
    return _instantiate_client(httpx.Client, kwargs)


# --------------------------------------------------------------------------------------
# Core request helpers (sync/async) with retries + redirects + egress checks
# --------------------------------------------------------------------------------------

async def afetch(
    *,
    method: str,
    url: str,
    client: Optional["httpx.AsyncClient"] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    files: Optional[Any] = None,
    timeout: Optional[Union[float, "httpx.Timeout"]] = None,
    allow_redirects: bool = True,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    retry: Optional[RetryPolicy] = None,
) -> "httpx.Response":
    if httpx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available")
    retry = retry or RetryPolicy()
    _validate_egress_or_raise(url)
    _validate_proxies_or_raise(proxies)

    attempts = max(1, retry.attempts)
    sleep_s = 0.0
    t0 = time.time()
    last_exc: Optional[Exception] = None

    async def _do_once(ac: "httpx.AsyncClient", target_url: str) -> Tuple["httpx.Response", str]:
        req_headers = _inject_trace_headers(headers)
        # Always disable internal redirects to enforce policy per hop
        try:
            r = await ac.request(
                method.upper(),
                target_url,
                headers=req_headers,
                params=params,
                json=json,
                data=data,
                files=files,
                timeout=timeout,
                follow_redirects=False,
            )
            return r, "ok"
        except Exception as e:  # transport error
            return None, e.__class__.__name__  # type: ignore[return-value]

    # Create ephemeral client if none provided
    need_close = False
    ac = client
    if ac is None:
        ac = create_async_client(proxies=proxies)
        need_close = True

    try:
        for attempt in range(1, attempts + 1):
            last_exc = None
            cur_url = url
            redirects = 0
            # Manual redirect handling
            while True:
                _validate_egress_or_raise(cur_url)
                resp, reason = await _do_once(ac, cur_url)
                if resp is None:
                    # network exception occurred
                    last_exc = NetworkError(reason)
                else:
                    # Check for redirect
                    if allow_redirects and resp.status_code in (301, 302, 303, 307, 308):
                        location = resp.headers.get("location")
                        try:
                            await resp.aclose()
                        except Exception:
                            pass
                        if not location:
                            # malformed redirect, treat as error
                            last_exc = NetworkError("Redirect without Location header")
                        else:
                            # Resolve relative redirects
                            try:
                                next_url = resp.request.url.join(httpx.URL(location)).human_repr()
                            except Exception:
                                # Fallback: absolute location or as-is
                                try:
                                    next_url = httpx.URL(location).human_repr()
                                except Exception:
                                    last_exc = NetworkError("Invalid redirect Location header")
                                    break
                            redirects += 1
                            if redirects > DEFAULT_MAX_REDIRECTS:
                                last_exc = NetworkError("Too many redirects")
                            else:
                                cur_url = next_url
                                # Loop to enforce egress on hop
                                continue
                    else:
                        # final response
                        if resp.status_code < 400:
                            # metrics for success
                            try:
                                host = _parse_host_from_url(str(resp.request.url))
                                get_metrics_registry().increment(
                                    "http_client_requests_total", 1, labels={"method": method.upper(), "host": host, "status": str(resp.status_code)}
                                )
                                get_metrics_registry().observe(
                                    "http_client_request_duration_seconds",
                                    time.time() - t0,
                                    labels={"method": method.upper(), "host": host},
                                )
                            except Exception:
                                pass
                            return resp
                        else:
                            # candidate for retry
                            should, rsn = _should_retry(method, resp.status_code, None, retry)
                            if not should or attempt == attempts:
                                return resp
                            reason = rsn
                            try:
                                host = _parse_host_from_url(str(resp.request.url))
                                get_metrics_registry().increment("http_client_retries_total", 1, labels={"reason": reason})
                            except Exception:
                                pass
                            # Honor Retry-After
                            delay = 0.0
                            if retry.respect_retry_after:
                                ra = resp.headers.get("retry-after")
                                if ra:
                                    try:
                                        delay = float(ra)
                                    except Exception:
                                        delay = 0.0
                            if delay <= 0:
                                delay = _decorrelated_jitter_sleep(sleep_s, retry.backoff_base_ms, retry.backoff_cap_s)
                            logger.debug(
                                f"afetch retry attempt={attempt} reason={reason} delay={delay:.3f}s url={cur_url}"
                            )
                            await asyncio.sleep(delay)
                            sleep_s = delay
                            # restart outer attempt loop
                            break

                # network error path
                if last_exc is not None:
                    should, rsn = _should_retry(method, None, last_exc, retry)
                    if not should or attempt == attempts:
                        raise last_exc
                    try:
                        get_metrics_registry().increment("http_client_retries_total", 1, labels={"reason": rsn})
                    except Exception:
                        pass
                    delay = _decorrelated_jitter_sleep(sleep_s, retry.backoff_base_ms, retry.backoff_cap_s)
                    logger.debug(
                        f"afetch network retry attempt={attempt} reason={rsn} delay={delay:.3f}s url={cur_url}"
                    )
                    await asyncio.sleep(delay)
                    sleep_s = delay
                    break

        # If we exit loop without return, attempts exhausted
        raise RetryExhaustedError("All retry attempts exhausted")
    finally:
        if need_close:
            try:
                await ac.aclose()
            except Exception:
                pass


def fetch(
    *,
    method: str,
    url: str,
    client: Optional["httpx.Client"] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    files: Optional[Any] = None,
    timeout: Optional[Union[float, "httpx.Timeout"]] = None,
    allow_redirects: bool = True,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    retry: Optional[RetryPolicy] = None,
) -> "httpx.Response":
    if httpx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available")
    retry = retry or RetryPolicy()
    _validate_egress_or_raise(url)
    _validate_proxies_or_raise(proxies)

    attempts = max(1, retry.attempts)
    sleep_s = 0.0
    t0 = time.time()

    def _do_once(sc: "httpx.Client", target_url: str) -> Tuple[Optional["httpx.Response"], str]:
        req_headers = _inject_trace_headers(headers)
        try:
            r = sc.request(
                method.upper(),
                target_url,
                headers=req_headers,
                params=params,
                json=json,
                data=data,
                files=files,
                timeout=timeout,
                follow_redirects=False,
            )
            return r, "ok"
        except Exception as e:
            return None, e.__class__.__name__

    need_close = False
    sc = client
    if sc is None:
        sc = create_client(proxies=proxies)
        need_close = True

    try:
        for attempt in range(1, attempts + 1):
            cur_url = url
            redirects = 0
            while True:
                _validate_egress_or_raise(cur_url)
                resp, reason = _do_once(sc, cur_url)
                if resp is None:
                    should, rsn = _should_retry(method, None, NetworkError(reason), retry)
                    if not should or attempt == attempts:
                        raise NetworkError(reason)
                    try:
                        get_metrics_registry().increment("http_client_retries_total", 1, labels={"reason": rsn})
                    except Exception:
                        pass
                    delay = _decorrelated_jitter_sleep(sleep_s, retry.backoff_base_ms, retry.backoff_cap_s)
                    logger.debug(
                        f"fetch network retry attempt={attempt} reason={rsn} delay={delay:.3f}s url={cur_url}"
                    )
                    time.sleep(delay)
                    sleep_s = delay
                    break
                # redirect handling
                if allow_redirects and resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    try:
                        resp.close()
                    except Exception:
                        pass
                    if not location:
                        if attempt == attempts:
                            raise NetworkError("Redirect without Location header")
                        delay = _decorrelated_jitter_sleep(sleep_s, retry.backoff_base_ms, retry.backoff_cap_s)
                        time.sleep(delay)
                        sleep_s = delay
                        break
                    try:
                        next_url = resp.request.url.join(httpx.URL(location)).human_repr()
                    except Exception:
                        try:
                            next_url = httpx.URL(location).human_repr()
                        except Exception:
                            raise NetworkError("Invalid redirect Location header")
                    redirects += 1
                    if redirects > DEFAULT_MAX_REDIRECTS:
                        raise NetworkError("Too many redirects")
                    cur_url = next_url
                    continue
                if resp.status_code < 400:
                    try:
                        host = _parse_host_from_url(str(resp.request.url))
                        get_metrics_registry().increment(
                            "http_client_requests_total", 1, labels={"method": method.upper(), "host": host, "status": str(resp.status_code)}
                        )
                        get_metrics_registry().observe(
                            "http_client_request_duration_seconds",
                            time.time() - t0,
                            labels={"method": method.upper(), "host": host},
                        )
                    except Exception:
                        pass
                    return resp
                should, rsn = _should_retry(method, resp.status_code, None, retry)
                if not should or attempt == attempts:
                    return resp
                try:
                    get_metrics_registry().increment("http_client_retries_total", 1, labels={"reason": rsn})
                except Exception:
                    pass
                delay = 0.0
                if retry.respect_retry_after:
                    ra = resp.headers.get("retry-after")
                    if ra:
                        try:
                            delay = float(ra)
                        except Exception:
                            delay = 0.0
                if delay <= 0:
                    delay = _decorrelated_jitter_sleep(sleep_s, retry.backoff_base_ms, retry.backoff_cap_s)
                logger.debug(
                    f"fetch retry attempt={attempt} reason={rsn} delay={delay:.3f}s url={cur_url}"
                )
                time.sleep(delay)
                sleep_s = delay
                break
        raise RetryExhaustedError("All retry attempts exhausted")
    finally:
        if need_close:
            try:
                sc.close()
            except Exception:
                pass


# --------------------------------------------------------------------------------------
# JSON helpers
# --------------------------------------------------------------------------------------

async def afetch_json(
    *,
    method: str,
    url: str,
    client: Optional["httpx.AsyncClient"] = None,
    require_json_ct: bool = True,
    max_bytes: Optional[int] = None,
    **kwargs: Any,
) -> Any:
    r = await afetch(method=method, url=url, client=client, **kwargs)
    ctype = r.headers.get("content-type", "").lower()
    if require_json_ct and "application/json" not in ctype:
        await r.aclose()
        raise JSONDecodeError("Response is not application/json")
    if max_bytes is not None:
        clen = r.headers.get("content-length")
        if clen and int(clen) > max_bytes:
            await r.aclose()
            raise JSONDecodeError("Response exceeds max_bytes limit")
    try:
        data = r.json()
    except Exception as e:
        await r.aclose()
        raise JSONDecodeError(str(e))
    return data


def fetch_json(
    *,
    method: str,
    url: str,
    client: Optional["httpx.Client"] = None,
    require_json_ct: bool = True,
    max_bytes: Optional[int] = None,
    **kwargs: Any,
) -> Any:
    r = fetch(method=method, url=url, client=client, **kwargs)
    ctype = r.headers.get("content-type", "").lower()
    if require_json_ct and "application/json" not in ctype:
        r.close()
        raise JSONDecodeError("Response is not application/json")
    if max_bytes is not None:
        clen = r.headers.get("content-length")
        if clen and int(clen) > max_bytes:
            r.close()
            raise JSONDecodeError("Response exceeds max_bytes limit")
    try:
        data = r.json()
    except Exception as e:
        r.close()
        raise JSONDecodeError(str(e))
    return data


# --------------------------------------------------------------------------------------
# Streaming helpers
# --------------------------------------------------------------------------------------

async def astream_bytes(
    *,
    method: str,
    url: str,
    client: Optional["httpx.AsyncClient"] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    files: Optional[Any] = None,
    timeout: Optional[Union[float, "httpx.Timeout"]] = None,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    chunk_size: int = 65536,
) -> AsyncIterator[bytes]:
    if httpx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available")
    _validate_egress_or_raise(url)
    _validate_proxies_or_raise(proxies)

    need_close = False
    ac = client
    if ac is None:
        ac = create_async_client(proxies=proxies)
        need_close = True

    req_headers = _inject_trace_headers(headers)
    try:
        async with ac.stream(
            method.upper(), url, headers=req_headers, params=params, json=json, data=data, files=files, timeout=timeout
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes(chunk_size):
                yield chunk
    except asyncio.CancelledError:
        # propagate cancellations cleanly
        raise
    except httpx.HTTPError as e:
        raise NetworkError(e.__class__.__name__) from e
    finally:
        if need_close:
            try:
                await ac.aclose()
            except Exception:
                pass


async def astream_sse(
    *,
    url: str,
    client: Optional["httpx.AsyncClient"] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: Optional[Union[float, "httpx.Timeout"]] = None,
) -> AsyncIterator[SSEEvent]:
    hdrs = {"Accept": "text/event-stream"}
    if headers:
        hdrs.update(headers)

    buffer = ""

    async for chunk in astream_bytes(
        method="GET",
        url=url,
        client=client,
        headers=hdrs,
        params=params,
        timeout=timeout,
    ):
        try:
            text = chunk.decode("utf-8", errors="replace")
        except Exception as e:
            raise StreamingProtocolError(f"Failed to decode SSE chunk: {e}")
        buffer += text
        while "\n\n" in buffer or "\r\n\r\n" in buffer:
            if "\r\n\r\n" in buffer and ("\n\n" not in buffer or buffer.index("\r\n\r\n") < buffer.index("\n\n")):
                raw, buffer = buffer.split("\r\n\r\n", 1)
            else:
                raw, buffer = buffer.split("\n\n", 1)
            event = _parse_sse_event(raw)
            if event is not None:
                yield event


def _parse_sse_event(raw: str) -> Optional[SSEEvent]:
    event = SSEEvent()
    data_lines: list[str] = []
    for line in raw.splitlines():
        if not line or line.startswith(":"):
            continue
        if ":" in line:
            field, val = line.split(":", 1)
            val = val[1:] if val.startswith(" ") else val
        else:
            field, val = line, ""
        if field == "event":
            event.event = val
        elif field == "data":
            data_lines.append(val)
        elif field == "id":
            event.id = val
        elif field == "retry":
            try:
                event.retry = int(val)
            except Exception:
                pass
    event.data = "\n".join(data_lines)
    return event


# --------------------------------------------------------------------------------------
# Download helpers
# --------------------------------------------------------------------------------------

def download(
    *,
    url: str,
    dest: Union[str, Path],
    client: Optional["httpx.Client"] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: Optional[Union[float, "httpx.Timeout"]] = None,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    checksum: Optional[str] = None,
    checksum_alg: str = "sha256",
    resume: bool = False,
    retry: Optional[RetryPolicy] = None,
) -> Path:
    if httpx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available")
    _validate_egress_or_raise(url)
    _validate_proxies_or_raise(proxies)
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".part")

    retry = retry or RetryPolicy()

    need_close = False
    sc = client
    if sc is None:
        sc = create_client(proxies=proxies)
        need_close = True

    attempts = max(1, retry.attempts)
    sleep_s = 0.0

    try:
        for attempt in range(1, attempts + 1):
            req_headers = _inject_trace_headers(headers)
            # Basic resume support
            existing = 0
            if resume and tmp_path.exists():
                try:
                    existing = tmp_path.stat().st_size
                except Exception:
                    existing = 0
                if existing > 0:
                    req_headers = dict(req_headers)
                    req_headers["Range"] = f"bytes={existing}-"

            last_exc: Optional[Exception] = None
            try:
                with sc.stream("GET", url, headers=req_headers, params=params, timeout=timeout) as resp:
                    if resp.status_code in (200, 206):
                        hasher = hashlib.new(checksum_alg) if checksum else None
                        mode = "ab" if (resume and existing > 0 and resp.status_code == 206) else "wb"
                        with open(tmp_path, mode) as f:
                            for chunk in resp.iter_bytes():
                                if not chunk:
                                    continue
                                f.write(chunk)
                                if hasher is not None:
                                    hasher.update(chunk)
                        # Validate checksum
                        if checksum and hasher is not None:
                            hex_val = hasher.hexdigest()
                            if hex_val.lower() != checksum.lower():
                                raise DownloadError("Checksum validation failed")
                        # Validate content-length if present (when not resuming)
                        clen = resp.headers.get("content-length")
                        if clen and not resume:
                            try:
                                if tmp_path.stat().st_size != int(clen):
                                    raise DownloadError("Content-Length mismatch")
                            except Exception:
                                raise
                        tmp_path.replace(dest_path)
                        return dest_path
                    else:
                        should, rsn = _should_retry("GET", resp.status_code, None, retry)
                        if not should or attempt == attempts:
                            raise DownloadError(f"Download failed with status {resp.status_code}")
                        try:
                            get_metrics_registry().increment("http_client_retries_total", 1, labels={"reason": rsn})
                        except Exception:
                            pass
                        delay = _decorrelated_jitter_sleep(sleep_s, retry.backoff_base_ms, retry.backoff_cap_s)
                        logger.debug(
                            f"download retry attempt={attempt} reason={rsn} delay={delay:.3f}s url={url}"
                        )
                        time.sleep(delay)
                        sleep_s = delay
                        if not resume:
                            try:
                                if tmp_path.exists():
                                    tmp_path.unlink()
                            except Exception:
                                pass
                        continue
            except Exception as e:
                last_exc = e

            if last_exc is not None:
                should, rsn = _should_retry("GET", None, last_exc, retry)
                if not should or attempt == attempts:
                    try:
                        if tmp_path.exists() and (not resume or attempt == attempts):
                            tmp_path.unlink()
                    except Exception:
                        pass
                    if isinstance(last_exc, DownloadError):
                        raise last_exc
                    raise DownloadError(str(last_exc))
                try:
                    get_metrics_registry().increment("http_client_retries_total", 1, labels={"reason": rsn})
                except Exception:
                    pass
                delay = _decorrelated_jitter_sleep(sleep_s, retry.backoff_base_ms, retry.backoff_cap_s)
                logger.debug(
                    f"download network retry attempt={attempt} reason={rsn} delay={delay:.3f}s url={url}"
                )
                time.sleep(delay)
                sleep_s = delay
                continue
        raise RetryExhaustedError("All retry attempts exhausted (download)")
    finally:
        if need_close:
            try:
                sc.close()
            except Exception:
                pass


async def adownload(
    *,
    url: str,
    dest: Union[str, Path],
    client: Optional["httpx.AsyncClient"] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: Optional[Union[float, "httpx.Timeout"]] = None,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    checksum: Optional[str] = None,
    checksum_alg: str = "sha256",
    resume: bool = False,
    retry: Optional[RetryPolicy] = None,
) -> Path:
    # Reuse sync downloader in a thread to avoid blocking event loop on file I/O
    return await asyncio.to_thread(
        download,
        url=url,
        dest=dest,
        client=None,  # create own sync client
        headers=headers,
        params=params,
        timeout=timeout,
        proxies=proxies,
        checksum=checksum,
        checksum_alg=checksum_alg,
        resume=resume,
        retry=retry,
    )


__all__ = [
    "HttpResponse",
    "RetryPolicy",
    "SSEEvent",
    "create_async_client",
    "create_client",
    "afetch",
    "fetch",
    "afetch_json",
    "fetch_json",
    "astream_bytes",
    "astream_sse",
    "download",
    "adownload",
]
