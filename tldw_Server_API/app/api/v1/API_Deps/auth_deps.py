# auth_deps.py
# Description: FastAPI dependency injection for authentication services
#
# Imports
from typing import Optional, Dict, Any, List
import re
import os
#
# 3rd-party imports
from fastapi import Depends, HTTPException, status, Request, Header, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger
#
# Local imports
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService, get_password_service
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService, get_jwt_service
from tldw_Server_API.app.core.AuthNZ.session_manager import SessionManager, get_session_manager
from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode, get_settings
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter, get_rate_limiter
from tldw_Server_API.app.services.registration_service import RegistrationService, get_registration_service
from tldw_Server_API.app.services.storage_quota_service import StorageQuotaService, get_storage_service
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    AuthenticationError,
    InvalidTokenError,
    TokenExpiredError,
    UserNotFoundError,
    AccountInactiveError,
    InsufficientPermissionsError
)
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.DB_Management.Users_DB import get_users_db
from tldw_Server_API.app.core.AuthNZ.db_config import get_configured_user_database
from tldw_Server_API.app.core.AuthNZ.orgs_teams import list_memberships_for_user
from tldw_Server_API.app.core.DB_Management.scope_context import set_scope

# Test stub shared state (persist across dependency calls under TEST_MODE/pytest)
_TEST_SESSION_STATE: dict = {"sid": 1000, "sessions": {}}

#######################################################################################################################
#
# Security scheme for JWT bearer tokens

security = HTTPBearer(auto_error=False)


#######################################################################################################################
#
# Service Dependency Functions

def _activate_scope_context(
    request: Request,
    *,
    user_id: Optional[int],
    org_ids: Optional[List[int]],
    team_ids: Optional[List[int]],
    is_admin: bool,
) -> None:
    """Record content scope information for downstream database access."""
    try:
        active_org = getattr(request.state, "active_org_id", None)
        active_team = getattr(request.state, "active_team_id", None)
        token = set_scope(
            user_id=user_id,
            org_ids=org_ids or (),
            team_ids=team_ids or (),
            active_org_id=active_org,
            active_team_id=active_team,
            is_admin=is_admin,
        )
        setattr(request.state, "_content_scope_token", token)
    except Exception as exc:
        logger.debug(f"Unable to establish content scope context: {exc}")

async def get_db_transaction():
    """Get database connection in transaction mode.

    Always behaves as an async generator for FastAPI compatibility. In TEST_MODE/pytest,
    yields a lightweight pool adapter that runs queries without holding a long-lived
    transaction to avoid event-loop and teardown issues. Otherwise, yields a
    request-scoped transaction connection.
    """
    db_pool = await get_db_pool()

    # Decide whether to use the lightweight adapter (tests/pytest) or a real transaction
    use_adapter = False
    try:
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            use_adapter = True
        else:
            import sys as _sys  # local import to avoid test-only dependency at module import
            if "pytest" in _sys.modules:
                use_adapter = True
    except Exception:
        # If any detection fails, fall back to default transaction behavior
        use_adapter = False

    if use_adapter:
        # Keep a single connection open for the request lifetime so cursors remain valid
        conn_cm = db_pool.acquire()
        conn = await conn_cm.__aenter__()

        class _ConnAdapter:
            def __init__(self, _conn):
                self._conn = _conn
                # Heuristic: asyncpg connection exposes fetchrow; aiosqlite does not
                self._is_sqlite = not hasattr(self._conn, "fetchrow")
                self._dollar_param = re.compile(r"\$\d+")

            def _normalize_sqlite_sql(self, query: str) -> str:
                if not self._is_sqlite or "$" not in query:
                    return query
                # Replace $1, $2 ... with '?'
                return self._dollar_param.sub("?", query)

            async def execute(self, query: str, *args):
                # Postgres (asyncpg) supports variadic args; SQLite expects a sequence
                if not self._is_sqlite:
                    # asyncpg connection
                    return await self._conn.execute(query, *args)
                else:
                    params = args[0] if (len(args) == 1 and isinstance(args[0], (list, tuple))) else args
                    q = self._normalize_sqlite_sql(query)
                    cur = await self._conn.execute(q, params)
                    try:
                        await self._conn.commit()
                    except Exception:
                        pass
                    return cur

            async def fetchval(self, query: str, *args):
                if not self._is_sqlite:
                    # asyncpg connection
                    return await self._conn.fetchval(query, *args)
                else:
                    params = args[0] if (len(args) == 1 and isinstance(args[0], (list, tuple))) else args
                    q = self._normalize_sqlite_sql(query)
                    cur = await self._conn.execute(q, params)
                    row = await cur.fetchone()
                    return row[0] if row else None

            async def fetch(self, query: str, *args):
                if not self._is_sqlite:
                    # asyncpg connection
                    rows = await self._conn.fetch(query, *args)
                    return [dict(r) for r in rows]
                else:
                    params = args[0] if (len(args) == 1 and isinstance(args[0], (list, tuple))) else args
                    q = self._normalize_sqlite_sql(query)
                    cur = await self._conn.execute(q, params)
                    rows = await cur.fetchall()
                    try:
                        return [{key: r[key] for key in r.keys()} for r in rows]
                    except Exception:
                        return rows

            async def fetchrow(self, query: str, *args):
                if not self._is_sqlite:
                    # asyncpg connection
                    return await self._conn.fetchrow(query, *args)
                else:
                    params = args[0] if (len(args) == 1 and isinstance(args[0], (list, tuple))) else args
                    q = self._normalize_sqlite_sql(query)
                    cur = await self._conn.execute(q, params)
                    row = await cur.fetchone()
                    try:
                        return {key: row[key] for key in row.keys()} if row else None
                    except Exception:
                        return row

            async def commit(self):
                if self._is_sqlite:
                    try:
                        await self._conn.commit()
                    except Exception:
                        pass

        adapter = _ConnAdapter(conn)
        try:
            yield adapter
        finally:
            await conn_cm.__aexit__(None, None, None)
    else:
        # Default: yield a request-scoped transaction so writes commit reliably
        async with db_pool.transaction() as conn:
            yield conn


