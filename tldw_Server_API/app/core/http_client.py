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
import json
import os
import time
import random
import hashlib
import ssl
import socket
import threading
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Optional, Dict, Any, TypedDict, AsyncIterator, Tuple, Callable, Union, Iterable
from urllib.parse import urlparse, urljoin
import re

try:
    # Python 3.8+/backport safe import
    from importlib import metadata as _importlib_metadata  # type: ignore
except Exception:  # pragma: no cover
    _importlib_metadata = None  # type: ignore

from loguru import logger

try:
    import httpx
except Exception:  # pragma: no cover - optional dependency
    httpx = None  # type: ignore

try:
    import aiohttp
except Exception:  # pragma: no cover - optional dependency
    aiohttp = None  # type: ignore

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
from tldw_Server_API.app.core.Metrics.traces import get_tracing_manager


def _resolve_httpx():
    """Return the current `httpx` module, honoring test stubs in sys.modules.

    Falls back to the module imported at file import time if dynamic import fails.
    """
    try:
        import importlib
        return importlib.import_module("httpx")
    except Exception:
        return httpx  # type: ignore


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
ENFORCE_TLS_MIN = (
    os.getenv("HTTP_ENFORCE_TLS_MIN")
    or os.getenv("TLS_ENFORCE_MIN_VERSION")
    or "false"
)
ENFORCE_TLS_MIN = (str(ENFORCE_TLS_MIN).lower() in {"1", "true", "yes", "on"})
TLS_MIN_VERSION = (os.getenv("HTTP_TLS_MIN_VERSION") or os.getenv("TLS_MIN_VERSION") or "1.2").strip()


def _httpx_timeout_from_defaults() -> "httpx.Timeout":
    return httpx.Timeout(
        connect=DEFAULT_CONNECT_TIMEOUT,
        read=DEFAULT_READ_TIMEOUT,
        write=DEFAULT_WRITE_TIMEOUT,
        pool=DEFAULT_POOL_TIMEOUT,
    )


def build_limits(
    *,
    max_connections: Optional[int] = None,
    max_keepalive_connections: Optional[int] = None,
    keepalive_expiry: Optional[float] = None,
) -> Optional["httpx.Limits"]:
    """Create an httpx.Limits instance when httpx is available."""
    _hx = _resolve_httpx()
    if _hx is None or not hasattr(_hx, "Limits"):
        return None
    kwargs: Dict[str, Any] = {}
    if max_connections is not None:
        kwargs["max_connections"] = max_connections
    if max_keepalive_connections is not None:
        kwargs["max_keepalive_connections"] = max_keepalive_connections
    if keepalive_expiry is not None:
        kwargs["keepalive_expiry"] = keepalive_expiry
    if not kwargs:
        return None
    try:
        return _hx.Limits(**kwargs)
    except Exception:
        return None


_CACHED_VERSION: Optional[str] = None


def _get_project_version() -> str:
    global _CACHED_VERSION
    if _CACHED_VERSION:
        return _CACHED_VERSION
    # 1) Env override
    v = os.getenv("TLDW_VERSION")
    if v:
        _CACHED_VERSION = v.strip()
        return _CACHED_VERSION
    # 2) Try package metadata if installed
    try:
        if _importlib_metadata is not None:
            _CACHED_VERSION = _importlib_metadata.version("tldw-server")  # type: ignore[attr-defined]
            if _CACHED_VERSION:
                return _CACHED_VERSION
    except Exception:
        pass
    # 3) Fallback: parse pyproject.toml in repo root
    try:
        root = Path(__file__).resolve().parents[3]
        pp = root / "pyproject.toml"
        if pp.exists():
            text = pp.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"^version\s*=\s*\"([^\"]+)\"", text, re.MULTILINE)
            if m:
                _CACHED_VERSION = m.group(1).strip()
                return _CACHED_VERSION
    except Exception:
        pass
    _CACHED_VERSION = "0.0.0"
    return _CACHED_VERSION


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
                description="Total egress policy denials for outbound HTTP",
                labels=["reason"],
            )
        )
    except Exception:
        pass

# Ensure metrics are registered on import
try:
    _register_http_client_metrics_once()
