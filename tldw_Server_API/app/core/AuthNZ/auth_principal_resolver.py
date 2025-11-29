"""
auth_principal_resolver.py

Resolver for the unified AuthPrincipal / AuthContext models.

This module provides a single entry point for deriving the authenticated
principal for a request. It intentionally reuses existing AuthNZ helpers
so that behavior stays aligned with current authentication flows.
"""

from typing import Optional

from fastapi import HTTPException, Request, status
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import (
    User,
    get_request_user,
    get_single_user_instance,
    verify_jwt_and_fetch_user,
    verify_single_user_api_key,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import (
    AuthContext,
    AuthPrincipal,
    PrincipalKind,
)
from tldw_Server_API.app.core.AuthNZ.settings import (
    get_settings,
    is_single_user_mode,
)


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
    except Exception:
        return None


def _extract_api_key(request: Request) -> Optional[str]:
    """Extract API key from X-API-KEY header."""
    try:
        api_key = request.headers.get("X-API-KEY")
        return api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
    except Exception:
        return None


def _build_principal_from_user(
    user: User,
    *,
    kind: PrincipalKind,
    request: Request,
    token_type: Optional[str] = None,
    jti: Optional[str] = None,
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
    except Exception:
        user_id_int = None

    # Membership/context from request.state (if present)
    org_ids: list[int] = []
    team_ids: list[int] = []
    try:
        raw_org_ids = getattr(request.state, "org_ids", None)
        if isinstance(raw_org_ids, (list, tuple)):
            org_ids = [int(o) for o in raw_org_ids if o is not None]
    except Exception:
        org_ids = []
    try:
        raw_team_ids = getattr(request.state, "team_ids", None)
        if isinstance(raw_team_ids, (list, tuple)):
            team_ids = [int(t) for t in raw_team_ids if t is not None]
    except Exception:
        team_ids = []

    # Claims on the User model are the canonical source of truth
    roles = list(getattr(user, "roles", []) or [])
    permissions = list(getattr(user, "permissions", []) or [])
    is_admin = bool(getattr(user, "is_admin", False) or ("admin" in roles))

    principal = AuthPrincipal(
        kind=kind,
        user_id=user_id_int,
        api_key_id=api_key_id,
        subject=None,
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
    except Exception:
        ip = None
    try:
        user_agent = request.headers.get("User-Agent")
    except Exception:
        user_agent = None
    try:
        request_id = (
            request.headers.get("X-Request-ID")
            or getattr(request.state, "request_id", None)
        )
    except Exception:
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
    - In single-user mode, validate the configured API key and treat the
      bootstrapped user as a single_user principal with admin-style claims.
    - In multi-user mode, prefer Bearer JWT tokens; fall back to X-API-KEY.
    - On missing or invalid credentials, raise HTTP 401 with stable semantics.
    """
    # Fast-path: reuse existing AuthContext if present
    existing = getattr(request.state, "auth", None)
    if isinstance(existing, AuthContext):
        return existing.principal

    settings = get_settings()

    # Single-user mode: validate fixed API key and map to single_user principal
    try:
        if is_single_user_mode():
            api_key = _extract_api_key(request)
            authorization = request.headers.get("Authorization") if getattr(request, "headers", None) else None

            # Reuse existing verification helper to honor all existing semantics
            await verify_single_user_api_key(
                request,
                api_key=api_key,
                authorization=authorization,
            )

            base_user = get_single_user_instance()
            # Mirror the claims semantics from get_request_user's single-user branch
            user = User(
                id=base_user.id,
                username=base_user.username,
                email=base_user.email,
                is_active=base_user.is_active,
                roles=["admin"],
                permissions=[
                    "system.configure",
                    "media.read",
                    "media.create",
                    "media.update",
                    "media.delete",
                ],
                is_admin=True,
            )

            # Maintain legacy request.state fields for compatibility
            try:
                request.state.user_id = user.id
                request.state.team_ids = []
                request.state.org_ids = []
            except Exception:
                pass

            principal = _build_principal_from_user(
                user=user,
                kind="single_user",
                request=request,
                token_type="api_key",
                jti=None,
                api_key_id=None,
            )
            ctx = _build_context(principal, request)
            try:
                request.state.auth = ctx
            except Exception:
                pass
            return principal
    except HTTPException:
        # Propagate auth failures as-is
        raise
    except Exception as exc:
        logger.error(f"Error resolving principal in single-user mode: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Multi-user mode: prefer Bearer JWT, fall back to X-API-KEY
    token = _extract_bearer_token(request)
    api_key = _extract_api_key(request)

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
            user = await verify_jwt_and_fetch_user(request, token)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error resolving principal from JWT: {exc}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

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
        except Exception:
            pass
        return principal

    # API key path
    if api_key:
        try:
            # Reuse existing logic that validates API keys and attaches
            # request.state.user_id, api_key_id, org_ids, team_ids.
            user = await get_request_user(request, token="", api_key=api_key)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error resolving principal from API key: {exc}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
            )

        api_key_id: Optional[int] = None
        try:
            raw_api_key_id = getattr(request.state, "api_key_id", None)
            if raw_api_key_id is not None:
                api_key_id = int(raw_api_key_id)
        except Exception:
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
        except Exception:
            pass
        return principal

    # Fallback (should not be reached)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

