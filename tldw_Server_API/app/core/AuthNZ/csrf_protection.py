# csrf_protection.py
# Description: CSRF protection middleware for FastAPI
#
# Imports
import secrets
import hashlib
from typing import Optional, Set, Callable
import hmac
import base64
from datetime import datetime, timedelta
#
# 3rd-party imports
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger
#
# Local imports
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import derive_hmac_key
from tldw_Server_API.app.core.config import settings as global_settings

#######################################################################################################################
#
# CSRF Token Manager

class CSRFTokenManager:
    """Manages CSRF tokens for session protection"""

    def __init__(self):
        """Initialize CSRF token manager"""
        self.settings = get_settings()
        self.token_header_name = "X-CSRF-Token"
        self.token_cookie_name = "csrf_token"
        self.token_length = 32

        # Methods that require CSRF protection
        self.protected_methods = {"POST", "PUT", "PATCH", "DELETE"}

        # Paths to exclude from CSRF protection
        self.excluded_paths = {
            "/api/v1/auth/login",  # Login needs to work without existing token
            "/api/v1/auth/refresh",  # Token refresh
            "/api/v1/health",  # Health checks
            "/docs",  # API documentation
            "/openapi.json",  # OpenAPI schema
            "/redoc",  # ReDoc documentation
        }

        # Content types that require CSRF protection
        self.protected_content_types = {
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
            "text/plain",
        }

    def _hmac_key(self) -> bytes:
        # Use shared derivation to avoid drift
        return derive_hmac_key(get_settings())

    def _bind_suffix(self, user_id: Optional[int]) -> Optional[str]:
        """Return HMAC suffix for user binding if enabled and user_id provided."""
        s = get_settings()
        if not s.CSRF_BIND_TO_USER or user_id is None:
            return None
        digest = hmac.new(self._hmac_key(), str(user_id).encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest)[:16].decode()

    def generate_token(self, request: Request) -> str:
        """Generate a new CSRF token"""
        base = secrets.token_urlsafe(self.token_length)
        try:
            uid = getattr(request.state, 'user_id', None)
        except Exception:
            uid = None
        suffix = self._bind_suffix(uid)
        return f"{base}.{suffix}" if suffix else base

    def hash_token(self, token: str) -> str:
        """Create a hash of the token for comparison"""
        return hashlib.sha256(token.encode()).hexdigest()

    def validate_token(self, cookie_token: str, header_token: str, user_id: Optional[int] = None) -> bool:
        """
        Validate CSRF token using double-submit cookie pattern

        Args:
            cookie_token: Token from cookie
            header_token: Token from header

        Returns:
            True if tokens match and are valid
        """
        if not cookie_token or not header_token:
            return False

        # Constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(cookie_token, header_token):
            return False
        # If token includes binding suffix, validate it
        parts = cookie_token.split('.')
        if len(parts) == 2 and get_settings().CSRF_BIND_TO_USER:
            suffix = parts[1]
            if not suffix or user_id is None:
                return False
            expected = self._bind_suffix(user_id)
            return secrets.compare_digest(suffix, expected)
        return True

    def should_protect(self, request: Request) -> bool:
        """
        Determine if request should be protected by CSRF

        Args:
            request: The incoming request

        Returns:
            True if CSRF protection should be applied
        """
        # Skip if not a protected method
        if request.method not in self.protected_methods:
            return False

        # Skip if path is excluded
        path = str(request.url.path)
        if any(path.startswith(excluded) for excluded in self.excluded_paths):
            return False

        # Skip if single-user mode with API key auth (X-API-KEY or Bearer fallback)
        if self.settings.AUTH_MODE == "single_user":
            # Check if API key is present
            api_key = request.headers.get("X-API-KEY")
            if api_key:
                return False  # API key auth doesn't need CSRF
            authorization = request.headers.get("authorization") or request.headers.get("Authorization")
            if authorization:
                scheme, _, credential = authorization.partition(" ")
                if scheme.lower() == "bearer" and credential.strip():
                    return False

        # Check content type
        content_type = request.headers.get("content-type", "").lower()
        if content_type:
            # Extract base content type (remove charset, etc.)
            content_type = content_type.split(";")[0].strip()

            # Skip if not a protected content type
            if not any(ct in content_type for ct in self.protected_content_types):
                return False

        return True

    def set_cookie(self, response: Response, token: str):
        """
        Set CSRF token cookie

        Args:
            response: Response to add cookie to
            token: CSRF token to set
        """
        response.set_cookie(
            key=self.token_cookie_name,
            value=token,
            max_age=3600 * 24,  # 24 hours
            httponly=False,  # Must be readable by JavaScript
            secure=self.settings.SESSION_COOKIE_SECURE,
            samesite=self.settings.SESSION_COOKIE_SAMESITE,
            path="/"
        )