except Exception:
    pass
    try:
        registry.register_metric(
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


class _AiohttpResponse:
    def __init__(self, response: Any, body: bytes) -> None:
        self._response = response
        self.status_code = int(getattr(response, "status", 0))
        self.headers = getattr(response, "headers", {}) or {}
        self.url = str(getattr(response, "url", ""))
        self.request = SimpleNamespace(url=self.url)
        self._body = body or b""
        try:
            encoding = getattr(response, "charset", None) or "utf-8"
        except Exception:
            encoding = "utf-8"
        try:
            self._text = self._body.decode(encoding, errors="replace")
        except Exception:
            self._text = self._body.decode("utf-8", errors="replace")

    @property
    def text(self) -> str:
        return self._text

    @property
    def content(self) -> bytes:
        return self._body

    def json(self) -> Any:
        return json.loads(self._text)

    def raise_for_status(self) -> None:
        if self.status_code < 400:
            return
        if httpx is not None:
            try:
                req = httpx.Request("GET", self.url)
                raise httpx.HTTPStatusError(f"HTTP {self.status_code}", request=req, response=self)  # type: ignore[arg-type]
            except Exception:
                raise NetworkError(f"HTTP {self.status_code}")
        raise NetworkError(f"HTTP {self.status_code}")

    async def aclose(self) -> None:
        try:
            if self._response is not None:
                self._response.release()
        except Exception:
            pass

    async def aiter_bytes(self, chunk_size: int = 65536) -> AsyncIterator[bytes]:
        if not self._body:
            return
        for idx in range(0, len(self._body), chunk_size):
            yield self._body[idx : idx + chunk_size]


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


def _sanitize_accept_encoding_for_backend(headers: Optional[Dict[str, str]], backend: str) -> Dict[str, str]:
    """Return a copy of headers with backend-specific Accept-Encoding tweaks.

    - Case-insensitively reads/removes existing Accept-Encoding headers.
    - For 'httpx' backend, removes any 'zstd' codings (with or without parameters, e.g. 'zstd;q=0.9').
    - Writes back a single canonical 'Accept-Encoding' header if tokens remain; otherwise removes it.
    - Best-effort: on any parsing error, leaves headers unchanged.
    """
    hdrs: Dict[str, str] = dict(headers or {})
    if str(backend).lower() != "httpx":
        return hdrs
    try:
        # Find all Accept-Encoding header keys regardless of case
        ae_keys = [k for k in hdrs.keys() if k.lower() == "accept-encoding"]
        if not ae_keys:
            return hdrs

        # Combine values from all variants
        raw_vals: list[str] = []
        for k in ae_keys:
            v = hdrs.get(k)
            if v is None:
                continue
            raw_vals.append(str(v))
        combined = ",".join(raw_vals)

        # Parse tokens, dropping any with coding 'zstd' (case-insensitive), regardless of parameters
        filtered: list[str] = []
        for part in combined.split(','):
            token = part.strip()
            if not token:
                continue
            coding = token.split(';', 1)[0].strip().lower()
            if coding == 'zstd':
                continue
            filtered.append(token)

        # Commit: remove all original variants
        for k in ae_keys:
            hdrs.pop(k, None)
        # Write canonical header back if any tokens remain
        if filtered:
            hdrs["Accept-Encoding"] = ", ".join(filtered)
        # else: if nothing remains, header stays removed
    except Exception:
        # Best-effort: return original headers unchanged
        return dict(headers or {})
    return hdrs


def _url_parts(u: Union[str, Any]) -> Tuple[str, str, str]:
    """Return (scheme, host, path) for logging; redacts query by omission."""
    try:
        s = str(u)
    except Exception:
        s = ""
    try:
        p = urlparse(s)
        scheme = (p.scheme or "").lower()
        host = (p.hostname or "").lower()
        path = p.path or "/"
        return scheme, host, path
    except Exception:
        return "", "", ""


def _log_outbound_request(
    *,
    method: str,
    url: Union[str, Any],
    status_code: int,
    start_time: float,
    attempt: int,
    last_retry_delay_s: float = 0.0,
    exception_class: str = "",
) -> None:
    """Emit a single structured log line for an outbound HTTP call.

    Fields: request_id (from global log context), method, scheme, host, path,
    status_code, duration_ms, attempt, retry_delay_ms, exception_class.
    """
    try:
        duration_ms = int(max(0.0, time.time() - start_time) * 1000)
        retry_delay_ms = int(max(0.0, last_retry_delay_s) * 1000)
        scheme, host, path = _url_parts(url)
        lvl = "warning" if (status_code >= 400 or exception_class) else "info"
        logger.bind(
            method=method.upper(),
            scheme=scheme,
            host=host,
            path=path,
            status_code=int(status_code),
            duration_ms=duration_ms,
            attempt=int(attempt),
            retry_delay_ms=retry_delay_ms,
            exception_class=exception_class,
        ).log(lvl, "http.client outbound")
    except Exception:
        # Never raise on logging failures
        pass

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
    # Also propagate X-Request-Id from tracing baggage when available
    try:
        tm = get_tracing_manager()
        req_id = tm.get_baggage("request_id")
        if req_id:
            out.setdefault("X-Request-Id", str(req_id))
    except Exception:
        pass
    return out


def _validate_egress_or_raise(url: str) -> None:
    from urllib.parse import urlparse as _urlparse
    from tldw_Server_API.app.core.Security.egress import evaluate_url_policy

    # In test environments, avoid DNS-based private IP checks for hostnames
    # (they can hang or be environment-dependent). For literal IPs we still
    # enforce the default private IP policy so security-focused tests remain
    # accurate.
    block_override: Optional[bool] = None
    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TESTING"):
        try:
            parsed = _urlparse(url)
            host = (parsed.hostname or "").strip()
        except Exception:
            host = ""
        is_ip = False
        if host:
            try:
                import ipaddress as _ipaddr
                _ipaddr.ip_address(host)
                is_ip = True
            except Exception:
                is_ip = False
        if not is_ip:
            block_override = False

    res = evaluate_url_policy(url, block_private_override=block_override)
    if not getattr(res, "allowed", False):
        reason = res.reason or "URL not allowed by egress policy"
        # metrics
        try:
            get_metrics_registry().increment(
                "http_client_egress_denials_total", 1, labels={"reason": (reason or "denied")}
            )
        except Exception:
            pass
        raise EgressPolicyError(reason)


def _is_url_allowed(url: str) -> bool:
    """Lightweight policy check used by simple fetch path (tests monkeypatch this).

    Delegates to the central egress policy evaluator and returns a boolean.
    """
    try:
        from tldw_Server_API.app.core.Security.egress import evaluate_url_policy
        res = evaluate_url_policy(url)
        return bool(getattr(res, "allowed", False))
    except Exception:
        # Fail closed in strict paths; the simple path's callers expect explicit
        # ValueError on denial and do not rely on exceptions from here.
        return False


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


def _resolve_proxy_for_url(url: str, proxies: Optional[Union[str, Dict[str, str]]]) -> Optional[str]:
    if not proxies:
        return None
    if isinstance(proxies, str):
        return proxies
    try:
        scheme = (urlparse(url).scheme or "").lower()
    except Exception:
        scheme = ""
    if scheme and scheme in proxies:
        return proxies.get(scheme)
    return proxies.get("http") or proxies.get("https")


def _resolve_redirect_url(base_url: str, location: str) -> Optional[str]:
    try:
        if httpx is not None:
            try:
                return str(httpx.URL(base_url).join(httpx.URL(location)))
            except Exception:
                return str(httpx.URL(location))
        return str(urljoin(base_url, location))
    except Exception:
        return None


def _get_response_url(resp: Any, fallback: str) -> str:
    try:
        req = getattr(resp, "request", None)
        url = getattr(req, "url", None)
        if url:
            return str(url)
    except Exception:
        pass
    try:
        url = getattr(resp, "url", None)
        if url:
            return str(url)
    except Exception:
        pass
    return str(fallback)


def _is_dns_resolution_error(exc: Exception) -> bool:
    """Best-effort detection of DNS resolution / unknown-host failures.

    Looks for socket.gaierror in the exception chain and for common
    platform-specific substrings in the message, including the explicit
    sentinel used by this module ("DNSResolutionError").
    """
    try:
        if getattr(exc, "_tldw_dns_resolution", False):
            return True
    except Exception:
        pass
    try:
        import socket as _socket

        markers = (
            "nodename nor servname provided",
            "Name or service not known",
            "Temporary failure in name resolution",
            "Host could not be resolved",
            "DNSResolutionError",
        )
        seen_ids: set[int] = set()
        cur: Optional[BaseException] = exc
        while cur is not None and id(cur) not in seen_ids:
            seen_ids.add(id(cur))
            if isinstance(cur, _socket.gaierror):
                return True
            msg = str(cur)
            if any(m in msg for m in markers):
                return True
            next_exc = getattr(cur, "__cause__", None) or getattr(cur, "__context__", None)
            if not isinstance(next_exc, BaseException):
                break
            cur = next_exc
    except Exception:
        return False
    return False


def _is_aiohttp_client(client: Any) -> bool:
    if aiohttp is None:
        return False
    try:
        return isinstance(client, aiohttp.ClientSession)
    except Exception:
        return False


def _aiohttp_timeout_from_defaults() -> "aiohttp.ClientTimeout":
    return aiohttp.ClientTimeout(
        total=None,
        connect=DEFAULT_CONNECT_TIMEOUT,
        sock_connect=DEFAULT_CONNECT_TIMEOUT,
        sock_read=DEFAULT_READ_TIMEOUT,
    )


def _aiohttp_timeout_from_value(timeout: Optional[Any]) -> Optional["aiohttp.ClientTimeout"]:
    if aiohttp is None:  # pragma: no cover
        return None
    if timeout is None:
        return _aiohttp_timeout_from_defaults()
    if isinstance(timeout, aiohttp.ClientTimeout):
        return timeout
    if isinstance(timeout, (int, float)):
        return aiohttp.ClientTimeout(total=float(timeout))
    # httpx.Timeout or similar object with connect/read attrs
    connect = getattr(timeout, "connect", None)
    read = getattr(timeout, "read", None)
    return aiohttp.ClientTimeout(
        total=None,
        connect=connect if connect is not None else DEFAULT_CONNECT_TIMEOUT,
        sock_connect=connect if connect is not None else DEFAULT_CONNECT_TIMEOUT,
        sock_read=read if read is not None else DEFAULT_READ_TIMEOUT,
    )


def _aiohttp_ssl_from_verify(verify: Optional[Any]) -> Optional[Any]:
    if aiohttp is None:  # pragma: no cover
        return None
    if verify is None or verify is True:
        return _build_ssl_context(ENFORCE_TLS_MIN, TLS_MIN_VERSION)
    if verify is False:
        return False
    if isinstance(verify, ssl.SSLContext):
        return verify
    if isinstance(verify, str):
        try:
            ctx = ssl.create_default_context(cafile=verify)
            if ENFORCE_TLS_MIN:
                try:
                    ctx.minimum_version = _tls_min_version_from_str(TLS_MIN_VERSION)
                except Exception:
                    pass
            return ctx
        except Exception:
            return _build_ssl_context(ENFORCE_TLS_MIN, TLS_MIN_VERSION)
    return _build_ssl_context(ENFORCE_TLS_MIN, TLS_MIN_VERSION)


_AIOHTTP_SESSION_CACHE: Dict[int, Any] = {}
_AIOHTTP_SESSION_LOCK = threading.Lock()


def _get_aiohttp_session() -> "aiohttp.ClientSession":
    if aiohttp is None:  # pragma: no cover
        raise RuntimeError("aiohttp is not available")
    loop = asyncio.get_running_loop()
    key = id(loop)
    with _AIOHTTP_SESSION_LOCK:
        session = _AIOHTTP_SESSION_CACHE.get(key)
        if session is not None and not getattr(session, "closed", False):
            return session
        connector = None
        try:
            ssl_ctx = _build_ssl_context(ENFORCE_TLS_MIN, TLS_MIN_VERSION)
            connector = aiohttp.TCPConnector(
                limit=int(os.getenv("HTTP_MAX_CONNECTIONS", "100")),
                limit_per_host=int(os.getenv("HTTP_MAX_KEEPALIVE_CONNECTIONS", "20")),
                ssl=ssl_ctx,
            )
        except Exception:
            connector = None
        session = aiohttp.ClientSession(
            connector=connector,
            timeout=_aiohttp_timeout_from_defaults(),
            trust_env=DEFAULT_TRUST_ENV,
            headers=_build_default_headers(),
        )
        try:
            env_pins = _parse_pins_from_env()
            if env_pins:
                setattr(session, "_tldw_cert_pinning", env_pins)
        except Exception:
            pass
        _AIOHTTP_SESSION_CACHE[key] = session
        return session


async def shutdown_http_client() -> None:
    if aiohttp is None:
        return
    sessions: list[Any] = []
    with _AIOHTTP_SESSION_LOCK:
        sessions = list(_AIOHTTP_SESSION_CACHE.values())
        _AIOHTTP_SESSION_CACHE.clear()
    for session in sessions:
        try:
            await session.close()
        except Exception:
            pass


def _iter_file_items(files: Any) -> Iterable[Tuple[str, Any]]:
    if files is None:
        return []
    if isinstance(files, dict):
        return list(files.items())
    return list(files)


def _rewind_files(files: Any) -> None:
    for _, spec in _iter_file_items(files):
        try:
            if isinstance(spec, (tuple, list)) and len(spec) >= 2:
                file_obj = spec[1]
            else:
                file_obj = spec
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
        except Exception:
            continue


def _build_aiohttp_form(data: Optional[Any], files: Optional[Any]) -> Optional["aiohttp.FormData"]:
    if aiohttp is None:  # pragma: no cover
        return None
    if files is None:
        return None
    form = aiohttp.FormData()
    if isinstance(data, dict):
        for key, val in data.items():
            form.add_field(str(key), str(val))
    elif isinstance(data, (list, tuple)):
        for key, val in data:
            form.add_field(str(key), str(val))
    elif data is not None:
        form.add_field("data", str(data))
    for name, spec in _iter_file_items(files):
        filename = None
        file_obj = None
        content_type = None
        if isinstance(spec, (tuple, list)):
            if len(spec) >= 1:
                filename = spec[0]
            if len(spec) >= 2:
                file_obj = spec[1]
            if len(spec) >= 3:
                content_type = spec[2]
        else:
            file_obj = spec
        if filename is None:
            filename = getattr(file_obj, "name", None) or "file"
        form.add_field(
            str(name),
            file_obj,
            filename=str(filename),
            content_type=content_type,
        )
    return form


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
        # Treat DNS resolution / unknown-host failures as permanent.
        try:
            if _is_dns_resolution_error(exc):
                return False, exc.__class__.__name__
        except Exception:
            pass
        # Other network-level exceptions remain retriable.
        return True, exc.__class__.__name__
    if status is None:
        return False, "no_status"
    if status in policy.retry_on_status:
        if m in policy.retry_on_methods or policy.retry_on_unsafe:
            return True, f"{status}"
    return False, "status_not_retriable"


def _build_default_headers(component: Optional[str] = None) -> Dict[str, str]:
    # Standardize UA: tldw_server/<version> (<component>)
    version = _get_project_version()
    if component:
        ua = f"tldw_server/{version} ({component})"
    else:
        ua = f"tldw_server/{version}"
    # Allow env to override completely if provided
    if os.getenv("HTTP_DEFAULT_USER_AGENT"):
        ua = os.getenv("HTTP_DEFAULT_USER_AGENT") or ua
    return {"User-Agent": ua}


def _httpx_limits_default():  # Optional["httpx.Limits"]
    """Return a default httpx.Limits if available; otherwise None.

    Some tests stub `httpx` with minimal objects lacking `Limits`. In that case,
    skip providing limits entirely so the client factory can succeed.
    """
    try:
        _hx = _resolve_httpx()
        if _hx is not None and hasattr(_hx, "Limits"):
            return _hx.Limits(
                max_connections=int(os.getenv("HTTP_MAX_CONNECTIONS", "100")),
                max_keepalive_connections=int(os.getenv("HTTP_MAX_KEEPALIVE_CONNECTIONS", "20")),
            )
    except Exception:
        pass
    return None


def _tls_min_version_from_str(ver: Optional[str]) -> ssl.TLSVersion:
    try:
        v = (ver or "1.2").strip().lower()
        if v in {"1.3", "tls1.3", "tlsv1.3"}:
            return ssl.TLSVersion.TLSv1_3
    except Exception:
        pass
    return ssl.TLSVersion.TLSv1_2


def _build_ssl_context(enforce_min: bool, min_ver: Optional[str]) -> Optional[ssl.SSLContext]:
    if not enforce_min:
        return None
    ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    try:
        ctx.minimum_version = _tls_min_version_from_str(min_ver)
    except Exception:
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def _get_client_cert_pins(client: Any) -> Optional[Dict[str, set[str]]]:
    try:
        pins = getattr(client, "_tldw_cert_pinning", None)
        if pins is None:
            return None
        out: Dict[str, set[str]] = {}
        for host, vals in pins.items():
            out[str(host).lower()] = {str(v).lower() for v in (vals or set())}
        return out
    except Exception:
        return None


def _parse_pins_from_env() -> Optional[Dict[str, set[str]]]:
    """Parse env-driven certificate pins: HTTP_CERT_PINS="hostA=pinA|pinB,hostB=pinC".

    Returns a mapping host -> set of lowercase sha256 hex pins.
    """
    raw = os.getenv("HTTP_CERT_PINS", "").strip()
    if not raw:
        return None
    out: Dict[str, set[str]] = {}
    try:
        parts = [p for p in re.split(r"[,;]", raw) if p]
        for part in parts:
            if "=" not in part:
                continue
            host, pins_str = part.split("=", 1)
            host = host.strip().lower()
            pins = {p.strip().lower() for p in pins_str.split("|") if p.strip()}
            if host and pins:
                out[host] = pins
    except Exception:
        return None
    return out or None


def _check_cert_pinning(host: str, port: int, pins: set[str], min_ver: Optional[str]) -> None:
    if not host or not pins:
        return
    try:
        # Enforce egress policy for the pinning connection itself. This guards
        # against any future callers that might invoke pinning without having
        # already passed through the main egress checks.
        try:
            url = f"https://{host}"
            if port not in (80, 443):
                url = f"https://{host}:{port}"
            _validate_egress_or_raise(url)
        except EgressPolicyError:
            raise
        except Exception as e:
            raise EgressPolicyError(f"TLS pinning egress check failed: {e}")

        ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
        try:
            ctx.minimum_version = _tls_min_version_from_str(min_ver)
        except Exception:
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        with socket.create_connection((host, port), timeout=DEFAULT_CONNECT_TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                der = ssock.getpeercert(binary_form=True)
        if not der:
            raise EgressPolicyError("TLS pinning: no certificate presented")
        fp = hashlib.sha256(der).hexdigest().lower()
        if fp not in pins:
            raise EgressPolicyError("TLS pinning mismatch for host")
    except EgressPolicyError:
        raise
    except Exception as e:
        raise EgressPolicyError(f"TLS pinning verification failed: {e}")


# --------------------------------------------------------------------------------------
# Client factories
# --------------------------------------------------------------------------------------

def _instantiate_client(factory, kwargs: Dict[str, Any]):  # type: ignore[no-untyped-def]
    """Instantiate httpx client tolerating version differences in kwargs.

    On TypeError mentioning an unexpected keyword argument, remove that kwarg
    and retry. This also supports tests that stub `httpx.Client` with a minimal
    constructor accepting only a subset (e.g., just `timeout`).
    """
    import re as _re
    while True:
        try:
            return factory(**kwargs)
        except TypeError as e:
            msg = str(e)
            # Look for patterns like: "unexpected keyword argument 'foo'"
            m = _re.search(r"unexpected keyword argument ['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]", msg)
            key = m.group(1) if m else None
            if key and key in kwargs:
                kwargs.pop(key, None)
                continue
            # Fallback: remove commonly problematic kwargs if present, then retry once
            removed_any = False
            for k in ["limits", "http2", "proxies", "headers", "transport", "trust_env", "base_url", "verify"]:
                if k in kwargs:
                    kwargs.pop(k, None)
                    removed_any = True
            if removed_any:
                continue
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
    enforce_tls_min_version: bool = ENFORCE_TLS_MIN,
    tls_min_version: str = TLS_MIN_VERSION,
    cert_pinning: Optional[Dict[str, set[str]]] = None,
    verify: Optional[Union[bool, str, ssl.SSLContext]] = None,
) -> "httpx.AsyncClient":
    _hx = _resolve_httpx()
    if _hx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available")
    _validate_proxies_or_raise(proxies)
    # Build a timeout value tolerant of stubbed httpx without Timeout class
    if hasattr(_hx, "Timeout"):
        try:
            to = (
                timeout
                if isinstance(timeout, _hx.Timeout)
                else (timeout if timeout is not None else _httpx_timeout_from_defaults())
            )
        except Exception:
            to = timeout if timeout is not None else DEFAULT_READ_TIMEOUT
        if not isinstance(to, getattr(_hx, "Timeout", object)):
            try:
                to = _hx.Timeout(float(to))
            except Exception:
                to = float(timeout) if timeout is not None else DEFAULT_READ_TIMEOUT
    else:
        to = float(timeout) if timeout is not None else DEFAULT_READ_TIMEOUT
    hdrs = _build_default_headers()
    if headers:
        hdrs.update(headers)
    verify_ctx = _build_ssl_context(enforce_tls_min_version, tls_min_version)
    kwargs: Dict[str, Any] = dict(
        timeout=to,
        trust_env=trust_env,
        http2=http2,
        proxies=proxies,
        headers=hdrs,
        transport=transport,
    )
    lim = limits or _httpx_limits_default()
    if lim is not None:
        kwargs["limits"] = lim
    if verify is not None:
        kwargs["verify"] = verify
    elif verify_ctx is not None:
        kwargs["verify"] = verify_ctx
    if base_url is not None:
        kwargs["base_url"] = base_url
    client = _instantiate_client(getattr(_hx, "AsyncClient", object), kwargs)
    try:
        if cert_pinning:
            setattr(client, "_tldw_cert_pinning", cert_pinning)
        else:
            env_pins = _parse_pins_from_env()
            if env_pins:
                setattr(client, "_tldw_cert_pinning", env_pins)
    except Exception:
        pass
    return client


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
    enforce_tls_min_version: bool = ENFORCE_TLS_MIN,
    tls_min_version: str = TLS_MIN_VERSION,
    cert_pinning: Optional[Dict[str, set[str]]] = None,
    verify: Optional[Union[bool, str, ssl.SSLContext]] = None,
) -> "httpx.Client":
    _hx = _resolve_httpx()
    if _hx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available")
    _validate_proxies_or_raise(proxies)
    # Build a timeout value tolerant of stubbed httpx without Timeout class
    if hasattr(_hx, "Timeout"):
        try:
            to = (
                timeout
                if isinstance(timeout, _hx.Timeout)
                else (timeout if timeout is not None else _httpx_timeout_from_defaults())
            )
        except Exception:
            to = timeout if timeout is not None else DEFAULT_READ_TIMEOUT
        if not isinstance(to, getattr(_hx, "Timeout", object)):
            try:
                to = _hx.Timeout(float(to))
            except Exception:
                to = float(timeout) if timeout is not None else DEFAULT_READ_TIMEOUT
    else:
        to = float(timeout) if timeout is not None else DEFAULT_READ_TIMEOUT
    hdrs = _build_default_headers()
    if headers:
        hdrs.update(headers)
    verify_ctx = _build_ssl_context(enforce_tls_min_version, tls_min_version)
    kwargs: Dict[str, Any] = dict(
        timeout=to,
        trust_env=trust_env,
        http2=http2,
        proxies=proxies,
        headers=hdrs,
        transport=transport,
    )
    lim = limits or _httpx_limits_default()
    if lim is not None:
        kwargs["limits"] = lim
    if verify is not None:
        kwargs["verify"] = verify
    elif verify_ctx is not None:
        kwargs["verify"] = verify_ctx
    if base_url is not None:
        kwargs["base_url"] = base_url
    # Debug which factory is being used, to verify test monkeypatches
    try:
        from loguru import logger as _logger  # local import to avoid global cost
        _logger.debug("http_client.create_client: httpx.Client factory={} kwargs_keys={}", getattr(_hx, "Client", None), list(kwargs.keys()))
    except Exception:
        pass
    client = _instantiate_client(getattr(_hx, "Client", object), kwargs)
    try:
        if cert_pinning:
            setattr(client, "_tldw_cert_pinning", cert_pinning)
        else:
            env_pins = _parse_pins_from_env()
            if env_pins:
                setattr(client, "_tldw_cert_pinning", env_pins)
    except Exception:
        pass
    return client


