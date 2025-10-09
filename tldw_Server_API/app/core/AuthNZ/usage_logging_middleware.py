from __future__ import annotations

import json
from time import monotonic
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from loguru import logger

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
        self._settings = get_settings()

    def _is_excluded(self, path: str) -> bool:
        try:
            for prefix in (self._settings.USAGE_LOG_EXCLUDE_PREFIXES or []):
                if path.startswith(prefix):
                    return True
        except Exception:
            pass
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not getattr(self._settings, "USAGE_LOG_ENABLED", False):
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
                if response is not None:
                    cl = response.headers.get("content-length")
                    if cl and cl.isdigit():
                        bytes_out = int(cl)
                ip = request.client.host if request.client else "unknown"
                ua = request.headers.get("user-agent", "")
                meta = json.dumps({"ip": ip, "ua": ua})

                # Insert row into usage_log (SQLite or Postgres)
                db_pool: DatabasePool = await get_db_pool()
                if db_pool.pool:
                    # PostgreSQL
                    query = (
                        "INSERT INTO usage_log (user_id, key_id, endpoint, status, latency_ms, bytes, meta) "
                        "VALUES ($1, $2, $3, $4, $5, $6, $7)"
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
                    )
                else:
                    # SQLite ('?' parameters)
                    query = (
                        "INSERT INTO usage_log (user_id, key_id, endpoint, status, latency_ms, bytes, meta) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)"
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
                    )
            except Exception as e:
                # Never fail request due to logging
                logger.debug(f"Usage logging skipped/failed: {e}")