#######################################################################################################################
#
# CSRF Protection Middleware

class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    CSRF Protection Middleware using double-submit cookie pattern

    This middleware implements CSRF protection by:
    1. Setting a CSRF token cookie on responses
    2. Requiring the token to be submitted in a header for protected requests
    3. Validating that the header token matches the cookie token
    """

    def __init__(self, app, enabled: bool = True):
        """
        Initialize CSRF protection middleware

        Args:
            app: FastAPI application
            enabled: Whether CSRF protection is enabled
        """
        super().__init__(app)
        self.enabled = enabled
        self.token_manager = CSRFTokenManager()
        logger.info(f"CSRF Protection Middleware initialized (enabled={enabled})")

    async def _resolve_user_id(self, request: Request) -> Optional[int]:
        """Resolve user identifier prior to dependency execution when binding required."""
        try:
            existing = getattr(request.state, "user_id", None)
            if isinstance(existing, int):
                return existing
        except Exception:
            existing = None
        # Attempt to decode Authorization bearer token
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            if token:
                try:
                    from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
                    payload = get_jwt_service().decode_access_token(token)
                    user_id = payload.get("user_id") or payload.get("sub")
                    if isinstance(user_id, str):
                        user_id = int(user_id)
                    if isinstance(user_id, int):
                        try:
                            request.state.user_id = user_id
                        except Exception:
                            pass
                        return user_id
                except Exception as exc:
                    logger.debug(f"CSRF binding: bearer token decode failed: {exc}")
        # Attempt API key lookup
        api_key = request.headers.get("X-API-KEY")
        if api_key:
            try:
                from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
                manager = await get_api_key_manager()
                info = await manager.validate_api_key(
                    api_key=api_key,
                    ip_address=request.client.host if request.client else None
                )
                user_id = info.get("user_id") if info else None
                if isinstance(user_id, int):
                    try:
                        request.state.user_id = user_id
                    except Exception:
                        pass
                    return user_id
            except Exception as exc:
                logger.debug(f"CSRF binding: API key resolution failed: {exc}")
        return None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with CSRF protection

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response with CSRF token cookie if needed
        """
        # Check runtime setting to allow test overrides
        # Use global settings which tests can modify
        runtime_csrf_enabled = global_settings.get('CSRF_ENABLED', None)

        # If CSRF_ENABLED is explicitly False, bypass protection
        if runtime_csrf_enabled is False or not self.enabled:
            return await call_next(request)

        # Check if this request needs CSRF protection
        if self.token_manager.should_protect(request):
            if get_settings().CSRF_BIND_TO_USER:
                user_id = await self._resolve_user_id(request)
            else:
                try:
                    user_id = getattr(request.state, 'user_id', None)
                except Exception:
                    user_id = None
            # Get tokens
            cookie_token = request.cookies.get(self.token_manager.token_cookie_name)
            header_token = request.headers.get(self.token_manager.token_header_name)

            # Validate tokens
            if not self.token_manager.validate_token(cookie_token, header_token, user_id):
                logger.warning(
                    f"CSRF token validation failed for {request.method} {request.url.path} "
                    f"from {request.client.host if request.client else 'unknown'}"
                )

                # Return 403 Forbidden
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF token validation failed"}
                )

        # Process request
        response = await call_next(request)

        # Set CSRF token cookie if not present
        if self.token_manager.token_cookie_name not in request.cookies:
            token = self.token_manager.generate_token(request)
            self.token_manager.set_cookie(response, token)

            # Also add token to response header for easy access
            response.headers[self.token_manager.token_header_name] = token

        return response