# --------------------------------------------------------------------------------------
# Core request helpers (sync/async) with retries + redirects + egress checks
# --------------------------------------------------------------------------------------

async def _afetch_httpx(
    *,
    method: str,
    url: str,
    client: Optional["httpx.AsyncClient"] = None,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    files: Optional[Any] = None,
    timeout: Optional[Union[float, "httpx.Timeout"]] = None,
    allow_redirects: bool = True,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    retry: Optional[RetryPolicy] = None,
    cert_pinning: Optional[Dict[str, set[str]]] = None,
    verify: Optional[Union[bool, str, ssl.SSLContext]] = None,
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
    tm = get_tracing_manager()
    host_attr = _parse_host_from_url(url)
    method_upper = str(method).upper()
    _head_disable_h2_tried = False
    _head_get_range_tried = False

    async def _do_once(ac: "httpx.AsyncClient", target_url: str) -> Tuple[Optional["httpx.Response"], str]:
        req_headers = _inject_trace_headers(headers)
        # Parity with other paths: drop 'zstd' from Accept-Encoding for httpx
        try:
            try:
                logger.debug(f"afetch _do_once: method={method_upper} url={target_url}")
            except Exception:
                pass
            req_headers = _sanitize_accept_encoding_for_backend(req_headers, "httpx")
        except Exception:
            pass
        try:
            # Optional cert pinning per host
            try:
                pins_map = cert_pinning or _get_client_cert_pins(ac)
                if pins_map:
                    u = httpx.URL(target_url)
                    if u.scheme.lower() == "https":
                        host = (u.host or "").lower()
                        if host in pins_map:
                            _check_cert_pinning(host, int(u.port or 443), pins_map[host], TLS_MIN_VERSION)
            except Exception as e:
                return None, e.__class__.__name__
            # Prefer verb-specific helpers when available so that tests that
            # patch `AsyncClient.post`/`get` can still intercept calls.
            if method_upper == "POST" and hasattr(ac, "post") and verify is None:
                try:
                    logger.debug("afetch _do_once: using AsyncClient.post")
                except Exception:
                    pass
                r = await ac.post(
                    target_url,
                    headers=req_headers,
                    cookies=cookies,
                    params=params,
                    json=json,
                    data=data,
                    files=files,
                    timeout=timeout,
                    follow_redirects=False,
                )
            else:
                try:
                    logger.debug("afetch _do_once: using AsyncClient.request")
                except Exception:
                    pass
                req_kwargs: Dict[str, Any] = dict(
                    headers=req_headers,
                    cookies=cookies,
                    params=params,
                    json=json,
                    data=data,
                    files=files,
                    timeout=timeout,
                    follow_redirects=False,
                )
                r = await ac.request(
                    method_upper,
                    target_url,
                    **req_kwargs,
                )
            return r, "ok"
        except Exception as e:
            # Let callers see HTTPStatusError directly so that adapters/tests
            # can distinguish 4xx/5xx responses from transport failures. All
            # other exceptions are normalized into a NetworkError reason.
            try:
                logger.debug(f"afetch _do_once: caught exception {e!r}")
            except Exception:
                pass
            try:
                _hx = _resolve_httpx()
                if _hx is not None and isinstance(e, getattr(_hx, "HTTPStatusError", Exception)):
                    raise
            except Exception:
                # If httpx cannot be resolved for some reason, fall back to
                # treating the error as a generic network failure.
                pass
            # Classify DNS resolution errors explicitly so that retry logic
            # can treat them as permanent failures.
            try:
                if _is_dns_resolution_error(e):
                    try:
                        setattr(e, "_tldw_dns_resolution", True)
                    except Exception:
                        pass
                    return None, "DNSResolutionError"
            except Exception:
                pass
            return None, e.__class__.__name__

    # Create ephemeral client if none provided
    need_close = False
    ac = client
    if ac is None:
        ac = create_async_client(proxies=proxies, verify=verify)
        need_close = True

    try:
        async with tm.async_span(
            "http.client",
            attributes={
                "http.method": method.upper(),
                "net.host.name": host_attr,
                "url.full": url,
            },
        ):
            for attempt in range(1, attempts + 1):
                last_exc = None
                cur_url = url
                redirects = 0

                # Manual redirect handling inside each attempt
                while True:
                    _validate_egress_or_raise(cur_url)
                    resp, reason = await _do_once(ac, cur_url)
                    if resp is None:
                        # Special HEAD fallbacks: disable HTTP/2, then GET with Range 0-0
                        if method_upper == "HEAD":
                            if not _head_disable_h2_tried:
                                _head_disable_h2_tried = True
                                try:
                                    if need_close:
                                        try:
                                            await ac.aclose()
                                        except Exception:
                                            pass
                                    ac = create_async_client(proxies=proxies, http2=False)
                                    need_close = True
                                    # Retry immediately inside same attempt
                                    continue
                                except Exception:
                                    pass
                            if not _head_get_range_tried:
                                _head_get_range_tried = True
                                try:
                                    req_headers = _inject_trace_headers(headers)
                                    try:
                                        req_headers = _sanitize_accept_encoding_for_backend(req_headers, "httpx")
                                    except Exception:
                                        pass
                                    req_headers.setdefault("Range", "bytes=0-0")
                                    # Use a small per-request timeout specifically for this fallback
                                    try:
                                        _head_fb_to = float(os.getenv("HTTP_HEAD_RANGE_FALLBACK_TIMEOUT", "5"))
                                    except Exception:
                                        _head_fb_to = 5.0
                                    r2 = await ac.request(
                                        "GET",
                                        cur_url,
                                        headers=req_headers,
                                        params=params,
                                        json=json,
                                        data=data,
                                        files=files,
                                        timeout=_head_fb_to,
                                        follow_redirects=False,
                                    )
                                    try:
                                        tm.set_attributes({"http.status_code": int(r2.status_code)})
                                    except Exception:
                                        pass
                                    _log_outbound_request(
                                        method="GET",
                                        url=r2.request.url if hasattr(r2.request, "url") else cur_url,
                                        status_code=int(r2.status_code),
                                        start_time=t0,
                                        attempt=attempt,
                                        last_retry_delay_s=sleep_s,
                                    )
                                    return r2
                                except Exception:
                                    pass
                        # network exception occurred (no HEAD fallback succeeded)
                        last_exc = NetworkError(reason)
                        try:
                            if reason == "DNSResolutionError":
                                setattr(last_exc, "_tldw_dns_resolution", True)
                        except Exception:
                            pass
                        # Exit redirect loop; retry/backoff handled after loop
                        break
                    else:
                        # Handle redirects explicitly to enforce per-hop egress
                        if allow_redirects and resp.status_code in (301, 302, 303, 307, 308):
                            location = resp.headers.get("location")
                            try:
                                await resp.aclose()
                            except Exception:
                                pass
                            if not location:
                                last_exc = NetworkError("Redirect without Location header")
                                break
                            else:
                                try:
                                    next_url = str(resp.request.url.join(httpx.URL(location)))
                                except Exception:
                                    try:
                                        next_url = str(httpx.URL(location))
                                    except Exception:
                                        last_exc = NetworkError("Invalid redirect Location header")
                                        break
                                redirects += 1
                                if redirects > DEFAULT_MAX_REDIRECTS:
                                    last_exc = NetworkError("Too many redirects")
                                    break
                                else:
                                    cur_url = next_url
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
                                try:
                                    tm.set_attributes({"http.status_code": int(resp.status_code)})
                                except Exception:
                                    pass
                                _log_outbound_request(
                                    method=method,
                                    url=resp.request.url,
                                    status_code=int(resp.status_code),
                                    start_time=t0,
                                    attempt=attempt,
                                    last_retry_delay_s=sleep_s,
                                )
                                return resp
                            # candidate for retry
                            should, rsn = _should_retry(method, resp.status_code, None, retry)
                            if not should or attempt == attempts:
                                _log_outbound_request(
                                    method=method,
                                    url=resp.request.url,
                                    status_code=int(resp.status_code),
                                    start_time=t0,
                                    attempt=attempt,
                                    last_retry_delay_s=sleep_s,
                                )
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
                            try:
                                tm.add_event("http.retry", {"attempt": attempt, "reason": reason})
                            except Exception:
                                pass
                            await asyncio.sleep(delay)
                            sleep_s = delay
                            # Restart outer attempt
                            break

                # network error path
                if last_exc is not None:
                    should, rsn = _should_retry(method, None, last_exc, retry)
                    if not should or attempt == attempts:
                        _log_outbound_request(
                            method=method,
                            url=cur_url,
                            status_code=0,
                            start_time=t0,
                            attempt=attempt,
                            last_retry_delay_s=sleep_s,
                            exception_class=last_exc.__class__.__name__,
                        )
                        raise last_exc
                    try:
                        get_metrics_registry().increment("http_client_retries_total", 1, labels={"reason": rsn})
                    except Exception:
                        pass
                    delay = _decorrelated_jitter_sleep(sleep_s, retry.backoff_base_ms, retry.backoff_cap_s)
                    logger.debug(
                        f"afetch network retry attempt={attempt} reason={rsn} delay={delay:.3f}s url={cur_url}"
                    )
                    try:
                        tm.add_event("http.retry", {"attempt": attempt, "reason": rsn})
                    except Exception:
                        pass
                    await asyncio.sleep(delay)
                    sleep_s = delay
                    continue

        # If we exit loop without return, attempts exhausted
        _log_outbound_request(
            method=method,
            url=url,
            status_code=0,
            start_time=t0,
            attempt=attempts,
            last_retry_delay_s=sleep_s,
            exception_class="RetryExhaustedError",
        )
        raise RetryExhaustedError("All retry attempts exhausted")
    finally:
        if need_close:
            try:
                await ac.aclose()
            except Exception:
                pass


async def _afetch_aiohttp(
    *,
    method: str,
    url: str,
    client: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    files: Optional[Any] = None,
    timeout: Optional[Any] = None,
    allow_redirects: bool = True,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    retry: Optional[RetryPolicy] = None,
    cert_pinning: Optional[Dict[str, set[str]]] = None,
    verify: Optional[Any] = None,
) -> _AiohttpResponse:
    if aiohttp is None:  # pragma: no cover
        raise RuntimeError("aiohttp is not available")
    retry = retry or RetryPolicy()
    _validate_egress_or_raise(url)
    _validate_proxies_or_raise(proxies)

    attempts = max(1, retry.attempts)
    sleep_s = 0.0
    t0 = time.time()
    last_exc: Optional[Exception] = None
    tm = get_tracing_manager()
    host_attr = _parse_host_from_url(url)
    method_upper = str(method).upper()
    _head_get_range_tried = False

    ssl_override = _aiohttp_ssl_from_verify(verify)

    async def _do_once(session: "aiohttp.ClientSession", target_url: str) -> Tuple[Optional[_AiohttpResponse], str]:
        req_headers = _inject_trace_headers(headers)
        try:
            req_headers = _sanitize_accept_encoding_for_backend(req_headers, "aiohttp")
        except Exception:
            pass
        try:
            # Optional cert pinning per host
            try:
                pins_map = cert_pinning or _get_client_cert_pins(session)
                if pins_map:
                    if httpx is not None:
                        u = httpx.URL(target_url)
                        host = (u.host or "").lower()
                        port = int(u.port or (443 if (u.scheme or "").lower() == "https" else 80))
                    else:
                        parsed = urlparse(target_url)
                        host = (parsed.hostname or "").lower()
                        port = parsed.port or (443 if (parsed.scheme or "").lower() == "https" else 80)
                    if host in pins_map:
                        _check_cert_pinning(host, port, pins_map[host], TLS_MIN_VERSION)
            except Exception as e:
                return None, e.__class__.__name__
            req_timeout = _aiohttp_timeout_from_value(timeout)
            proxy = _resolve_proxy_for_url(target_url, proxies)
            req_kwargs: Dict[str, Any] = dict(
                headers=req_headers,
                cookies=cookies,
                params=params,
                timeout=req_timeout,
                allow_redirects=False,
            )
            if proxy:
                req_kwargs["proxy"] = proxy
            if ssl_override is not None:
                req_kwargs["ssl"] = ssl_override
            if files is not None:
                _rewind_files(files)
                req_kwargs["data"] = _build_aiohttp_form(data, files)
            else:
                if json is not None:
                    req_kwargs["json"] = json
                if data is not None:
                    req_kwargs["data"] = data
            async with session.request(method_upper, target_url, **req_kwargs) as resp:
                body = await resp.read()
                return _AiohttpResponse(resp, body), "ok"
        except Exception as e:
            try:
                if _is_dns_resolution_error(e):
                    try:
                        setattr(e, "_tldw_dns_resolution", True)
                    except Exception:
                        pass
                    return None, "DNSResolutionError"
            except Exception:
                pass
            return None, e.__class__.__name__

    session = client or _get_aiohttp_session()

    async with tm.async_span(
        "http.client",
        attributes={
            "http.method": method.upper(),
            "net.host.name": host_attr,
            "url.full": url,
        },
    ):
        for attempt in range(1, attempts + 1):
            last_exc = None
            cur_url = url
            redirects = 0

            while True:
                _validate_egress_or_raise(cur_url)
                resp, reason = await _do_once(session, cur_url)
                if resp is None:
                    if method_upper == "HEAD" and not _head_get_range_tried:
                        _head_get_range_tried = True
                        try:
                            req_headers = _inject_trace_headers(headers)
                            req_headers.setdefault("Range", "bytes=0-0")
                            try:
                                _head_fb_to = float(os.getenv("HTTP_HEAD_RANGE_FALLBACK_TIMEOUT", "5"))
                            except Exception:
                                _head_fb_to = 5.0
                            req_timeout = _aiohttp_timeout_from_value(_head_fb_to)
                            proxy = _resolve_proxy_for_url(cur_url, proxies)
                            req_kwargs: Dict[str, Any] = dict(
                                headers=req_headers,
                                cookies=cookies,
                                params=params,
                                timeout=req_timeout,
                                allow_redirects=False,
                            )
                            if proxy:
                                req_kwargs["proxy"] = proxy
                            if ssl_override is not None:
                                req_kwargs["ssl"] = ssl_override
                            async with session.request("GET", cur_url, **req_kwargs) as r2:
                                body = await r2.read()
                                r2_wrap = _AiohttpResponse(r2, body)
                                try:
                                    tm.set_attributes({"http.status_code": int(r2_wrap.status_code)})
                                except Exception:
                                    pass
                                _log_outbound_request(
                                    method="GET",
                                    url=_get_response_url(r2_wrap, cur_url),
                                    status_code=int(r2_wrap.status_code),
                                    start_time=t0,
                                    attempt=attempt,
                                    last_retry_delay_s=sleep_s,
                                )
                                return r2_wrap
                        except Exception:
                            pass
                    last_exc = NetworkError(reason)
                    try:
                        if reason == "DNSResolutionError":
                            setattr(last_exc, "_tldw_dns_resolution", True)
                    except Exception:
                        pass
                    break

                if allow_redirects and resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    if not location:
                        last_exc = NetworkError("Redirect without Location header")
                        break
                    base_url = _get_response_url(resp, cur_url)
                    next_url = _resolve_redirect_url(base_url, location)
                    if not next_url:
                        last_exc = NetworkError("Invalid redirect Location header")
                        break
                    redirects += 1
                    if redirects > DEFAULT_MAX_REDIRECTS:
                        last_exc = NetworkError("Too many redirects")
                        break
                    cur_url = next_url
                    continue

                # final response
                if resp.status_code < 400:
                    try:
                        host = _parse_host_from_url(_get_response_url(resp, cur_url))
                        get_metrics_registry().increment(
                            "http_client_requests_total",
                            1,
                            labels={"method": method.upper(), "host": host, "status": str(resp.status_code)},
                        )
                        get_metrics_registry().observe(
                            "http_client_request_duration_seconds",
                            time.time() - t0,
                            labels={"method": method.upper(), "host": host},
                        )
                    except Exception:
                        pass
                    try:
                        tm.set_attributes({"http.status_code": int(resp.status_code)})
                    except Exception:
                        pass
                    _log_outbound_request(
                        method=method,
                        url=_get_response_url(resp, cur_url),
                        status_code=int(resp.status_code),
                        start_time=t0,
                        attempt=attempt,
                        last_retry_delay_s=sleep_s,
                    )
                    return resp

                should, rsn = _should_retry(method, resp.status_code, None, retry)
                if not should or attempt == attempts:
                    _log_outbound_request(
                        method=method,
                        url=_get_response_url(resp, cur_url),
                        status_code=int(resp.status_code),
                        start_time=t0,
                        attempt=attempt,
                        last_retry_delay_s=sleep_s,
                    )
                    return resp
                reason = rsn
                try:
                    host = _parse_host_from_url(_get_response_url(resp, cur_url))
                    get_metrics_registry().increment("http_client_retries_total", 1, labels={"reason": reason})
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
                    f"afetch retry attempt={attempt} reason={reason} delay={delay:.3f}s url={cur_url}"
                )
                try:
                    tm.add_event("http.retry", {"attempt": attempt, "reason": reason})
                except Exception:
                    pass
                await asyncio.sleep(delay)
                sleep_s = delay
                break

            if last_exc is not None:
                should, rsn = _should_retry(method, None, last_exc, retry)
                if not should or attempt == attempts:
                    _log_outbound_request(
                        method=method,
                        url=cur_url,
                        status_code=0,
                        start_time=t0,
                        attempt=attempt,
                        last_retry_delay_s=sleep_s,
                        exception_class=last_exc.__class__.__name__,
                    )
                    raise last_exc
                try:
                    get_metrics_registry().increment("http_client_retries_total", 1, labels={"reason": rsn})
                except Exception:
                    pass
                delay = _decorrelated_jitter_sleep(sleep_s, retry.backoff_base_ms, retry.backoff_cap_s)
                logger.debug(
                    f"afetch network retry attempt={attempt} reason={rsn} delay={delay:.3f}s url={cur_url}"
                )
                try:
                    tm.add_event("http.retry", {"attempt": attempt, "reason": rsn})
                except Exception:
                    pass
                await asyncio.sleep(delay)
                sleep_s = delay
                continue

    _log_outbound_request(
        method=method,
        url=url,
        status_code=0,
        start_time=t0,
        attempt=attempts,
        last_retry_delay_s=sleep_s,
        exception_class="RetryExhaustedError",
    )
    raise RetryExhaustedError("All retry attempts exhausted")


