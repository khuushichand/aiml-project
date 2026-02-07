"""
Shared auth and rate-limit helpers for Evaluations endpoints.

This module centralizes:
- API key/JWT verification
- Rate-limit dependency helpers
- Error sanitization and admin gating
"""

import contextlib
import os
import warnings
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_rate_limiter_dep
from tldw_Server_API.app.api.v1.API_Deps.v1_endpoint_deps import oauth2_scheme
from tldw_Server_API.app.core.AuthNZ.exceptions import InvalidTokenError, TokenExpiredError
from tldw_Server_API.app.core.AuthNZ.ip_allowlist import (
    is_single_user_ip_allowed,
    resolve_client_ip,
)
from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import (
    User,
    get_request_user,
    verify_jwt_and_fetch_user,
)
from tldw_Server_API.app.core.exceptions import InactiveUserError

security = HTTPBearer(auto_error=False)


def sanitize_error_message(error: Exception, context: str = "") -> str:
    """Return a safe error string while logging details."""
    with contextlib.suppress(Exception):
        logger.error(f"Error in {context}: {type(error).__name__}: {str(error)}")
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
    *,
    request: Request,
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

    client_ip = resolve_client_ip(request, settings)

    if settings.AUTH_MODE == "single_user" and not is_single_user_ip_allowed(client_ip, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {
                "message": "Access denied from this network",
                "type": "authentication_error",
                "code": "ip_not_allowed",
            }},
        )

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
            jwt_service = get_jwt_service()
            # Decode early to surface token-specific errors before user lookup.
            jwt_service.decode_access_token(token)
        except TokenExpiredError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {
                    "message": "Token has expired",
                    "type": "authentication_error",
                    "code": "token_expired",
                }},
            ) from None
        except InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {
                    "message": sanitize_error_message(e, "authentication"),
                    "type": "authentication_error",
                    "code": "invalid_token",
                }},
            ) from e
        except Exception as exc:
            logger.error(f"Unexpected error decoding JWT for evaluations auth: {exc}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {
                    "message": "Invalid API key or token",
                    "type": "authentication_error",
                    "code": "invalid_token",
                }},
            ) from exc
        try:
            user = await verify_jwt_and_fetch_user(request, token)
            user_id = getattr(user, "id_str", None) or str(getattr(user, "id", ""))
            return f"user_{user_id}"
        except InactiveUserError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {
                    "message": "Inactive user",
                    "type": "authentication_error",
                    "code": "inactive_user",
                }},
            ) from exc
        except HTTPException as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {
                    "message": "Invalid API key or token",
                    "type": "authentication_error",
                    "code": "invalid_credentials",
                }},
            ) from exc
        except Exception as exc:
            logger.error(f"Unexpected error verifying JWT for evaluations auth: {exc}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {
                    "message": "Invalid API key or token",
                    "type": "authentication_error",
                    "code": "invalid_credentials",
                }},
            ) from exc

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {
            "message": "Invalid API key or token",
            "type": "authentication_error",
            "code": "invalid_credentials",
        }},
    )


async def get_eval_request_user(
    request: Request,
    _user_ctx: str = Depends(verify_api_key),
    api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    token: Optional[str] = Depends(oauth2_scheme),
    legacy_token_header: Optional[str] = Header(None, alias="Token"),
) -> User:
    """Resolve the authenticated User after evaluations auth validation."""
    if not api_key and not token and not legacy_token_header:
        try:
            if os.getenv("TESTING", "").lower() in {"true", "1", "yes", "on"} and \
               os.getenv("EVALS_HEAVY_ADMIN_ONLY", "true").lower() not in {"true", "1", "yes", "on"}:
                return await get_request_user(
                    request=request,
                    api_key=api_key,
                    token=token,
                    legacy_token_header=legacy_token_header,
                )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "message": "Missing API key or token",
                    "type": "authentication_error",
                    "code": "missing_credentials",
                }
            },
        )
    return await get_request_user(
        request=request,
        api_key=api_key,
        token=token,
        legacy_token_header=legacy_token_header,
    )


def require_eval_permissions(*permissions: str):
    """Evaluation-specific permission gate with consistent auth errors."""
    perms = [str(p) for p in permissions if str(p).strip()]

    async def _checker(current_user: User = Depends(get_eval_request_user)) -> User:  # noqa: B008
        if getattr(current_user, "is_admin", False):
            return current_user
        user_perms = set(getattr(current_user, "permissions", []) or [])
        missing = [p for p in perms if p not in user_perms]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: missing {', '.join(missing)}",
            )
        return current_user

    return _checker


async def check_evaluation_rate_limit(
    request: Request,
    rate_limiter = Depends(get_rate_limiter_dep),
):
    """Simple IP/path based limiter for high-level guarding (per-minute)."""
    # If ResourceGovernor ingress has already governed this route, avoid
    # double-enforcement via legacy AuthNZ rate limiter.
    try:
        policy_id = getattr(request.state, "rg_policy_id", None)
        if policy_id:
            logger.debug(
                f"Skipping rate limit check; ResourceGovernor policy {policy_id} already applied"
            )
            return
    except AttributeError:
        # request.state may not exist in some test scenarios
        pass

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


async def _apply_rate_limit_headers(limiter, user_id: str, response: Response, meta: Optional[dict[str, Any]] = None) -> None:
    try:
        summary = await limiter.get_usage_summary(user_id)
        limits = summary.get("limits", {})
        summary.get("usage", {})
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


def enforce_heavy_evaluations_admin(principal: Optional[AuthPrincipal]) -> None:
    """
    Claim-first enforcement for heavy evaluations admin operations.

    When EVALS_HEAVY_ADMIN_ONLY is disabled, this is a no-op. Otherwise,
    require an admin-style principal (is_admin or role 'admin') for heavy
    evaluations flows.

    Args:
        principal: Authenticated principal; None is only allowed when
                   EVALS_HEAVY_ADMIN_ONLY is disabled.

    Raises:
        HTTPException: 403 if admin privileges are required but not present.
    """
    if os.getenv("EVALS_HEAVY_ADMIN_ONLY", "true").lower() not in ("true", "1", "yes"):
        return
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for heavy evaluations",
        )
    is_admin_flag = bool(
        principal.is_admin
        or ("admin" in (principal.roles or []))
    )
    if not is_admin_flag:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for heavy evaluations",
        )


def require_admin(user: User) -> None:
    """
    Legacy user-dict gate for heavy evaluations (compatibility shim).

    New code and HTTP routes should prefer the claim-first
    `enforce_heavy_evaluations_admin(AuthPrincipal)` helper together with
    `require_roles` / `require_permissions`. This function is kept only
    for tests and for any remaining legacy callsites that have not yet
    been migrated.
    """
    warnings.warn(
        "evaluations_auth.require_admin is deprecated; use enforce_heavy_evaluations_admin(principal) "
        "with claim-first dependencies instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    if os.getenv("EVALS_HEAVY_ADMIN_ONLY", "true").lower() not in ("true", "1", "yes"):
        return
    is_admin_flag = bool(
        getattr(user, "is_admin", False)
        or getattr(user, "role", None) == "admin"
        or ("admin" in (getattr(user, "roles", None) or []))
    )
    if not user or not is_admin_flag:
        raise HTTPException(status_code=403, detail="Admin privileges required for heavy evaluations")


__all__ = [
    "verify_api_key",
    "sanitize_error_message",
    "create_error_response",
    "check_evaluation_rate_limit",
    "_apply_rate_limit_headers",
    "require_admin",
    "enforce_heavy_evaluations_admin",
]