async def get_password_service_dep() -> PasswordService:
    """Get password service dependency"""
    return get_password_service()


async def get_jwt_service_dep() -> JWTService:
    """Get JWT service dependency"""
    return get_jwt_service()


async def get_session_manager_dep() -> SessionManager:
    """Get session manager dependency"""
    # In pytest/TEST_MODE contexts, return a lightweight stub to avoid heavy init
    try:
        import os as _os, sys as _sys

        force_real = _os.getenv("AUTHNZ_FORCE_REAL_SESSION_MANAGER", "").lower() in ("1", "true", "yes")
        if not force_real and (_os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes") or "pytest" in _sys.modules):
            from datetime import datetime  # local import for stub

            class _StubSessionManager:
                enabled = True

                async def is_token_blacklisted(
                    self,
                    token: str,
                    jti: Optional[str] = None,
                    *,
                    token_type: Optional[str] = None,
                    user_id: Optional[int] = None,
                ) -> bool:
                    return False

                async def create_session(
                    self,
                    user_id: int,
                    access_token: str,
                    refresh_token: str,
                    ip_address: str = "",
                    user_agent: str = "",
                ):
                    _TEST_SESSION_STATE["sid"] += 1
                    sid = _TEST_SESSION_STATE["sid"]
                    now = datetime.utcnow()
                    sess = {
                        "id": sid,
                        "session_id": sid,
                        "user_id": user_id,
                        "ip_address": ip_address,
                        "user_agent": user_agent,
                        "created_at": now,
                        "last_activity": now,
                        "expires_at": now,
                        "is_active": True,
                        "is_revoked": False,
                    }
                    _TEST_SESSION_STATE["sessions"][sid] = sess
                    return sess

                async def update_session_tokens(self, session_id: int, access_token: str, refresh_token: str):
                    # No-op in stub
                    return True

                async def refresh_session(self, *args, **kwargs):
                    return {
                        "session_id": kwargs.get("session_id") or 1,
                        "user_id": kwargs.get("user_id") or 1,
                        "expires_at": datetime.utcnow().isoformat(),
                    }

                async def get_user_sessions(self, user_id: int):
                    return [s for s in _TEST_SESSION_STATE["sessions"].values() if s.get("user_id") == user_id]

                async def revoke_session(self, session_id: int, *args, **kwargs):
                    if session_id in _TEST_SESSION_STATE["sessions"]:
                        _TEST_SESSION_STATE["sessions"][session_id]["is_revoked"] = True
                        _TEST_SESSION_STATE["sessions"][session_id]["is_active"] = False
                        return True
                    return False

                async def revoke_all_user_sessions(self, user_id: int):
                    changed = 0
                    for s in _TEST_SESSION_STATE["sessions"].values():
                        if s.get("user_id") == user_id:
                            s["is_revoked"] = True
                            s["is_active"] = False
                            changed += 1
                    return changed

            return _StubSessionManager()  # type: ignore[return-value]
    except Exception:
        pass
    return await get_session_manager()


async def get_rate_limiter_dep() -> RateLimiter:
    """Get rate limiter dependency"""
    # In TEST_MODE, avoid touching the database by returning a disabled, initialized limiter
    try:
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter as _RL
            rl = _RL(db_pool=None)
            rl.enabled = False
            rl._initialized = True
            return rl
    except Exception:
        # Fall back to normal path if any issue
        pass
    return await get_rate_limiter()


async def get_registration_service_dep() -> RegistrationService:
    """Get registration service dependency"""
    return await get_registration_service()


async def get_storage_service_dep() -> StorageQuotaService:
    """Get storage service dependency"""
    return await get_storage_service()


#######################################################################################################################
#
# User Authentication Dependencies

async def get_current_user(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session_manager: SessionManager = Depends(get_session_manager_dep),
    db_pool: DatabasePool = Depends(get_db_pool),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY")
) -> Dict[str, Any]:
    """
    Get current authenticated user from JWT token

    Args:
        request: FastAPI request object
        credentials: Bearer token from Authorization header
        jwt_service: JWT service instance
        session_manager: Session manager instance
        db_pool: Database pool instance

    Returns:
        User dictionary with all user information

    Raises:
        HTTPException: If authentication fails
    """
    # TEST_MODE diagnostics: log auth header presence
    try:
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            logger.info(f"get_current_user: has_bearer={bool(credentials)} has_api_key={bool(x_api_key)} path={request.url.path}")
    except Exception:
        pass

    # Helper: IP allowlist check for single-user mode
    def _ip_allowed_single_user(client_ip: Optional[str]) -> bool:
        try:
            settings = get_settings()
            allowed = [s.strip() for s in (settings.SINGLE_USER_ALLOWED_IPS or []) if str(s).strip()]
            if not allowed:
                return True
            if not client_ip:
                return False
            import ipaddress as _ip
            ip = _ip.ip_address(client_ip)
            for entry in allowed:
                try:
                    # Support exact IP or CIDR
                    if '/' in entry:
                        if ip in _ip.ip_network(entry, strict=False):
                            return True
                    else:
                        if str(ip) == entry:
                            return True
                except Exception:
                    continue
            return False
        except Exception:
            # Fail closed if configuration is malformed
            return False

    # Single-user mode: honor the configured SINGLE_USER_API_KEY directly (no DB lookups)
    try:
        if is_single_user_mode():
            settings = get_settings()
            client_ip = request.client.host if getattr(request, "client", None) else None
            # Accept X-API-KEY header
            # In pytest/TEST_MODE contexts, also accept env override in case Settings were cached pre-change.
            _accept = False
            if x_api_key and x_api_key == settings.SINGLE_USER_API_KEY:
                _accept = True
            else:
                try:
                    import sys as _sys, os as _os
                    if x_api_key and ("pytest" in _sys.modules or _os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes")):
                        env_key = _os.getenv("SINGLE_USER_API_KEY")
                        if env_key and x_api_key == env_key:
                            _accept = True
                except Exception:
                    pass
            if _accept:
                if not _ip_allowed_single_user(client_ip):
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="IP not allowed")
                user = {
                    "id": settings.SINGLE_USER_FIXED_ID,
                    "username": "single_user",
                    "email": None,
                    "role": "admin",
                    "roles": ["admin"],
                    "permissions": ["*"],
                    "is_active": True,
                    "is_verified": True,
                }
                try:
                    request.state.user_id = settings.SINGLE_USER_FIXED_ID
                    request.state.team_ids = []
                    request.state.org_ids = []
                except Exception:
                    pass
                _activate_scope_context(
                    request,
                    user_id=settings.SINGLE_USER_FIXED_ID,
                    org_ids=[],
                    team_ids=[],
                    is_admin=True,
                )
                return user
            # Also allow Authorization: Bearer <SINGLE_USER_API_KEY>
            if credentials and (credentials.scheme or '').lower() == 'bearer':
                token = credentials.credentials
                if token == settings.SINGLE_USER_API_KEY:
                    if not _ip_allowed_single_user(client_ip):
                        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="IP not allowed")
                    user = {
                        "id": settings.SINGLE_USER_FIXED_ID,
                        "username": "single_user",
                        "email": None,
                        "role": "admin",
                        "roles": ["admin"],
                        "permissions": ["*"],
                        "is_active": True,
                        "is_verified": True,
                    }
                    try:
                        request.state.user_id = settings.SINGLE_USER_FIXED_ID
                        request.state.team_ids = []
                        request.state.org_ids = []
                    except Exception:
                        pass
                    _activate_scope_context(
                        request,
                        user_id=settings.SINGLE_USER_FIXED_ID,
                        org_ids=[],
                        team_ids=[],
                        is_admin=True,
                    )
                    return user
    except Exception:
        # Fall through to other mechanisms if any issue arises
        pass

    # If Authorization is absent but X-API-KEY present, attempt API-key auth (SQLite/Postgres multi-user).
    if not credentials and x_api_key:
        test_mode = os.getenv("TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
        if test_mode:
            try:
                settings = get_settings()
            except Exception:
                settings = None
            allowed_keys = {os.getenv("SINGLE_USER_TEST_API_KEY", "test-api-key-12345")}
            if settings and settings.SINGLE_USER_API_KEY:
                allowed_keys.add(settings.SINGLE_USER_API_KEY)
            if x_api_key in allowed_keys:
                try:
                    if settings and isinstance(settings.DATABASE_URL, str) and settings.DATABASE_URL.startswith("sqlite:///"):
                        from pathlib import Path as _Path
                        from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables as _ensure_authnz_tables
                        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
                        _ensure_authnz_tables(_Path(db_path))
                except Exception as _ensure_err:
                    logger.debug(f"AuthNZ test fallback: ensure_authnz_tables skipped/failed: {_ensure_err}")
                fixed_id = getattr(settings, "SINGLE_USER_FIXED_ID", 1)
                user = {
                    "id": fixed_id,
                    "username": "single_user",
                    "email": None,
                    "role": "admin",
                    "roles": ["admin"],
                    "permissions": ["*"],
                    "is_active": True,
                    "is_verified": True,
                }
                try:
                    request.state.user_id = fixed_id
                    request.state.team_ids = []
                    request.state.org_ids = []
                except Exception:
                    pass
                return user
        try:
            api_mgr = await get_api_key_manager()
            # Forward client IP for allowed_ips enforcement
            client_ip = request.client.host if getattr(request, "client", None) else None
            key_info = await api_mgr.validate_api_key(api_key=x_api_key, ip_address=client_ip)
            if not key_info:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key"
                )

            user_id = key_info.get("user_id")
            if not isinstance(user_id, int):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key"
                )

            users_db = await get_users_db()
            user = await users_db.get_user_by_id(user_id)
            if not user or not user.get("is_active", True):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive"
                )

            # Attach user_id for downstream rate limiting where used
            team_ids: List[int] = []
            org_ids: List[int] = []
            try:
                request.state.user_id = user_id
                request.state.api_key_id = key_info.get("id")
                # Best-effort team/org membership resolution for downstream features
                try:
                    memberships = await list_memberships_for_user(int(user_id))
                    team_ids = [m.get("team_id") for m in memberships if m.get("team_id") is not None]
                    org_ids = sorted({m.get("org_id") for m in memberships if m.get("org_id") is not None})
                    request.state.team_ids = team_ids
                    request.state.org_ids = org_ids
                except Exception:
                    request.state.team_ids = []
                    request.state.org_ids = []
            except Exception:
                pass

            _activate_scope_context(
                request,
                user_id=user_id,
                org_ids=org_ids,
                team_ids=team_ids,
                is_admin=bool(user.get("is_admin") or ("admin" in (user.get("roles") or []))),
            )

            return user
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"API key authentication error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate API key"
            )

    # Otherwise, require Bearer token
    if not credentials:
        # TEST_MODE: surface why we failed
        extra_headers = {"WWW-Authenticate": "Bearer"}
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            try:
                present_headers = ",".join(h for h in ("Authorization", "X-API-KEY") if request.headers.get(h)) or "none"
                extra_headers["X-TLDW-Auth-Reason"] = "missing-bearer"
                extra_headers["X-TLDW-Auth-Headers"] = present_headers
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers=extra_headers
        )

    try:
        # Extract token
        token = credentials.credentials

        # Single-user mode should not attempt JWT initialization
        try:
            if is_single_user_mode():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"}
                )
        except Exception:
            # If settings lookup fails, proceed to JWT path by default
            pass

        # Lazily obtain JWT service only in multi-user path
        jwt_service = get_jwt_service()

        # Decode and validate JWT
        payload = jwt_service.decode_access_token(token)

        # Check if token is blacklisted (fail-closed on errors)
        jti = payload.get("jti")
        if await session_manager.is_token_blacklisted(token, jti):
            raise InvalidTokenError("Token has been revoked")

        # Get user from database
        # JWT standard uses 'sub' for subject (user ID)
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise InvalidTokenError("Invalid token payload")

        # Convert to int if it's a string
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            raise InvalidTokenError("Invalid user ID in token")

        # Fetch user from database
        if db_pool.pool:  # PostgreSQL
            user = await db_pool.fetchone(
                "SELECT * FROM users WHERE id = $1 AND is_active = $2",
                user_id, True
            )
        else:  # SQLite
            user = await db_pool.fetchone(
                "SELECT * FROM users WHERE id = ? AND is_active = ?",
                user_id, 1
            )

        if not user:
            raise UserNotFoundError(f"User {user_id}")

        # Session activity is already updated during token validation in session_manager

        # Convert to dict if needed
        if hasattr(user, 'dict'):
            user = dict(user)

        # Attach user_id for downstream rate limiting where used
        team_ids: List[int] = []
        org_ids: List[int] = []
        try:
            request.state.user_id = int(user_id)
            # Best-effort team/org membership resolution
            try:
                memberships = await list_memberships_for_user(int(user_id))
                team_ids = [m.get("team_id") for m in memberships if m.get("team_id") is not None]
                org_ids = sorted({m.get("org_id") for m in memberships if m.get("org_id") is not None})
                request.state.team_ids = team_ids
                request.state.org_ids = org_ids
            except Exception:
                request.state.team_ids = []
                request.state.org_ids = []
                pass
        except Exception:
            pass

        _activate_scope_context(
            request,
            user_id=int(user_id) if isinstance(user_id, int) else None,
            org_ids=org_ids,
            team_ids=team_ids,
            is_admin=bool(user.get("is_admin") or ("admin" in (user.get("roles") or []))),
        )

        return user

    except TokenExpiredError:
        logger.warning("get_current_user: token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except InvalidTokenError as e:
        logger.warning(f"get_current_user: invalid token: {e}")
        extra_headers = {"WWW-Authenticate": "Bearer"}
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            extra_headers["X-TLDW-Auth-Reason"] = f"invalid-token:{e}"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers=extra_headers
        )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        extra_headers = {"WWW-Authenticate": "Bearer"}
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            extra_headers["X-TLDW-Auth-Reason"] = f"auth-error:{e}"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers=extra_headers
        )