async def afetch(
    *,
    method: str,
    url: str,
    client: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    files: Optional[Any] = None,
    timeout: Optional[Any] = None,
    allow_redirects: bool = True,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    retry: Optional[RetryPolicy] = None,
    cert_pinning: Optional[Dict[str, set[str]]] = None,
    verify: Optional[Union[bool, str, ssl.SSLContext]] = None,
) -> Any:
    if client is not None:
        if _is_aiohttp_client(client):
            return await _afetch_aiohttp(
                method=method,
                url=url,
                client=client,
                headers=headers,
                cookies=cookies,
                params=params,
                json=json,
                data=data,
                files=files,
                timeout=timeout,
                allow_redirects=allow_redirects,
                proxies=proxies,
                retry=retry,
                cert_pinning=cert_pinning,
                verify=verify,
            )
        return await _afetch_httpx(
            method=method,
            url=url,
            client=client,
            headers=headers,
            cookies=cookies,
            params=params,
            json=json,
            data=data,
            files=files,
            timeout=timeout,
            allow_redirects=allow_redirects,
            proxies=proxies,
            retry=retry,
            cert_pinning=cert_pinning,
            verify=verify,
        )
    if aiohttp is not None:
        return await _afetch_aiohttp(
            method=method,
            url=url,
            client=None,
            headers=headers,
            cookies=cookies,
            params=params,
            json=json,
            data=data,
            files=files,
            timeout=timeout,
            allow_redirects=allow_redirects,
            proxies=proxies,
            retry=retry,
            cert_pinning=cert_pinning,
            verify=verify,
        )
    return await _afetch_httpx(
        method=method,
        url=url,
        client=None,
        headers=headers,
        cookies=cookies,
        params=params,
        json=json,
        data=data,
        files=files,
        timeout=timeout,
        allow_redirects=allow_redirects,
        proxies=proxies,
        retry=retry,
        cert_pinning=cert_pinning,
        verify=verify,
    )


