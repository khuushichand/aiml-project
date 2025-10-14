"""Backwards-compatible re-export of the hardened security headers middleware."""

from tldw_Server_API.app.core.Security.middleware import (
    SecurityHeadersMiddleware,
    create_security_headers_middleware,
)

__all__ = ["SecurityHeadersMiddleware", "create_security_headers_middleware"]