async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get current active user (verified and not locked)

    Args:
        current_user: Current authenticated user

    Returns:
        User dictionary if active and verified

    Raises:
        HTTPException: If user is inactive or unverified
    """
    if not current_user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    if not current_user.get("is_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )

    return current_user


async def require_admin(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Require admin role for access

    Args:
        current_user: Current active user

    Returns:
        User dictionary if admin

    Raises:
        HTTPException: If user is not admin
    """
    # In single-user mode treat the sole user as admin
    try:
        if is_single_user_mode():
            return current_user
    except Exception:
        pass
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return current_user


def require_role(role: str):
    """
    Create a dependency that requires a specific role

    Args:
        role: Required role name

    Returns:
        Dependency function that checks for the role
    """
    async def role_checker(
        current_user: Dict[str, Any] = Depends(get_current_active_user)
    ) -> Dict[str, Any]:
        user_role = current_user.get("role", "user")

        # Admin can access everything
        if user_role == "admin":
            return current_user

        # Check specific role
        if user_role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {role} role"
            )

        return current_user

    return role_checker


async def get_optional_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    jwt_service: JWTService = Depends(get_jwt_service_dep),
    session_manager: SessionManager = Depends(get_session_manager_dep),
    db_pool: DatabasePool = Depends(get_db_pool)
) -> Optional[Dict[str, Any]]:
    """
    Get current user if authenticated, None otherwise

    This is useful for endpoints that have different behavior
    for authenticated vs unauthenticated users

    Args:
        request: FastAPI request object
        credentials: Optional bearer token
        jwt_service: JWT service instance
        session_manager: Session manager instance
        db_pool: Database pool instance

    Returns:
        User dictionary if authenticated, None otherwise
    """
    if not credentials:
        return None

    try:
        return await get_current_user(
            request, credentials, jwt_service, session_manager, db_pool
        )
    except HTTPException:
        return None