async def apost(
    *,
    url: str,
    client: Optional["httpx.AsyncClient"] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    files: Optional[Any] = None,
    timeout: Optional[Union[float, "httpx.Timeout"]] = None,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
) -> "httpx.Response":
    """
    Minimal async POST helper that enforces egress policy.

    This is intentionally lightweight (no retries/redirect handling) so that
    adapters and unit tests that monkeypatch `httpx.AsyncClient.post` can still
    intercept calls, while centralizing the egress check.
    """
    if httpx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available")
    _validate_egress_or_raise(url)
    _validate_proxies_or_raise(proxies)

    need_close = False
    ac = client
    if ac is None:
        ac = create_async_client(proxies=proxies, timeout=timeout)
        need_close = True

    try:
        resp = await ac.post(
            url,
            headers=headers,
            params=params,
            json=json,
            data=data,
            files=files,
            timeout=timeout,
        )
        return resp
    finally:
        if need_close:
            try:
                await ac.aclose()
            except Exception:
                pass


def _fetch_httpx_response(
    *,
    method: str,
    url: str,
    client: Optional["httpx.Client"] = None,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    files: Optional[Any] = None,
    timeout: Optional[Union[float, "httpx.Timeout"]] = None,
    allow_redirects: bool = True,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    retry: Optional[RetryPolicy] = None,
    cert_pinning: Optional[Dict[str, set[str]]] = None,
) -> "httpx.Response":
    if httpx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available")
    retry = retry or RetryPolicy()
    _validate_egress_or_raise(url)
    _validate_proxies_or_raise(proxies)

    attempts = max(1, retry.attempts)
    sleep_s = 0.0
    t0 = time.time()
    tm = get_tracing_manager()
    host_attr = _parse_host_from_url(url)
    method_upper = str(method).upper()
    _head_disable_h2_tried = False
    _head_get_range_tried = False

    def _do_once(sc: "httpx.Client", target_url: str) -> Tuple[Optional["httpx.Response"], str]:
        req_headers = _inject_trace_headers(headers)
        # Parity with simple fetch: drop 'zstd' from Accept-Encoding for httpx
        try:
            req_headers = _sanitize_accept_encoding_for_backend(req_headers, "httpx")
        except Exception:
            # Best-effort only; ignore sanitizer errors
            pass
        try:
            # Optional cert pinning per host
            try:
                pins_map = cert_pinning or _get_client_cert_pins(sc)
                if pins_map:
                    u = httpx.URL(target_url)
                    if u.scheme.lower() == "https":
                        host = (u.host or "").lower()
                        if host in pins_map:
                            _check_cert_pinning(host, int(u.port or 443), pins_map[host], TLS_MIN_VERSION)
            except Exception as e:
                return None, e.__class__.__name__
            r = sc.request(
                method.upper(),
                target_url,
                headers=req_headers,
                cookies=cookies,
                params=params,
                json=json,
                data=data,
                files=files,
                timeout=timeout,
                follow_redirects=False,
            )
            return r, "ok"
        except Exception as e:
            # Classify DNS resolution errors explicitly so that retry logic
            # can treat them as permanent failures.
            try:
                if _is_dns_resolution_error(e):
                    return None, "DNSResolutionError"
            except Exception:
                pass
            return None, e.__class__.__name__

    need_close = False
    sc = client
    if sc is None:
        sc = create_client(proxies=proxies)
        need_close = True

    try:
        with tm.span(
            "http.client",
            attributes={
                "http.method": method.upper(),
                "net.host.name": host_attr,
                "url.full": url,
            },
        ):
            for attempt in range(1, attempts + 1):
                cur_url = url
                redirects = 0
                while True:
                    _validate_egress_or_raise(cur_url)
                    resp, reason = _do_once(sc, cur_url)
                    if resp is None:
                        if method_upper == "HEAD":
                            if not _head_disable_h2_tried:
                                _head_disable_h2_tried = True
                                try:
                                    if need_close:
                                        try:
                                            sc.close()
                                        except Exception:
                                            pass
                                    sc = create_client(proxies=proxies, http2=False)
                                    need_close = True
                                    # Retry immediately within same attempt
                                    continue
                                except Exception:
                                    pass
                            if not _head_get_range_tried:
                                _head_get_range_tried = True
                                try:
                                    req_headers = _inject_trace_headers(headers)
                                    try:
                                        req_headers = _sanitize_accept_encoding_for_backend(req_headers, "httpx")
                                    except Exception:
                                        pass
                                    req_headers.setdefault("Range", "bytes=0-0")
                                    # Use a small per-request timeout specifically for this fallback
                                    try:
                                        _head_fb_to = float(os.getenv("HTTP_HEAD_RANGE_FALLBACK_TIMEOUT", "5"))
                                    except Exception:
                                        _head_fb_to = 5.0
                                    r2 = sc.request(
                                        "GET",
                                        cur_url,
                                        headers=req_headers,
                                        cookies=cookies,
                                        params=params,
                                        json=json,
                                        data=data,
                                        files=files,
                                        timeout=_head_fb_to,
                                        follow_redirects=False,
                                    )
                                    try:
                                        tm.set_attributes({"http.status_code": int(r2.status_code)})
                                    except Exception:
                                        pass
                                    _log_outbound_request(
                                        method="GET",
                                        url=r2.request.url if hasattr(r2.request, "url") else cur_url,
                                        status_code=int(r2.status_code),
                                        start_time=t0,
                                        attempt=attempt,
                                        last_retry_delay_s=sleep_s,
                                    )
                                    return r2
                                except Exception:
                                    pass
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
                            next_url = str(resp.request.url.join(httpx.URL(location)))
                        except Exception:
                            try:
                                next_url = str(httpx.URL(location))
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
                        try:
                            tm.set_attributes({"http.status_code": int(resp.status_code)})
                        except Exception:
                            pass
                        _log_outbound_request(
                            method=method,
                            url=resp.request.url,
                            status_code=int(resp.status_code),
                            start_time=t0,
                            attempt=attempt,
                            last_retry_delay_s=sleep_s,
                        )
                        return resp
                    should, rsn = _should_retry(method, resp.status_code, None, retry)
                    if not should or attempt == attempts:
                        _log_outbound_request(
                            method=method,
                            url=resp.request.url,
                            status_code=int(resp.status_code),
                            start_time=t0,
                            attempt=attempt,
                            last_retry_delay_s=sleep_s,
                        )
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
                    try:
                        tm.add_event("http.retry", {"attempt": attempt, "reason": rsn})
                    except Exception:
                        pass
                    time.sleep(delay)
                    sleep_s = delay
                    break
        _log_outbound_request(
            method=method,
            url=url,
            status_code=0,
            start_time=t0,
            attempt=attempts,
            last_retry_delay_s=sleep_s,
            exception_class="RetryExhaustedError",
        )
        raise RetryExhaustedError("All retry attempts exhausted")
    finally:
        if need_close:
            try:
                sc.close()
            except Exception:
                pass


