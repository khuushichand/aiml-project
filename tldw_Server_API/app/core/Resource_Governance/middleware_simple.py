from __future__ import annotations

"""
Minimal ASGI middleware that derives a policy_id from route tags or path and
calls the Resource Governor before and after handlers.

This is a thin adapter for Stage 1/2 validation and can be replaced by a
full-featured middleware later.
"""

import os
import re
import uuid
from typing import Any, Callable, Awaitable, Optional

from loguru import logger
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import JSONResponse

from .governor import RGRequest
from .deps import derive_entity_key


class RGSimpleMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        # Compile simple path matchers from stub mapping
        self._compiled_map: list[tuple[re.Pattern[str], str]] = []

    def _init_route_map(self, request: Request) -> None:
        try:
            loader = getattr(request.app.state, "rg_policy_loader", None)
            if not loader:
                return
            snap = loader.get_snapshot()
            route_map = getattr(snap, "route_map", {}) or {}
            by_path = dict(route_map.get("by_path") or {})
            compiled = []
            for pat, pol in by_path.items():
                # Convert simple "/api/v1/chat/*" to regex
                pat = str(pat)
                if pat.endswith("*"):
                    regex = re.escape(pat[:-1]) + ".*"
                else:
                    regex = re.escape(pat) + "$"
                compiled.append((re.compile(regex), str(pol)))
            self._compiled_map = compiled
        except Exception as e:
            logger.debug(f"RGSimpleMiddleware: route_map init skipped: {e}")

    def _derive_policy_id(self, request: Request) -> Optional[str]:
        # Prefer path-based routing (works even before route resolution)
        try:
            loader = getattr(request.app.state, "rg_policy_loader", None)
            snap = loader.get_snapshot() if loader else None
            route_map = getattr(snap, "route_map", {}) or {}
            by_path = dict(route_map.get("by_path") or {})
            path = request.url.path or "/"
            # Simple wildcard matching: prefix* → startswith(prefix), else exact
            for pat, pol in by_path.items():
                pat = str(pat)
                if pat.endswith("*"):
                    if path.startswith(pat[:-1]):
                        return str(pol)
                else:
                    if path == pat:
                        return str(pol)
        except Exception:
            pass

        # Fallback to tag-based routing (may not be available early in ASGI pipeline)
        try:
            by_tag = dict((route_map or {}).get("by_tag") or {})  # type: ignore[name-defined]
        except Exception:
            by_tag = {}
        try:
            route = request.scope.get("route")
            tags = list(getattr(route, "tags", []) or [])
            for t in tags:
                if t in by_tag:
                    return str(by_tag[t])
        except Exception:
            pass
        return None

    @staticmethod
    def _derive_entity(request: Request) -> str:
        return derive_entity_key(request)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        # If governor not initialized, pass through
        gov = getattr(request.app.state, "rg_governor", None)
        if gov is None:
            await self.app(scope, receive, send)
            return

        policy_id = self._derive_policy_id(request)
        if not policy_id:
            await self.app(scope, receive, send)
            return

        # Build RG request for 'requests' category
        entity = self._derive_entity(request)
        op_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        rg_req = RGRequest(entity=entity, categories={"requests": {"units": 1}}, tags={"policy_id": policy_id, "endpoint": request.url.path})

        try:
            decision, handle_id = await gov.reserve(rg_req, op_id=op_id)
        except Exception as e:
            logger.debug(f"RGSimpleMiddleware reserve error: {e}")
            await self.app(scope, receive, send)
            return

        if not decision.allowed:
            retry_after = int(decision.retry_after or 1)
            # Map basic rate-limit headers for compatibility
            # Extract per-category details if available
            categories = {}
            try:
                categories = dict((decision.details or {}).get("categories") or {})
            except Exception:
                categories = {}
            req_cat = categories.get("requests") or {}
            limit = int(req_cat.get("limit") or 0)

            resp = JSONResponse({
                "error": "rate_limited",
                "policy_id": policy_id,
                "retry_after": retry_after,
            }, status_code=429)
            resp.headers["Retry-After"] = str(retry_after)
            if limit:
                resp.headers["X-RateLimit-Limit"] = str(limit)
            resp.headers["X-RateLimit-Remaining"] = "0"
            resp.headers["X-RateLimit-Reset"] = str(retry_after)
            await resp(scope, receive, send)
            return

        # Allowed; run handler with header injection wrapper and then commit in finally
        # Prepare success-path rate-limit headers (using precise peek when available)
        try:
            _cats = dict((decision.details or {}).get("categories") or {})
        except Exception:
            _cats = {}
        _req_cat = _cats.get("requests") or {}
        _limit = int(_req_cat.get("limit") or 0)
        # Determine categories to peek for precise Remaining/Reset
        _categories_to_peek = list(_cats.keys()) or ["requests"]

        async def _send_wrapped(message):
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers") or [])
                try:
                    # Try to get accurate remaining/reset via governor.peek
                    peek = getattr(gov, "peek_with_policy", None)
                    peek_result = None
                    if callable(peek):
                        try:
                            peek_result = await peek(entity, _categories_to_peek, policy_id)
                        except Exception:
                            peek_result = None
                    # requests headers (compat)
                    if _limit:
                        headers.append((b"x-ratelimit-limit", str(_limit).encode()))
                    req_remaining = None
                    req_reset = None
                    if isinstance(peek_result, dict):
                        rinfo = peek_result.get("requests") or {}
                        if rinfo.get("remaining") is not None:
                            req_remaining = int(rinfo.get("remaining"))
                        if rinfo.get("reset") is not None:
                            req_reset = int(rinfo.get("reset"))
                    if req_remaining is None and _limit:
                        req_remaining = max(0, _limit - 1)
                    if req_reset is None:
                        req_reset = 0
                    if _limit:
                        headers.append((b"x-ratelimit-remaining", str(req_remaining).encode()))
                        headers.append((b"x-ratelimit-reset", str(req_reset).encode()))

                    # If additional categories are present (e.g., tokens), set namespaced headers
                    if isinstance(peek_result, dict):
                        # Compute overall reset as max across categories for compatibility
                        try:
                            resets = [int((peek_result.get(c) or {}).get("reset") or 0) for c in _categories_to_peek]
                            overall_reset = max(resets) if resets else req_reset
                            if overall_reset is not None and overall_reset > req_reset and _limit:
                                # override generic reset with stricter value
                                headers = [(k, v) for (k, v) in headers if k != b"x-ratelimit-reset"]
                                headers.append((b"x-ratelimit-reset", str(overall_reset).encode()))
                        except Exception:
                            pass
                        # Tokens headers (if present)
                        tinfo = peek_result.get("tokens") or {}
                        if tinfo.get("remaining") is not None:
                            headers.append((b"x-ratelimit-tokens-remaining", str(int(tinfo.get("remaining") or 0)).encode()))
                        # If we later enforce tokens category, expose per-minute headers too when policy defines per_min
                        try:
                            loader = getattr(request.app.state, "rg_policy_loader", None)
                            if loader is not None:
                                pol = loader.get_policy(policy_id) or {}
                                per_min = int((pol.get("tokens") or {}).get("per_min") or 0)
                                if per_min > 0 and tinfo:
                                    headers.append((b"x-ratelimit-perminute-limit", str(per_min).encode()))
                                    if tinfo.get("remaining") is not None:
                                        headers.append((b"x-ratelimit-perminute-remaining", str(int(tinfo.get("remaining") or 0)).encode()))
                        except Exception:
                            # best-effort only
                            pass
                except Exception:
                    pass
                message = {**message, "headers": headers}
            await send(message)

        response = None
        try:
            response = await self.app(scope, receive, _send_wrapped)
        finally:
            try:
                if handle_id:
                    await gov.commit(handle_id, actuals=None)
            except Exception as e:
                logger.debug(f"RGSimpleMiddleware commit error: {e}")

        return response