#######################################################################################################################
#
# Rate Limiting Dependencies

async def check_rate_limit(
    request: Request,
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep)
):
    """
    Check rate limit for the current request

    Args:
        request: FastAPI request object
        rate_limiter: Rate limiter instance

    Raises:
        HTTPException: If rate limit exceeded
    """
    # In TEST_MODE, bypass rate limiting entirely for deterministic tests
    try:
        if os.getenv("TEST_MODE", "").lower() == "true":
            return  # Skip enforcement in test environments
    except Exception:
        pass

    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Get endpoint key
    endpoint = f"{request.method}:{request.url.path}"

    # Check rate limit
    allowed, metadata = await rate_limiter.check_rate_limit(client_ip, endpoint)

    if not allowed:
        retry_after = 60
        try:
            if isinstance(metadata, dict):
                retry_after = int(metadata.get("retry_after", retry_after))
        except Exception:
            # Fallback to default if parsing fails
            retry_after = 60
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {retry_after} seconds",
            headers={"Retry-After": str(retry_after)}
        )


async def check_auth_rate_limit(
    request: Request,
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep)
):
    """
    Check stricter rate limit for authentication endpoints

    Args:
        request: FastAPI request object
        rate_limiter: Rate limiter instance

    Raises:
        HTTPException: If rate limit exceeded
    """
    # In TEST_MODE, bypass rate limiting entirely for deterministic tests
    try:
        if os.getenv("TEST_MODE", "").lower() == "true":
            return
    except Exception:
        pass

    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Use stricter limits for auth endpoints
    allowed, metadata = await rate_limiter.check_rate_limit(
        client_ip,
        "auth",
        limit=5,  # Stricter limit (5 requests per minute)
        window_minutes=1
    )
    retry_after = metadata.get("retry_after", 60)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many authentication attempts. Retry after {retry_after} seconds",
            headers={"Retry-After": str(retry_after)}
        )


