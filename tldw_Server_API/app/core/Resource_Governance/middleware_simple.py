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

    @staticmethod
    def _derive_policy_id(request: Request) -> Optional[str]:
        # 1) From route tags via by_tag map
        try:
            loader = getattr(request.app.state, "rg_policy_loader", None)
            if loader is not None:
                snap = loader.get_snapshot()
                route_map = getattr(snap, "route_map", {}) or {}
                by_tag = dict(route_map.get("by_tag") or {})
            else:
                by_tag = {}
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

        # 2) From path via by_path rules
        try:
            path = request.url.path or "/"
            # init compiled map on first use
            if not self._compiled_map:
                self._init_route_map(request)
            for regex, pol in self._compiled_map:
                if regex.match(path):
                    return pol
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
            resp = JSONResponse({
                "error": "rate_limited",
                "policy_id": policy_id,
                "retry_after": retry_after,
            }, status_code=429)
            resp.headers["Retry-After"] = str(retry_after)
            await resp(scope, receive, send)
            return

        # Allowed; run handler and then commit in finally
        response = None
        try:
            response = await self.app(scope, receive, send)
        finally:
            try:
                if handle_id:
                    await gov.commit(handle_id, actuals=None)
            except Exception as e:
                logger.debug(f"RGSimpleMiddleware commit error: {e}")

        return response
