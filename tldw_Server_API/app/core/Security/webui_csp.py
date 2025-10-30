from __future__ import annotations

import base64
import os
import re
from typing import Callable

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


_SCRIPT_TAG_RE = re.compile(rb"<script(\s[^>]*)?>", re.IGNORECASE)


def _gen_nonce() -> str:
    # 128-bit random, URL-safe base64 without padding
    raw = os.urandom(16)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _inject_nonce_into_html(html: bytes, nonce: str) -> bytes:
    # Insert nonce attribute into every <script ...> tag
    nonce_attr = f' nonce="{nonce}"'.encode("utf-8")

    def _repl(match: re.Match[bytes]) -> bytes:
        tag = match.group(0)
        # If nonce already present, leave as-is
        if b" nonce=" in tag:
            return tag
        # Insert just before closing '>' of the opening tag
        if tag.endswith(b">"):
            return tag[:-1] + nonce_attr + b">"
        return tag + nonce_attr

    try:
        return _SCRIPT_TAG_RE.sub(_repl, html)
    except Exception as exc:
        logger.debug(f"Nonce injection regex failed: {exc}")
        return html


def _build_webui_csp(nonce: str) -> str:
    # Provide a restrictive CSP with script nonces for /webui.
    # Keep 'unsafe-eval' for legacy helpers; consider removing once JS is refactored.
    return (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}' 'strict-dynamic' 'unsafe-eval'; "
        f"script-src-elem 'nonce-{nonce}'; "
        "script-src-attr 'none'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "media-src 'self' data: blob:; "
        "connect-src 'self' ws: wss:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "upgrade-insecure-requests"
    )


class WebUICSPMiddleware(BaseHTTPMiddleware):
    """Adds a per-request CSP nonce for /webui and injects it into HTML script tags.

    This allows inline script blocks in legacy static HTML to execute without
    using 'unsafe-inline', while keeping a strict CSP elsewhere.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path or ""
        # Only apply to WebUI paths
        if not path.startswith("/webui"):
            return await call_next(request)

        # Generate and attach nonce to request state for downstream use
        nonce = _gen_nonce()
        try:
            setattr(request.state, "csp_nonce", nonce)
        except Exception:
            pass

        response = await call_next(request)

        # If the response is HTML, inject nonce into script tags
        content_type = (response.headers.get("content-type") or "").lower()
        is_html = content_type.startswith("text/html") or path.endswith(".html")
        if is_html:
            try:
                body_bytes = b""
                async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                    body_bytes += chunk
                new_body = _inject_nonce_into_html(body_bytes, nonce)
                # Copy headers and set CSP with nonce
                headers = dict(response.headers)
                headers["Content-Security-Policy"] = _build_webui_csp(nonce)
                new_resp = Response(
                    content=new_body,
                    status_code=response.status_code,
                    headers=headers,
                    media_type=response.media_type or "text/html; charset=utf-8",
                    background=response.background,
                )
                return new_resp
            except Exception as exc:
                logger.debug(f"Failed nonce injection for {path}: {exc}")
                # Ensure at least a CSP header is present even if we failed to inject
                response.headers.setdefault("Content-Security-Policy", _build_webui_csp(nonce))
                return response

        # Non-HTML assets under /webui: just add CSP with nonce so any inline
        # scripts executed by DOM insertion can be nonced.
        response.headers.setdefault("Content-Security-Policy", _build_webui_csp(nonce))
        return response


__all__ = ["WebUICSPMiddleware"]