def fetch(*args, **kwargs):
    """Dual-mode fetch helper.

    - If called with keyword 'method', delegates to the HTTPX response API and
      returns an httpx.Response (backward compatible with existing callers).
    - Otherwise, provides a simplified fetch suitable for Web_Scraping tests:
      accepts `url` (positional), optional `headers`, `backend` (default 'httpx'),
      and returns a mapping with keys: status, headers, text, url, backend.
    """
    # Response-based API path (existing callers/tests)
    if "method" in kwargs:
        return _fetch_httpx_response(**kwargs)
    # Simple path (tests: Web_Scraping/test_http_client_fetch.py)
    if not args and "url" not in kwargs:
        raise TypeError("fetch() missing required argument: 'url'")
    url = str(args[0] if args else kwargs.get("url"))
    backend = str(kwargs.get("backend", "httpx"))
    headers = kwargs.get("headers") or {}
    cookies = kwargs.get("cookies")
    follow_redirects_cfg = kwargs.get("follow_redirects", None)
    trust_env = kwargs.get("trust_env", None)
    proxies = kwargs.get("proxies", None)
    timeout = kwargs.get("timeout", None)

    # Enforce egress via stubbed policy helper (tests monkeypatch this).
    # This remains intentionally lightweight so tests can override without
    # triggering full DNS lookups in the central policy during unit runs.
    if not _is_url_allowed(url):
        raise ValueError("Egress denied for URL")

    # Validate proxies against allowlist even in simple mode
    _validate_proxies_or_raise(proxies)

    if httpx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available")

    # Sanitize Accept-Encoding as per backend expectations
    req_headers = _sanitize_accept_encoding_for_backend(headers, backend)

    # Determine redirect behavior, honoring env/Config_Files when caller did not
    # explicitly supply follow_redirects.
    if follow_redirects_cfg is None:
        env_allow_redirects = os.getenv("HTTP_ALLOW_REDIRECTS")
        if env_allow_redirects is not None:
            follow_redirects = str(env_allow_redirects).strip().lower() in {"1", "true", "yes", "on"}
        else:
            follow_redirects = True
    else:
        follow_redirects = bool(follow_redirects_cfg)

    allow_cross_host = str(os.getenv("HTTP_ALLOW_CROSS_HOST_REDIRECTS", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    allow_downgrade = str(os.getenv("HTTP_ALLOW_SCHEME_DOWNGRADE", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    def _redirect_allowed(prev: str, nxt: str) -> bool:
        try:
            pu = httpx.URL(prev)
            nu = httpx.URL(nxt)
        except Exception:
            return False
        # Disallow scheme downgrade unless explicitly allowed
        if not allow_downgrade and (pu.scheme or "").lower() == "https" and (nu.scheme or "").lower() == "http":
            return False
        # Same-host redirects are always allowed (subject to egress checks)
        if (pu.host or "").lower() == (nu.host or "").lower():
            return True
        # Cross-host redirects configurable (default disabled)
        return bool(allow_cross_host)

    client_kwargs: Dict[str, Any] = {}
    if timeout is not None:
        client_kwargs["timeout"] = timeout
    if trust_env is not None:
        client_kwargs["trust_env"] = trust_env
    if proxies is not None:
        client_kwargs["proxies"] = proxies

    # Minimal client lifecycle for simple fetch with explicit redirect handling
    with httpx.Client(**client_kwargs) as sc:  # type: ignore[call-arg]
        cur_url = url
        redirects = 0

        while True:
            # Re-enforce lightweight egress guard on each hop
            if not _is_url_allowed(cur_url):
                raise ValueError("Egress denied for URL")

            r = sc.request("GET", cur_url, headers=req_headers, cookies=cookies, follow_redirects=False)
            status = int(getattr(r, "status_code", 0))

            if not follow_redirects or status not in (301, 302, 303, 307, 308):
                break

            location = getattr(r, "headers", {}) or {}
            location = location.get("location") or location.get("Location")
            if not location:
                break

            try:
                base_url = str(getattr(r, "url", cur_url))
                next_url = str(httpx.URL(base_url).join(httpx.URL(location)))
            except Exception:
                try:
                    next_url = str(httpx.URL(location))
                except Exception:
                    break

            if not _redirect_allowed(cur_url, next_url):
                break

            redirects += 1
            if redirects > DEFAULT_MAX_REDIRECTS:
                break

            cur_url = next_url

        return HttpResponse(
            status=status,
            headers=dict(getattr(r, "headers", {}) or {}),
            text=str(getattr(r, "text", "")),
            url=str(getattr(r, "url", cur_url)),
            backend=str(backend),
        )


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

async def _astream_bytes_httpx(
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
    cert_pinning: Optional[Dict[str, set[str]]] = None,
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
    t0 = time.time()
    try:
        # Optional cert pinning
        try:
            pins_map = cert_pinning or _get_client_cert_pins(ac)
            if pins_map:
                u = httpx.URL(url)
                if u.scheme.lower() == "https":
                    host = (u.host or "").lower()
                    if host in pins_map:
                        _check_cert_pinning(host, int(u.port or 443), pins_map[host], TLS_MIN_VERSION)
        except Exception as e:
            raise NetworkError(e.__class__.__name__) from e
        async with ac.stream(
            method.upper(), url, headers=req_headers, params=params, json=json, data=data, files=files, timeout=timeout
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes(chunk_size):
                yield chunk
            # per-request structured log on successful completion
            _log_outbound_request(
                method=method,
                url=resp.request.url,
                status_code=int(resp.status_code),
                start_time=t0,
                attempt=1,
                last_retry_delay_s=0.0,
            )
    except asyncio.CancelledError:
        # propagate cancellations cleanly
        raise
    except httpx.HTTPError as e:
        _log_outbound_request(
            method=method,
            url=url,
            status_code=0,
            start_time=t0,
            attempt=1,
            last_retry_delay_s=0.0,
            exception_class=e.__class__.__name__,
        )
        raise NetworkError(e.__class__.__name__) from e
    finally:
        if need_close:
            try:
                await ac.aclose()
            except Exception:
                pass


async def _astream_bytes_aiohttp(
    *,
    method: str,
    url: str,
    client: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    files: Optional[Any] = None,
    timeout: Optional[Any] = None,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    chunk_size: int = 65536,
    cert_pinning: Optional[Dict[str, set[str]]] = None,
) -> AsyncIterator[bytes]:
    if aiohttp is None:  # pragma: no cover
        raise RuntimeError("aiohttp is not available")
    _validate_egress_or_raise(url)
    _validate_proxies_or_raise(proxies)

    session = client or _get_aiohttp_session()
    req_headers = _inject_trace_headers(headers)
    t0 = time.time()
    try:
        # Optional cert pinning
        try:
            pins_map = cert_pinning or _get_client_cert_pins(session)
            if pins_map:
                if httpx is not None:
                    u = httpx.URL(url)
                    host = (u.host or "").lower()
                    port = int(u.port or (443 if (u.scheme or "").lower() == "https" else 80))
                else:
                    parsed = urlparse(url)
                    host = (parsed.hostname or "").lower()
                    port = parsed.port or (443 if (parsed.scheme or "").lower() == "https" else 80)
                if host in pins_map:
                    _check_cert_pinning(host, port, pins_map[host], TLS_MIN_VERSION)
        except Exception as e:
            raise NetworkError(e.__class__.__name__) from e
        req_timeout = _aiohttp_timeout_from_value(timeout)
        proxy = _resolve_proxy_for_url(url, proxies)
        req_kwargs: Dict[str, Any] = dict(
            headers=req_headers,
            params=params,
            timeout=req_timeout,
            allow_redirects=False,
        )
        if proxy:
            req_kwargs["proxy"] = proxy
        ssl_ctx = _build_ssl_context(ENFORCE_TLS_MIN, TLS_MIN_VERSION)
        if ssl_ctx is not None:
            req_kwargs["ssl"] = ssl_ctx
        if files is not None:
            _rewind_files(files)
            req_kwargs["data"] = _build_aiohttp_form(data, files)
        else:
            if json is not None:
                req_kwargs["json"] = json
            if data is not None:
                req_kwargs["data"] = data
        async with session.request(method.upper(), url, **req_kwargs) as resp:
            if resp.status >= 400:
                await resp.read()
                raise NetworkError(f"HTTP {resp.status}")
            async for chunk in resp.content.iter_chunked(chunk_size):
                if not chunk:
                    continue
                yield chunk
            _log_outbound_request(
                method=method,
                url=str(getattr(resp, "url", url)),
                status_code=int(resp.status),
                start_time=t0,
                attempt=1,
                last_retry_delay_s=0.0,
            )
    except asyncio.CancelledError:
        raise
    except Exception as e:
        _log_outbound_request(
            method=method,
            url=url,
            status_code=0,
            start_time=t0,
            attempt=1,
            last_retry_delay_s=0.0,
            exception_class=e.__class__.__name__,
        )
        raise NetworkError(e.__class__.__name__) from e


async def astream_bytes(
    *,
    method: str,
    url: str,
    client: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    files: Optional[Any] = None,
    timeout: Optional[Any] = None,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    chunk_size: int = 65536,
    cert_pinning: Optional[Dict[str, set[str]]] = None,
) -> AsyncIterator[bytes]:
    if client is not None:
        if _is_aiohttp_client(client):
            async for chunk in _astream_bytes_aiohttp(
                method=method,
                url=url,
                client=client,
                headers=headers,
                params=params,
                json=json,
                data=data,
                files=files,
                timeout=timeout,
                proxies=proxies,
                chunk_size=chunk_size,
                cert_pinning=cert_pinning,
            ):
                yield chunk
            return
        async for chunk in _astream_bytes_httpx(
            method=method,
            url=url,
            client=client,
            headers=headers,
            params=params,
            json=json,
            data=data,
            files=files,
            timeout=timeout,
            proxies=proxies,
            chunk_size=chunk_size,
            cert_pinning=cert_pinning,
        ):
            yield chunk
        return
    if aiohttp is not None:
        async for chunk in _astream_bytes_aiohttp(
            method=method,
            url=url,
            client=None,
            headers=headers,
            params=params,
            json=json,
            data=data,
            files=files,
            timeout=timeout,
            proxies=proxies,
            chunk_size=chunk_size,
            cert_pinning=cert_pinning,
        ):
            yield chunk
        return
    async for chunk in _astream_bytes_httpx(
        method=method,
        url=url,
        client=None,
        headers=headers,
        params=params,
        json=json,
        data=data,
        files=files,
        timeout=timeout,
        proxies=proxies,
        chunk_size=chunk_size,
        cert_pinning=cert_pinning,
    ):
        yield chunk


async def _astream_sse_httpx(
    *,
    url: str,
    method: str = "GET",
    client: Optional["httpx.AsyncClient"] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    timeout: Optional[Union[float, "httpx.Timeout"]] = None,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    retry: Optional[RetryPolicy] = None,
    cert_pinning: Optional[Dict[str, set[str]]] = None,
) -> AsyncIterator[SSEEvent]:
    hdrs = {"Accept": "text/event-stream"}
    if headers:
        hdrs.update(headers)
    retry = retry or RetryPolicy()
    _validate_egress_or_raise(url)
    _validate_proxies_or_raise(proxies)

    need_close = False
    ac = client
    if ac is None:
        ac = create_async_client(proxies=proxies)
        need_close = True

    attempts = max(1, retry.attempts)
    sleep_s = 0.0
    cur_url = url
    redirects = 0
    t0 = time.time()

    try:
        for attempt in range(1, attempts + 1):
            # manual redirect handling before starting to read body
            while True:
                _validate_egress_or_raise(cur_url)
                try:
                    # Optional cert pinning
                    try:
                        pins_map = cert_pinning or _get_client_cert_pins(ac)
                        if pins_map:
                            u = httpx.URL(cur_url)
                            if u.scheme.lower() == "https":
                                host = (u.host or "").lower()
                                if host in pins_map:
                                    _check_cert_pinning(host, int(u.port or 443), pins_map[host], TLS_MIN_VERSION)
                    except Exception as e:
                        raise NetworkError(e.__class__.__name__) from e

                    async with ac.stream(
                        method.upper(), cur_url, headers=_inject_trace_headers(hdrs), params=params, json=json, data=data, timeout=timeout, follow_redirects=False
                    ) as resp:
                        # Handle redirect response codes before reading any bytes
                        if resp.status_code in (301, 302, 303, 307, 308):
                            if redirects >= DEFAULT_MAX_REDIRECTS:
                                raise NetworkError("Too many redirects")
                            location = resp.headers.get("location")
                            if not location:
                                raise NetworkError("Redirect without Location header")
                            try:
                                next_url = str(resp.request.url.join(httpx.URL(location)))
                            except Exception:
                                try:
                                    next_url = str(httpx.URL(location))
                                except Exception:
                                    raise NetworkError("Invalid redirect Location header")
                            redirects += 1
                            cur_url = next_url
                            continue  # loop to re-validate egress and attempt again
                        # Raise for non-OK statuses pre-body if not retriable
                        if resp.status_code >= 400:
                            should, rsn = _should_retry(method, resp.status_code, None, retry)
                            if not should or attempt == attempts:
                                # escalate as NetworkError; caller handles as appropriate
                                raise NetworkError(f"HTTP {resp.status_code}")
                            # retry with backoff
                            delay = _decorrelated_jitter_sleep(sleep_s, retry.backoff_base_ms, retry.backoff_cap_s)
                            await asyncio.sleep(delay)
                            sleep_s = delay
                            break  # exit redirect loop to outer attempt

                        # Successful response; iterate SSE bytes and yield events
                        buffer = ""
                        async for chunk in resp.aiter_bytes():
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
                        # per-request structured log on successful end of stream
                        _log_outbound_request(
                            method=method,
                            url=resp.request.url,
                            status_code=int(resp.status_code),
                            start_time=t0,
                            attempt=attempt,
                            last_retry_delay_s=sleep_s,
                        )
                        return  # finished streaming without error
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    # network or early error before bytes consumed
                    should, rsn = _should_retry(method, None, NetworkError(str(e)), retry)
                    if not should or attempt == attempts:
                        raise
                    delay = _decorrelated_jitter_sleep(sleep_s, retry.backoff_base_ms, retry.backoff_cap_s)
                    await asyncio.sleep(delay)
                    sleep_s = delay
                    break  # next outer attempt
        # exhausted attempts
        _log_outbound_request(
            method=method,
            url=cur_url,
            status_code=0,
            start_time=t0,
            attempt=attempts,
            last_retry_delay_s=sleep_s,
            exception_class="RetryExhaustedError",
        )
        raise RetryExhaustedError("All retry attempts exhausted (astream_sse)")
    finally:
        if need_close:
            try:
                await ac.aclose()
            except Exception:
                pass


async def _astream_sse_aiohttp(
    *,
    url: str,
    method: str = "GET",
    client: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    files: Optional[Any] = None,
    timeout: Optional[Any] = None,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    retry: Optional[RetryPolicy] = None,
    cert_pinning: Optional[Dict[str, set[str]]] = None,
) -> AsyncIterator[SSEEvent]:
    if aiohttp is None:  # pragma: no cover
        raise RuntimeError("aiohttp is not available")
    hdrs = {"Accept": "text/event-stream"}
    if headers:
        hdrs.update(headers)
    retry = retry or RetryPolicy()
    _validate_egress_or_raise(url)
    _validate_proxies_or_raise(proxies)

    session = client or _get_aiohttp_session()
    attempts = max(1, retry.attempts)
    sleep_s = 0.0
    cur_url = url
    redirects = 0
    t0 = time.time()

    for attempt in range(1, attempts + 1):
        while True:
            _validate_egress_or_raise(cur_url)
            try:
                # Optional cert pinning
                try:
                    pins_map = cert_pinning or _get_client_cert_pins(session)
                    if pins_map:
                        if httpx is not None:
                            u = httpx.URL(cur_url)
                            host = (u.host or "").lower()
                            port = int(u.port or (443 if (u.scheme or "").lower() == "https" else 80))
                        else:
                            parsed = urlparse(cur_url)
                            host = (parsed.hostname or "").lower()
                            port = parsed.port or (443 if (parsed.scheme or "").lower() == "https" else 80)
                        if host in pins_map:
                            _check_cert_pinning(host, port, pins_map[host], TLS_MIN_VERSION)
                except Exception as e:
                    raise NetworkError(e.__class__.__name__) from e

                req_timeout = _aiohttp_timeout_from_value(timeout)
                proxy = _resolve_proxy_for_url(cur_url, proxies)
                req_kwargs: Dict[str, Any] = dict(
                    headers=_inject_trace_headers(hdrs),
                    params=params,
                    timeout=req_timeout,
                    allow_redirects=False,
                )
                if proxy:
                    req_kwargs["proxy"] = proxy
                ssl_ctx = _build_ssl_context(ENFORCE_TLS_MIN, TLS_MIN_VERSION)
                if ssl_ctx is not None:
                    req_kwargs["ssl"] = ssl_ctx
                if files is not None:
                    _rewind_files(files)
                    req_kwargs["data"] = _build_aiohttp_form(data, files)
                else:
                    if json is not None:
                        req_kwargs["json"] = json
                    if data is not None:
                        req_kwargs["data"] = data

                async with session.request(method.upper(), cur_url, **req_kwargs) as resp:
                    if resp.status in (301, 302, 303, 307, 308):
                        if redirects >= DEFAULT_MAX_REDIRECTS:
                            raise NetworkError("Too many redirects")
                        location = resp.headers.get("location")
                        if not location:
                            raise NetworkError("Redirect without Location header")
                        next_url = _resolve_redirect_url(str(resp.url), location)
                        if not next_url:
                            raise NetworkError("Invalid redirect Location header")
                        redirects += 1
                        cur_url = next_url
                        continue

                    if resp.status >= 400:
                        should, rsn = _should_retry(method, resp.status, None, retry)
                        if not should or attempt == attempts:
                            raise NetworkError(f"HTTP {resp.status}")
                        delay = _decorrelated_jitter_sleep(sleep_s, retry.backoff_base_ms, retry.backoff_cap_s)
                        await asyncio.sleep(delay)
                        sleep_s = delay
                        break

                    buffer = ""
                    async for chunk in resp.content.iter_any():
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
                    _log_outbound_request(
                        method=method,
                        url=str(getattr(resp, "url", cur_url)),
                        status_code=int(resp.status),
                        start_time=t0,
                        attempt=attempt,
                        last_retry_delay_s=sleep_s,
                    )
                    return
            except asyncio.CancelledError:
                raise
            except Exception as e:
                should, rsn = _should_retry(method, None, NetworkError(str(e)), retry)
                if not should or attempt == attempts:
                    raise
                delay = _decorrelated_jitter_sleep(sleep_s, retry.backoff_base_ms, retry.backoff_cap_s)
                await asyncio.sleep(delay)
                sleep_s = delay
                break

    _log_outbound_request(
        method=method,
        url=cur_url,
        status_code=0,
        start_time=t0,
        attempt=attempts,
        last_retry_delay_s=sleep_s,
        exception_class="RetryExhaustedError",
    )
    raise RetryExhaustedError("All retry attempts exhausted (astream_sse)")


async def astream_sse(
    *,
    url: str,
    method: str = "GET",
    client: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    timeout: Optional[Any] = None,
    proxies: Optional[Union[str, Dict[str, str]]] = None,
    retry: Optional[RetryPolicy] = None,
    cert_pinning: Optional[Dict[str, set[str]]] = None,
) -> AsyncIterator[SSEEvent]:
    if client is not None:
        if _is_aiohttp_client(client):
            async for event in _astream_sse_aiohttp(
                url=url,
                method=method,
                client=client,
                headers=headers,
                params=params,
                json=json,
                data=data,
                timeout=timeout,
                proxies=proxies,
                retry=retry,
                cert_pinning=cert_pinning,
            ):
                yield event
            return
        async for event in _astream_sse_httpx(
            url=url,
            method=method,
            client=client,
            headers=headers,
            params=params,
            json=json,
            data=data,
            timeout=timeout,
            proxies=proxies,
            retry=retry,
            cert_pinning=cert_pinning,
        ):
            yield event
        return
    if aiohttp is not None:
        async for event in _astream_sse_aiohttp(
            url=url,
            method=method,
            client=None,
            headers=headers,
            params=params,
            json=json,
            data=data,
            timeout=timeout,
            proxies=proxies,
            retry=retry,
            cert_pinning=cert_pinning,
        ):
            yield event
        return
    async for event in _astream_sse_httpx(
        url=url,
        method=method,
        client=None,
        headers=headers,
        params=params,
        json=json,
        data=data,
        timeout=timeout,
        proxies=proxies,
        retry=retry,
        cert_pinning=cert_pinning,
    ):
        yield event


def _parse_sse_event(raw: str) -> Optional[SSEEvent]:
    event = SSEEvent()
    data_lines: list[str] = []
    saw_event = False
    saw_id = False
    saw_retry = False
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
            saw_event = True
        elif field == "data":
            data_lines.append(val)
        elif field == "id":
            event.id = val
            saw_id = True
        elif field == "retry":
            try:
                event.retry = int(val)
                saw_retry = True
            except Exception:
                pass
    event.data = "\n".join(data_lines)
    if not data_lines and not saw_event and not saw_id and not saw_retry:
        return None
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
    cert_pinning: Optional[Dict[str, set[str]]] = None,
    # Optional safety checks
    max_bytes_total: Optional[int] = None,
    require_content_type: Optional[str] = None,
) -> Path:
    if httpx is None:  # pragma: no cover
        raise RuntimeError("httpx is not available")
    _validate_egress_or_raise(url)
    _validate_proxies_or_raise(proxies)
    t0 = time.time()
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
            # Enforce disk quota if resuming
            if max_bytes_total is not None and existing > max_bytes_total:
                raise DownloadError("Disk quota exceeded before download")

            last_exc: Optional[Exception] = None
            try:
                # Optional cert pinning
                try:
                    pins_map = cert_pinning or _get_client_cert_pins(sc)
                    if pins_map:
                        u = httpx.URL(url)
                        if u.scheme.lower() == "https":
                            host = (u.host or "").lower()
                            if host in pins_map:
                                _check_cert_pinning(host, int(u.port or 443), pins_map[host], TLS_MIN_VERSION)
                except Exception as e:
                    raise DownloadError(str(e))
                with sc.stream("GET", url, headers=req_headers, params=params, timeout=timeout) as resp:
                    if resp.status_code in (200, 206):
                        # Optional content-type enforcement
                        if require_content_type:
                            ctype = (resp.headers.get("content-type") or "").lower()
                            if require_content_type.lower() not in ctype:
                                raise DownloadError("Unexpected Content-Type")
                        hasher = hashlib.new(checksum_alg) if checksum else None
                        mode = "ab" if (resume and existing > 0 and resp.status_code == 206) else "wb"
                        with open(tmp_path, mode) as f:
                            written = existing if (resume and mode == "ab") else 0
                            for chunk in resp.iter_bytes():
                                if not chunk:
                                    continue
                                if max_bytes_total is not None:
                                    if written + len(chunk) > max_bytes_total:
                                        raise DownloadError("Disk quota exceeded")
                                f.write(chunk)
                                if hasher is not None:
                                    hasher.update(chunk)
                                written += len(chunk)
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
                        # per-request structured log
                        _log_outbound_request(
                            method="GET",
                            url=resp.request.url if hasattr(resp.request, "url") else url,
                            status_code=int(resp.status_code),
                            start_time=t0,
                            attempt=attempt,
                            last_retry_delay_s=sleep_s,
                        )
                        return dest_path
                    else:
                        should, rsn = _should_retry("GET", resp.status_code, None, retry)
                        if not should or attempt == attempts:
                            # terminal error response
                            _log_outbound_request(
                                method="GET",
                                url=resp.request.url if hasattr(resp.request, "url") else url,
                                status_code=int(resp.status_code),
                                start_time=t0,
                                attempt=attempt,
                                last_retry_delay_s=sleep_s,
                            )
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
                    # terminal network error
                    _log_outbound_request(
                        method="GET",
                        url=url,
                        status_code=0,
                        start_time=t0,
                        attempt=attempt,
                        last_retry_delay_s=sleep_s,
                        exception_class=(last_exc.__class__.__name__ if last_exc else "DownloadError"),
                    )
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
        _log_outbound_request(
            method="GET",
            url=url,
            status_code=0,
            start_time=t0,
            attempt=attempts,
            last_retry_delay_s=sleep_s,
            exception_class="RetryExhaustedError",
        )
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
    cert_pinning: Optional[Dict[str, set[str]]] = None,
    max_bytes_total: Optional[int] = None,
    require_content_type: Optional[str] = None,
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
        cert_pinning=cert_pinning,
        max_bytes_total=max_bytes_total,
        require_content_type=require_content_type,
    )


__all__ = [
    "HttpResponse",
    "RetryPolicy",
    "SSEEvent",
    "build_limits",
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
    "shutdown_http_client",
]