# ---------------------------------------------------------------------------------
# RBAC resource-aware rate limit (stub - logs selected limits, no enforcement yet)

async def enforce_rbac_rate_limit(
    request: Request,
    resource: str,
    db_pool: DatabasePool = Depends(get_db_pool)
):
    """
    Resource-aware rate limit selector (stub).

    Reads the strictest configured limit for the current user from rbac_user_rate_limits
    and rbac_role_rate_limits. Currently logs selected limits without enforcing.
    """
    try:
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            # Unknown user context; skip
            return

        # User-level limit
        user_limit = None
        role_limit = None

        # SQLite vs Postgres param binding
        if db_pool.pool:  # Postgres
            user_limit = await db_pool.fetchone(
                "SELECT limit_per_min, burst FROM rbac_user_rate_limits WHERE user_id = $1 AND resource = $2",
                user_id, resource
            )
            # Get roles for user
            role_ids = await db_pool.fetchall(
                """
                SELECT role_id FROM user_roles
                WHERE user_id = $1 AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                """,
                user_id
            )
            if role_ids:
                role_ids_list = [r['role_id'] for r in role_ids]
                # Take the strictest (min) among role limits
                role_limit = await db_pool.fetchone(
                    """
                    SELECT MIN(limit_per_min) as limit_per_min, MIN(burst) as burst
                    FROM rbac_role_rate_limits WHERE role_id = ANY($1) AND resource = $2
                    """,
                    role_ids_list, resource
                )
        else:  # SQLite
            cur = await db_pool.acquire().__aenter__()
            try:
                c1 = await cur.execute(
                    "SELECT limit_per_min, burst FROM rbac_user_rate_limits WHERE user_id = ? AND resource = ?",
                    (user_id, resource)
                )
                user_limit = await c1.fetchone()
                c2 = await cur.execute(
                    """
                    SELECT MIN(rl.limit_per_min), MIN(rl.burst)
                    FROM rbac_role_rate_limits rl
                    JOIN user_roles ur ON ur.role_id = rl.role_id
                    WHERE ur.user_id = ? AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
                      AND rl.resource = ?
                    """,
                    (user_id, resource)
                )
                role_limit = await c2.fetchone()
            finally:
                await db_pool.acquire().__aexit__(None, None, None)

        # Choose strictest (lowest) effective limits
        candidates = []
        if user_limit:
            lp = user_limit[0] if not isinstance(user_limit, dict) else user_limit.get('limit_per_min')
            bp = user_limit[1] if not isinstance(user_limit, dict) else user_limit.get('burst')
            candidates.append((lp, bp))
        if role_limit:
            lp = role_limit[0] if not isinstance(role_limit, dict) else role_limit.get('limit_per_min')
            bp = role_limit[1] if not isinstance(role_limit, dict) else role_limit.get('burst')
            candidates.append((lp, bp))

        if candidates:
            limit_per_min = min([c[0] for c in candidates if c[0] is not None]) if any(c[0] for c in candidates) else None
            burst = min([c[1] for c in candidates if c[1] is not None]) if any(c[1] for c in candidates) else None
            logger.debug(f"RBAC rate-limit selected for user {user_id}, resource {resource}: rpm={limit_per_min}, burst={burst}")
        else:
            logger.debug(f"RBAC rate-limit: no configured limits for user {user_id}, resource {resource}")
    except Exception as e:
        logger.debug(f"RBAC rate-limit selection failed: {e}")


