from __future__ import annotations

import json
from time import monotonic
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from loguru import logger
import hmac
import hashlib

from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, DatabasePool


class UsageLoggingMiddleware(BaseHTTPMiddleware):
    """
    Lightweight per-request usage logger.

    Writes to AuthNZ.usage_log when USAGE_LOG_ENABLED is true. Designed to be
    low-risk: failures to write never impact request handling.
    """

    def __init__(self, app):
        super().__init__(app)

    def _is_excluded(self, path: str) -> bool:
        try:
            settings = get_settings()
            for prefix in (getattr(settings, "USAGE_LOG_EXCLUDE_PREFIXES", []) or []):
                if path.startswith(prefix):
                    return True
        except Exception:
            pass
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Evaluate settings at request time to honor test env changes
        settings = get_settings()
        if not getattr(settings, "USAGE_LOG_ENABLED", False):
            return await call_next(request)

        path = request.url.path
        if self._is_excluded(path):
            return await call_next(request)

        start = monotonic()
        response: Optional[Response] = None
        status_code = 0
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            try:
                duration_ms = int((monotonic() - start) * 1000)
                user_id = getattr(request.state, "user_id", None)
                api_key_id = getattr(request.state, "api_key_id", None)
                endpoint = f"{request.method}:{path}"
                bytes_out = None
                bytes_in = None
                if response is not None:
                    cl = response.headers.get("content-length")
                    if cl and cl.isdigit():
                        bytes_out = int(cl)
                try:
                    cl_in = request.headers.get("content-length")
                    if cl_in and cl_in.isdigit():
                        bytes_in = int(cl_in)
                except Exception:
                    bytes_in = None
                # Meta (IP/User-Agent) handling, with optional hashing for PII
                try:
                    if getattr(settings, "USAGE_LOG_DISABLE_META", False):
                        meta = "{}"
                    else:
                        ip = request.client.host if request.client else "unknown"
                        ua = request.headers.get("user-agent", "")
                        if getattr(settings, "PII_REDACT_LOGS", False):
                            # Replace raw IP with a salted HMAC for anomaly detection without PII retention
                            salt = getattr(settings, "API_KEY_PEPPER", None) or getattr(settings, "JWT_SECRET_KEY", None)
                            if salt and ip and ip != "unknown":
                                try:
                                    digest = hmac.new(str(salt).encode("utf-8"), str(ip).encode("utf-8"), hashlib.sha256).hexdigest()
                                    ip = f"hash:{digest[:16]}"
                                except Exception:
                                    ip = "redacted"
                            else:
                                ip = "redacted"
                            ua = ""
                        meta = json.dumps({"ip": ip, "ua": ua})
                except Exception:
                    meta = "{}"

                # Insert row into usage_log (SQLite or Postgres)
                db_pool: DatabasePool = await get_db_pool()
                # Request ID propagation
                request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")

                if db_pool.pool:
                    # PostgreSQL
                    try:
                        query = (
                            "INSERT INTO usage_log (user_id, key_id, endpoint, status, latency_ms, bytes, bytes_in, meta, request_id) "
                            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)"
                        )
                        await db_pool.execute(
                            query,
                            user_id,
                            api_key_id,
                            endpoint,
                            int(status_code),
                            int(duration_ms),
                            int(bytes_out) if bytes_out is not None else None,
                            int(bytes_in) if bytes_in is not None else None,
                            meta,
                            request_id,
                        )
                    except Exception:
                        # Fallback to legacy schema without bytes_in
                        query = (
                            "INSERT INTO usage_log (user_id, key_id, endpoint, status, latency_ms, bytes, meta, request_id) "
                            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
                        )
                        await db_pool.execute(
                            query,
                            user_id,
                            api_key_id,
                            endpoint,
                            int(status_code),
                            int(duration_ms),
                            int(bytes_out) if bytes_out is not None else None,
                            meta,
                            request_id,
                        )
                else:
                    # SQLite ('?' parameters)
                    try:
                        query = (
                            "INSERT INTO usage_log (user_id, key_id, endpoint, status, latency_ms, bytes, bytes_in, meta, request_id) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                        )
                        await db_pool.execute(
                            query,
                            user_id,
                            api_key_id,
                            endpoint,
                            int(status_code),
                            int(duration_ms),
                            int(bytes_out) if bytes_out is not None else None,
                            int(bytes_in) if bytes_in is not None else None,
                            meta,
                            request_id,
                        )
                    except Exception:
                        query = (
                            "INSERT INTO usage_log (user_id, key_id, endpoint, status, latency_ms, bytes, meta, request_id) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                        )
                        await db_pool.execute(
                            query,
                            user_id,
                            api_key_id,
                            endpoint,
                            int(status_code),
                            int(duration_ms),
                            int(bytes_out) if bytes_out is not None else None,
                            meta,
                            request_id,
                        )
            except Exception as e:
                # Never fail request due to logging
                logger.debug(f"Usage logging skipped/failed: {e}")