#######################################################################################################################
#
# Helper Functions

def get_csrf_token(request: Request) -> Optional[str]:
    """
    Get CSRF token from request cookie

    Args:
        request: FastAPI request

    Returns:
        CSRF token if present, None otherwise
    """
    return request.cookies.get("csrf_token")


def validate_csrf_token(request: Request) -> bool:
    """
    Validate CSRF token in request

    Args:
        request: FastAPI request

    Returns:
        True if CSRF token is valid

    Raises:
        HTTPException: If CSRF validation fails
    """
    manager = CSRFTokenManager()

    if manager.should_protect(request):
        # Resolve user_id when CSRF binding is enabled to validate suffix binding
        user_id = None
        try:
            user_id = getattr(request.state, 'user_id', None)
        except Exception:
            user_id = None

        # Lightweight bearer decode path (sync) to enrich user_id when possible
        try:
            if user_id is None and get_settings().CSRF_BIND_TO_USER:
                auth_header = request.headers.get("authorization")
                if auth_header and auth_header.lower().startswith("bearer "):
                    token = auth_header.split(" ", 1)[1].strip()
                    if token:
                        from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
                        payload = get_jwt_service().decode_access_token(token)
                        uid = payload.get("user_id") or payload.get("sub")
                        if isinstance(uid, str):
                            try:
                                uid = int(uid)
                            except Exception:
                                uid = None
                        if isinstance(uid, int):
                            user_id = uid
        except Exception:
            # Best-effort enrichment; fall back to no user binding if unavailable
            pass

        cookie_token = request.cookies.get(manager.token_cookie_name)
        header_token = request.headers.get(manager.token_header_name)

        if not manager.validate_token(cookie_token, header_token, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token validation failed"
            )

    return True


#######################################################################################################################
#
# FastAPI Integration

def add_csrf_protection(app):
    """
    Add CSRF protection middleware to FastAPI app

    Args:
        app: FastAPI application instance
    """
    settings = get_settings()

    # Check both AUTH_MODE and CSRF_ENABLED setting
    # CSRF_ENABLED can override the default behavior for testing
    csrf_enabled = global_settings.get('CSRF_ENABLED', None)
    # In test mode, default to disabled unless explicitly enabled in settings
    try:
        import os as _os, sys as _sys
        if csrf_enabled is None and (
            _os.getenv("TEST_MODE", "").strip().lower() in {"1", "true", "yes"}
            or "pytest" in _sys.modules
        ):
            csrf_enabled = False
    except Exception:
        pass

    if csrf_enabled is False:
        # Explicitly disabled (e.g., for testing)
        logger.info("CSRF Protection explicitly disabled via CSRF_ENABLED setting")
        app.add_middleware(
            CSRFProtectionMiddleware,
            enabled=False
        )
    elif settings.AUTH_MODE == "multi_user" or csrf_enabled is True:
        # Enable for multi-user mode or if explicitly enabled
        app.add_middleware(
            CSRFProtectionMiddleware,
            enabled=True
        )
        logger.info("CSRF Protection enabled")
    else:
        # Single-user mode and not explicitly enabled
        app.add_middleware(
            CSRFProtectionMiddleware,
            enabled=False
        )
        logger.info("CSRF Protection disabled for single-user mode")


#
# End of csrf_protection.py
#######################################################################################################################