def rbac_rate_limit(resource: str):
    """Factory returning a dependency that logs selected RBAC limits for the given resource."""
    async def _dep(request: Request, db_pool: DatabasePool = Depends(get_db_pool)):
        await enforce_rbac_rate_limit(request, resource, db_pool)
    try:
        setattr(_dep, "_tldw_rate_limit_resource", resource)
    except Exception:
        pass
    return _dep


#######################################################################################################################
#
# Scoped Virtual-Key Enforcement

_VK_USAGE: dict = {}


def require_token_scope(
    scope: str,
    *,
    require_if_present: bool = True,
    require_schedule_match: bool = False,
    schedule_path_param: str = "schedule_id",
    schedule_header: str = "X-Workflow-Schedule-Id",
    allow_admin_bypass: bool = True,
    endpoint_id: Optional[str] = None,
    count_as: Optional[str] = None,
):
    """
    Create a dependency that enforces a scoped JWT ("virtual key").

    Behavior:
    - If the Authorization bearer token contains a 'scope' claim and require_if_present=True,
      it must match the provided `scope` or 403.
    - If `require_schedule_match=True` and the token includes 'schedule_id', the value must
      match the request path param `schedule_path_param` when present, or header `schedule_header`.
    - In single-user mode, or when no bearer token is present, this check is bypassed.
    - If `allow_admin_bypass=True`, admin users skip this enforcement.
    """
    async def _checker(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        jwt_service: JWTService = Depends(get_jwt_service_dep),
        db_pool: DatabasePool = Depends(get_db_pool),
    ) -> None:
        # Allow direct invocation (e.g., pytest unit tests) by resolving Depends defaults manually
        try:
            from fastapi.params import Depends as _Depends  # Local import to avoid top-level dependency

            if isinstance(jwt_service, _Depends) or jwt_service is None:
                jwt_service = await get_jwt_service_dep()
            if isinstance(db_pool, _Depends) or db_pool is None:
                db_pool = await get_db_pool()
        except Exception:
            # Best effort: if resolution fails, leave as-is; downstream code handles missing services.
            pass

        # If we have Authorization bearer, apply JWT-based checks; otherwise, try X-API-KEY checks
        if credentials:
            token = credentials.credentials
            try:
                payload = jwt_service.decode_access_token(token)
            except Exception:
                return None
            # Optional admin bypass based on token role claim
            try:
                if allow_admin_bypass and str(payload.get("role", "")) == "admin":
                    return None
            except Exception:
                pass
            tok_scope = str(payload.get("scope") or "").strip()
            if tok_scope and require_if_present and tok_scope != str(scope):
                raise HTTPException(status_code=403, detail="Forbidden: invalid token scope")

            # Enforce endpoint allowlist
            try:
                if endpoint_id:
                    allowed_eps = payload.get("allowed_endpoints")
                    if isinstance(allowed_eps, list) and allowed_eps:
                        if endpoint_id not in [str(x) for x in allowed_eps]:
                            raise HTTPException(status_code=403, detail="Forbidden: endpoint not permitted for token")
            except HTTPException:
                raise
            except Exception:
                pass

            # Enforce HTTP method allowlist
            try:
                am = payload.get("allowed_methods")
                if isinstance(am, list) and am:
                    method = str(getattr(request, "method", "")).upper()
                    if method and method not in [str(x).upper() for x in am]:
                        raise HTTPException(status_code=403, detail="Forbidden: method not permitted for token")
            except HTTPException:
                raise
            except Exception:
                pass

            # Enforce path prefix allowlist
            try:
                ap = payload.get("allowed_paths")
                if isinstance(ap, list) and ap:
                    path = getattr(getattr(request, "url", None), "path", None) or getattr(request, "scope", {}).get("path")
                    if path and not any(str(path).startswith(str(pfx)) for pfx in ap):
                        raise HTTPException(status_code=403, detail="Forbidden: path not permitted for token")
            except HTTPException:
                raise
            except Exception:
                pass

            # Quotas: simple per-token counters (DB-backed; fallback to process-local)
            try:
                if count_as:
                    jti = payload.get("jti")
                    if jti:
                        key = (f"jwt:{jti}", str(count_as))
                        max_calls = None
                        if str(count_as) == "run":
                            max_calls = payload.get("max_runs")
                        if max_calls is None:
                            max_calls = payload.get("max_calls")
                        if isinstance(max_calls, int) and max_calls >= 0:
                            try:
                                from tldw_Server_API.app.core.AuthNZ.quotas import increment_and_check_jwt_quota
                                allowed, _cnt = await increment_and_check_jwt_quota(
                                    db_pool=db_pool,
                                    jti=str(jti),
                                    counter_type=str(count_as),
                                    limit=int(max_calls),
                                )
                                if not allowed:
                                    raise HTTPException(status_code=403, detail="Forbidden: token quota exceeded")
                            except HTTPException:
                                raise
                            except Exception:
                                cur = int(_VK_USAGE.get(key, 0))
                                if cur >= int(max_calls):
                                    raise HTTPException(status_code=403, detail="Forbidden: token quota exceeded")
                                _VK_USAGE[key] = cur + 1
            except HTTPException:
                raise
            except Exception:
                pass

            if require_schedule_match:
                try:
                    tok_sid = payload.get("schedule_id")
                except Exception:
                    tok_sid = None
                expected = None
                try:
                    expected = request.path_params.get(schedule_path_param)
                except Exception:
                    expected = None
                if expected is None:
                    try:
                        expected = request.headers.get(schedule_header)
                    except Exception:
                        expected = None
                if tok_sid is not None and expected is not None and str(tok_sid) != str(expected):
                    raise HTTPException(status_code=403, detail="Forbidden: schedule scope mismatch")

            return None

        # Fallback: X-API-KEY constraints enforcement (if header present and key is valid)
        try:
            api_key = request.headers.get("X-API-KEY") if getattr(request, "headers", None) else None
        except Exception:
            api_key = None
        if api_key:
            try:
                from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
                api_mgr = await get_api_key_manager()
                client_ip = request.client.host if getattr(request, "client", None) else None
                info = await api_mgr.validate_api_key(api_key=api_key, ip_address=client_ip)
                if not info:
                    # Let upstream auth fail; do not enforce here
                    return None
                # Admin bypass via scope 'admin'
                if allow_admin_bypass and str(info.get("scope", "")).lower() == "admin":
                    return None
                # Allowed endpoints from llm_allowed_endpoints
                allowed_eps = info.get("llm_allowed_endpoints")
                if isinstance(allowed_eps, str):
                    import json as _json
                    try:
                        allowed_eps = _json.loads(allowed_eps)
                    except Exception:
                        allowed_eps = None
                if endpoint_id and isinstance(allowed_eps, list) and allowed_eps:
                    if endpoint_id not in [str(x) for x in allowed_eps]:
                        raise HTTPException(status_code=403, detail="Forbidden: endpoint not permitted for API key")
                # Metadata-based constraints
                meta = info.get("metadata")
                if isinstance(meta, str):
                    import json as _json
                    try:
                        meta = _json.loads(meta)
                    except Exception:
                        meta = None
                if isinstance(meta, dict):
                    am = meta.get("allowed_methods")
                    if isinstance(am, list) and am:
                        method = str(getattr(request, "method", "")).upper()
                        if method and method not in [str(x).upper() for x in am]:
                            raise HTTPException(status_code=403, detail="Forbidden: method not permitted for API key")
                    ap = meta.get("allowed_paths")
                    if isinstance(ap, list) and ap:
                        path = getattr(getattr(request, "url", None), "path", None) or getattr(request, "scope", {}).get("path")
                        if path and not any(str(path).startswith(str(pfx)) for pfx in ap):
                            raise HTTPException(status_code=403, detail="Forbidden: path not permitted for API key")
                    if count_as:
                        key_id = info.get("id")
                        if key_id is not None:
                            quota = None
                            if str(count_as) == "run":
                                quota = meta.get("max_runs")
                            if quota is None:
                                quota = meta.get("max_calls")
                            if isinstance(quota, int) and quota >= 0:
                                try:
                                    from tldw_Server_API.app.core.AuthNZ.quotas import increment_and_check_api_key_quota
                                    allowed, _cnt = await increment_and_check_api_key_quota(
                                        db_pool=db_pool,
                                        api_key_id=int(key_id),
                                        counter_type=str(count_as),
                                        limit=int(quota),
                                    )
                                    if not allowed:
                                        raise HTTPException(status_code=403, detail="Forbidden: API key quota exceeded")
                                except HTTPException:
                                    raise
                                except Exception:
                                    key = (f"apikey:{key_id}", str(count_as))
                                    cur = int(_VK_USAGE.get(key, 0))
                                    if cur >= int(quota):
                                        raise HTTPException(status_code=403, detail="Forbidden: API key quota exceeded")
                                    _VK_USAGE[key] = cur + 1
            except HTTPException:
                raise
            except Exception:
                # Best-effort: do not block if metadata not available
                return None
        return None

    try:
        setattr(_checker, "_tldw_endpoint_id", endpoint_id)
        setattr(_checker, "_tldw_scope_name", scope)
    except Exception:
        pass

    return _checker
#
# End of auth_deps.py
#######################################################################################################################
