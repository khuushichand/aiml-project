"""
Shared auth and rate-limit helpers for Evaluations endpoints.

This module centralizes:
- API key/JWT verification
- Rate-limit dependency helpers
- Error sanitization and admin gating
"""

import os
from typing import Optional, Dict, Any
from fastapi import Depends, Header, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.settings import get_settings, is_single_user_mode
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.exceptions import InvalidTokenError, TokenExpiredError
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_rate_limiter_dep
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User


security = HTTPBearer(auto_error=False)


def sanitize_error_message(error: Exception, context: str = "") -> str:
    """Return a safe error string while logging details."""
    try:
        logger.error(f"Error in {context}: {type(error).__name__}: {str(error)}")
    except Exception:
        pass
    mapping = {
        "FileNotFoundError": "The requested resource was not found",
        "PermissionError": "Permission denied for this operation",
        "ValueError": "Invalid input provided",
        "KeyError": "Required data is missing",
        "ConnectionError": "Connection failed. Please try again later",
        "TimeoutError": "Operation timed out. Please try again",
        "DatabaseError": "Database operation failed",
        "IntegrityError": "Data integrity error occurred",
        "NotFoundError": "The requested resource was not found",
        "ValidationError": "Validation failed for the provided data",
    }
    name = type(error).__name__
    if name in mapping:
        return mapping[name]
    return f"An error occurred during {context}" if context else "An internal error occurred. Please try again later"


def create_error_response(
    message: str,
    error_type: str = "invalid_request_error",
    param: Optional[str] = None,
    code: Optional[str] = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "message": message,
                "type": error_type,
                "param": param,
                "code": code,
            }
        },
    )


async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
) -> str:
    """Verify API key or JWT token based on auth mode (single_user|multi_user)."""
    settings = get_settings()

    # Testing bypass
    try:
        if os.getenv("TESTING", "").lower() in ("true", "1", "yes") and \
           os.getenv("EVALS_HEAVY_ADMIN_ONLY", "true").lower() not in ("true", "1", "yes"):
            return "test_user"
    except Exception:
        pass

    token = None
    if settings.AUTH_MODE == "single_user" and x_api_key and isinstance(x_api_key, str):
        token = x_api_key
    elif credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {
                "message": "Missing API key or token",
                "type": "authentication_error",
                "code": "missing_credentials",
            }},
        )

    if isinstance(token, str) and token.startswith("Bearer "):
        token = token[7:]

    # Test-mode convenience
    try:
        if os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes") and settings.AUTH_MODE == "single_user":
            return token
    except Exception:
        pass

    if settings.AUTH_MODE == "single_user":
        expected_token = (
            os.getenv("SINGLE_USER_API_KEY")
            or getattr(settings, "SINGLE_USER_API_KEY", None)
            or os.getenv("API_BEARER")
            or getattr(settings, "API_BEARER", None)
        )
        if not expected_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": {
                    "message": "Server authentication not configured",
                    "type": "configuration_error",
                    "code": "auth_not_configured",
                }},
            )
        if token == expected_token:
            return token
    elif settings.AUTH_MODE == "multi_user":
        # In TEST_MODE, allow using SINGLE_USER_API_KEY as a bearer for compatibility
        try:
            if os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes"):
                env_key = os.getenv("SINGLE_USER_API_KEY") or getattr(settings, "SINGLE_USER_API_KEY", None)
                if env_key and token == env_key:
                    return "test_user"
        except Exception:
            pass
        try:
            jwt_service = JWTService(settings)
            payload = jwt_service.decode_access_token(token)
            return f"user_{payload['sub']}"
        except TokenExpiredError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {
                    "message": "Token has expired",
                    "type": "authentication_error",
                    "code": "token_expired",
                }},
            )
        except InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {
                    "message": sanitize_error_message(e, "authentication"),
                    "type": "authentication_error",
                    "code": "invalid_token",
                }},
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {
            "message": "Invalid API key or token",
            "type": "authentication_error",
            "code": "invalid_credentials",
        }},
    )


async def check_evaluation_rate_limit(
    request: Request,
    rate_limiter = Depends(get_rate_limiter_dep),
):
    """Simple IP/path based limiter for high-level guarding (per-minute)."""
    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path
    if "batch" in path:
        limit = 5
        endpoint_type = "eval_batch"
    elif "/runs" in path:
        limit = 10
        endpoint_type = "eval_run"
    else:
        limit = 60
        endpoint_type = "eval_standard"
    allowed, metadata = await rate_limiter.check_rate_limit(client_ip, endpoint_type, limit=limit, window_minutes=1)
    if not allowed:
        retry_after = metadata.get("retry_after", 60)
        logger.warning(f"Rate limit exceeded for {client_ip} on {endpoint_type}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {retry_after} seconds",
            headers={"Retry-After": str(retry_after)},
        )


async def _apply_rate_limit_headers(limiter, user_id: str, response: Response, meta: Optional[Dict[str, Any]] = None) -> None:
    try:
        summary = await limiter.get_usage_summary(user_id)
        limits = summary.get("limits", {})
        usage = summary.get("usage", {})
        remaining = summary.get("remaining", {})
        response.headers["X-RateLimit-Tier"] = str(summary.get("tier", "free"))
        pm = limits.get("per_minute", {})
        per_min_limit = int(pm.get("evaluations", 0) or 0)
        response.headers["X-RateLimit-PerMinute-Limit"] = str(per_min_limit)
        try:
            remaining_requests = meta.get("requests_remaining") if isinstance(meta, dict) else None
            response.headers["X-RateLimit-PerMinute-Remaining"] = str(int(remaining_requests or 0))
        except Exception:
            response.headers["X-RateLimit-PerMinute-Remaining"] = "0"
        daily = limits.get("daily", {})
        response.headers["X-RateLimit-Daily-Limit"] = str(daily.get("evaluations", 0))
        response.headers["X-RateLimit-Daily-Remaining"] = str(remaining.get("daily_evaluations", 0))
        response.headers["X-RateLimit-Tokens-Remaining"] = str(remaining.get("daily_tokens", 0))
        response.headers["X-RateLimit-Daily-Cost-Remaining"] = f"{remaining.get('daily_cost', 0):.2f}"
        response.headers["X-RateLimit-Monthly-Cost-Remaining"] = f"{remaining.get('monthly_cost', 0):.2f}"
        response.headers["RateLimit-Limit"] = str(per_min_limit)
        if isinstance(meta, dict) and "requests_remaining" in meta:
            response.headers["RateLimit-Remaining"] = str(int(meta.get("requests_remaining") or 0))
        reset_val = int(meta.get("reset_seconds") or 60) if isinstance(meta, dict) else 60
        response.headers["RateLimit-Reset"] = str(reset_val)
        response.headers["X-RateLimit-Reset"] = str(reset_val)
    except Exception:
        pass


def require_admin(user: User) -> None:
    try:
        if is_single_user_mode():
            return
    except Exception:
        pass
    if os.getenv("EVALS_HEAVY_ADMIN_ONLY", "true").lower() not in ("true", "1", "yes"):
        return
    if not user or not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin privileges required for heavy evaluations")


__all__ = [
    "verify_api_key",
    "sanitize_error_message",
    "create_error_response",
    "check_evaluation_rate_limit",
    "_apply_rate_limit_headers",
    "require_admin",
]
