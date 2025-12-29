"""
auth_principal_resolver.py

Resolver for the unified AuthPrincipal / AuthContext models.

This module provides a single entry point for deriving the authenticated
principal for a request. It intentionally reuses existing AuthNZ helpers
so that behavior stays aligned with current authentication flows.
"""

import os
from typing import Optional

from fastapi import HTTPException, Request, status
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.AuthNZ import User_DB_Handling
from tldw_Server_API.app.core.AuthNZ.principal_model import (
    AuthContext,
    AuthPrincipal,
    PrincipalKind,
)
from tldw_Server_API.app.core.AuthNZ.ip_allowlist import is_single_user_ip_allowed
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.exceptions import InactiveUserError


def is_single_user_mode() -> bool:
    """
    Compatibility shim for tests that expect this helper in auth_principal_resolver.

    The canonical implementation lives in AuthNZ settings; this thin wrapper
    allows tests to monkeypatch the mode without touching global settings.
    """
    try:
        from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode as _is_single_user_mode  # noqa: WPS433

        return _is_single_user_mode()
    except Exception:
        return False


def _extract_bearer_token(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None
        scheme, _, credential = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not credential:
            return None
        return credential.strip()
    except (AttributeError, TypeError):
        return None


def _extract_api_key(request: Request) -> Optional[str]:
    """Extract API key from X-API-KEY header."""
    try:
        api_key = request.headers.get("X-API-KEY")
        if isinstance(api_key, str) and api_key.strip():
            return api_key.strip()
    except (AttributeError, TypeError):
        return None

    # Legacy compatibility: allow "Token: Bearer <api_key>" header
    try:
        legacy = request.headers.get("Token")
        if not isinstance(legacy, str) or not legacy.strip():
            return None
        legacy = legacy.strip()
        if legacy.lower().startswith("bearer "):
            extracted = legacy[len("Bearer ") :].strip()
            return extracted if extracted else None
        return None
    except (AttributeError, TypeError):
        return None


def _build_principal_from_user(
    user: User,
    *,
    kind: PrincipalKind,
    request: Request,
    token_type: Optional[str] = None,
    jti: Optional[str] = None,
    subject: Optional[str] = None,
    api_key_id: Optional[int] = None,
) -> AuthPrincipal:
    """
    Construct an AuthPrincipal from an authenticated User and request context.

    This helper derives organization and team membership from request.state
    for backwards compatibility with existing middleware and DB scoping logic.
    """
    # Best-effort numeric user id
    try:
        user_id_int = user.id_int
    except (AttributeError, TypeError, ValueError):
        logger.debug("Could not extract numeric user_id from user object")
        user_id_int = None

    # Membership/context from request.state (if present)
    org_ids: list[int] = []
    team_ids: list[int] = []
    try:
        raw_org_ids = getattr(request.state, "org_ids", None)
        if isinstance(raw_org_ids, (list, tuple)):
            org_ids = [int(o) for o in raw_org_ids if o is not None]
    except (AttributeError, TypeError, ValueError):
        org_ids = []
    try:
        raw_team_ids = getattr(request.state, "team_ids", None)
        if isinstance(raw_team_ids, (list, tuple)):
            team_ids = [int(t) for t in raw_team_ids if t is not None]
    except (AttributeError, TypeError, ValueError):
        team_ids = []

    # Claims on the User model are the canonical source of truth
    roles = list(getattr(user, "roles", []) or [])
    permissions = list(getattr(user, "permissions", []) or [])
    is_admin = bool(getattr(user, "is_admin", False) or ("admin" in roles))
    username = None
    email = None
    try:
        raw_username = getattr(user, "username", None)
        if raw_username:
            username = str(raw_username)
    except Exception:
        username = None
    try:
        raw_email = getattr(user, "email", None)
        if raw_email:
            email = str(raw_email)
    except Exception:
        email = None

    principal = AuthPrincipal(
        kind=kind,
        user_id=user_id_int,
        api_key_id=api_key_id,
        username=username,
        email=email,
        subject=subject,
        token_type=token_type,
        jti=jti,
        roles=roles,
        permissions=permissions,
        is_admin=is_admin,
        org_ids=org_ids,
        team_ids=team_ids,
    )
    return principal


def _build_context(
    principal: AuthPrincipal,
    request: Request,
) -> AuthContext:
    """Construct AuthContext from principal and request metadata."""
    try:
        ip = request.client.host if request.client else None  # type: ignore[union-attr]
    except (AttributeError, TypeError):
        ip = None
    try:
        user_agent = request.headers.get("User-Agent")
    except (AttributeError, TypeError):
        user_agent = None
    try:
        request_id = (
            request.headers.get("X-Request-ID")
            or getattr(request.state, "request_id", None)
        )
        # getattr(request, "state", ...) can raise if state is not present or misconfigured
    except (AttributeError, TypeError):
        request_id = None

    return AuthContext(
        principal=principal,
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
    )


async def get_auth_principal(request: Request) -> AuthPrincipal:
    """
    Resolve the AuthPrincipal for the current request.

    Behavior:
    - If request.state.auth is already populated with an AuthContext, reuse it.
    - Prefer Bearer JWT tokens; fall back to X-API-KEY when no token is present.
    - On missing or invalid credentials, raise HTTP 401 with stable semantics.
    """
    # Fast-path: reuse existing AuthContext if present
    existing = getattr(request.state, "auth", None)
    if isinstance(existing, AuthContext):
        return existing.principal
    # Prefer Bearer JWT, fall back to X-API-KEY
    token = _extract_bearer_token(request)
    api_key = _extract_api_key(request)

    # In single-user mode, treat Authorization Bearer as an API key for compatibility.
    if token and not api_key:
        try:
            settings = get_settings()
            if getattr(settings, "AUTH_MODE", None) == "single_user":
                api_key = token
                token = None
        except Exception:
            pass

    if not token and not api_key:
        # Align with existing 401 semantics when no credentials are provided
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (provide Bearer token or X-API-KEY)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # JWT path
    if token:
        try:
            user = await User_DB_Handling.verify_jwt_and_fetch_user(request, token)
        except InactiveUserError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user",
            ) from exc
        except HTTPException:
            # Propagate explicit HTTP errors (401/400/etc.) unchanged
            raise
        except Exception as exc:
            logger.exception("Error resolving principal from JWT: {}", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        # verify_jwt_and_fetch_user populates request.state.auth / _auth_user; reuse if present.
        try:
            ctx = getattr(request.state, "auth", None)
            if isinstance(ctx, AuthContext):
                return ctx.principal
        except (AttributeError, TypeError) as exc:
            # Fall back to rebuilding principal if state is missing/misconfigured.
            logger.debug("Could not access request.state.auth after JWT validation: {}", exc)

        principal = _build_principal_from_user(
            user=user,
            kind="user",
            request=request,
            token_type="access",
            jti=None,
            api_key_id=None,
        )
        ctx = _build_context(principal, request)
        try:
            request.state.auth = ctx
            # Cache the resolved user for downstream dependencies
            request.state._auth_user = user
        except Exception as exc:  # noqa: BLE001 - defensive: caching failures must not break auth
            logger.exception("Unable to cache auth context/user: {}", exc)
        return principal

    # API key path
    if api_key:
        # Single-user compatibility: treat SINGLE_USER_API_KEY/SINGLE_USER_TEST_API_KEY
        # as a user-kind principal without requiring API key store lookups.
        try:
            from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings  # noqa: WPS433

            settings = _get_settings()
            if getattr(settings, "AUTH_MODE", None) == "single_user":
                allowed_keys: set[str] = set()
                primary_key = getattr(settings, "SINGLE_USER_API_KEY", None)
                if primary_key:
                    allowed_keys.add(primary_key)
                test_key = os.getenv("SINGLE_USER_TEST_API_KEY")
                if test_key:
                    allowed_keys.add(test_key)
                if api_key in allowed_keys:
                    client_ip = None
                    try:
                        client = getattr(request, "client", None)
                        if client is not None:
                            client_ip = getattr(client, "host", None)
                    except Exception:
                        client_ip = None
                    if not is_single_user_ip_allowed(client_ip, settings):
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not authenticated (provide Bearer token or X-API-KEY)",
                            headers={"WWW-Authenticate": "Bearer"},
                        )
                    user = User_DB_Handling.get_single_user_instance()
                    principal = _build_principal_from_user(
                        user=user,
                        kind="user",
                        request=request,
                        token_type="api_key",
                        jti=None,
                        api_key_id=None,
                    )
                    ctx = _build_context(principal, request)
                    try:
                        request.state.auth = ctx
                        request.state._auth_user = user
                        request.state.user_id = user.id
                        request.state.api_key_id = None
                        request.state.team_ids = []
                        request.state.org_ids = []
                    except Exception as state_exc:
                        logger.debug(
                            "auth_principal_resolver: unable to attach single-user state context: {}",
                            state_exc,
                        )
                    return principal
        except Exception as single_exc:
            logger.debug(
                "auth_principal_resolver: single-user API key compat path failed; falling back: {}",
                single_exc,
            )

        try:
            user = await User_DB_Handling.authenticate_api_key_user(request, api_key)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Error resolving principal from API key: {}", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
            ) from exc

        # authenticate_api_key_user populates request.state.auth / _auth_user; reuse if present.
        try:
            ctx = getattr(request.state, "auth", None)
            if isinstance(ctx, AuthContext):
                return ctx.principal
        except (AttributeError, TypeError) as exc:
            logger.debug("Could not access request.state.auth after API key validation: {}", exc)

        api_key_id: Optional[int] = None
        try:
            raw_api_key_id = getattr(request.state, "api_key_id", None)
            if raw_api_key_id is not None:
                api_key_id = int(raw_api_key_id)
        except (AttributeError, TypeError, ValueError):
            api_key_id = None

        principal = _build_principal_from_user(
            user=user,
            kind="api_key",
            request=request,
            token_type="api_key",
            jti=None,
            api_key_id=api_key_id,
        )
        ctx = _build_context(principal, request)
        try:
            request.state.auth = ctx
            # Cache the resolved user for downstream dependencies
            request.state._auth_user = user
        except Exception as exc:  # noqa: BLE001 - defensive: caching failures must not break auth
            logger.exception("Unable to cache auth context/user: {}", exc)
        return principal

    # Fallback (should not be reached)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
