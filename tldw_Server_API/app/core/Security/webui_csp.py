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


def _build_webui_csp(nonce: str, *, allow_inline_scripts: bool, allow_eval: bool) -> str:
    """Build CSP for WebUI.

    - For /webui we drop 'unsafe-inline' for scripts by default (migrated tabs use modules/bindings).
    - For /setup we keep inline scripts allowed as the setup flow still uses inline helpers.
    - Set env TLDW_WEBUI_NO_EVAL=1 to drop 'unsafe-eval' once migrated tabs avoid eval.
    """
    script_parts = ["'self'"]
    if allow_inline_scripts:
        script_parts.append("'unsafe-inline'")
    if allow_eval:
        script_parts.append("'unsafe-eval'")
    policy = (
        "default-src 'self'; "
        + f"script-src {' '.join(script_parts)}; "
        + "style-src 'self' 'unsafe-inline'; "
        + "img-src 'self' data: blob: https:; "
        + "font-src 'self' data:; "
        + "media-src 'self' data: blob:; "
        + "connect-src 'self' http: https: ws: wss:; "
        + "frame-ancestors 'none'; "
        + "base-uri 'self'; "
        + "form-action 'self'; "
        + "upgrade-insecure-requests"
    )
    return policy


class WebUICSPMiddleware(BaseHTTPMiddleware):
    """Add CSP headers for /webui and /setup without rewriting response bodies.

    We keep a relaxed CSP suitable for the legacy static WebUI by allowing
    'unsafe-inline' and 'unsafe-eval'. We avoid injecting nonces into HTML
    to prevent interfering with streaming/static responses and Content-Length.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path or ""
        if not (path.startswith("/webui") or path.startswith("/setup")):
            return await call_next(request)

        # Generate a nonce to future-proof policy customization; store on state
        nonce = _gen_nonce()
        try:
            setattr(request.state, "csp_nonce", nonce)
        except Exception:
            pass

        response = await call_next(request)
        try:
            # Web UI CSP policy
            # - /setup: keep permissive (inline + eval) as gating protects access
            # - /webui: by default in production, DISALLOW inline handlers; allow eval based on env
            if path.startswith("/setup"):
                allow_inline_scripts = True
                allow_eval = True
            else:
                # /webui: always disallow inline script handlers in script-src
                # Tests assert that /webui never includes 'unsafe-inline' in script-src
                allow_inline_scripts = False

                # Eval policy precedence (simplified and explicit):
                # 1) Compute production flag once from env.
                env = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or os.getenv("ENV") or "dev").lower()
                prod_flag = env in {"prod", "production"}
                # 2) Respect TLDW_WEBUI_NO_EVAL first if present; otherwise default by prod flag.
                no_eval_env = os.getenv("TLDW_WEBUI_NO_EVAL")
                if no_eval_env is not None:
                    truthy = no_eval_env.strip().lower() in {"1", "true", "yes", "on", "y"}
                    allow_eval = not truthy
                else:
                    allow_eval = False if prod_flag else True
            response.headers.setdefault(
                "Content-Security-Policy",
                _build_webui_csp(nonce, allow_inline_scripts=allow_inline_scripts, allow_eval=allow_eval),
            )
        except Exception:
            # Best-effort header set; return original response
            pass
        return response


__all__ = ["WebUICSPMiddleware"]
