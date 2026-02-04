# auth_deps.py
# Description: FastAPI dependency injection for authentication services
#
import asyncio
import inspect
import os
import re
import threading
import time
from collections.abc import AsyncGenerator, Awaitable, Mapping
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from weakref import WeakKeyDictionary

#
# 3rd-party imports
from fastapi import Depends, Header, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.AuthNZ.auth_governor import get_auth_governor
from tldw_Server_API.app.core.AuthNZ.auth_principal_resolver import (
    get_auth_principal as _resolve_auth_principal,
)

#
# Local imports
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    InvalidTokenError,
    TokenExpiredError,
)
from tldw_Server_API.app.core.AuthNZ.ip_allowlist import (
    is_single_user_ip_allowed,
    resolve_client_ip,
)
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService, get_jwt_service
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService, get_password_service
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal, is_single_user_principal
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter, get_rate_limiter
from tldw_Server_API.app.core.AuthNZ.session_manager import SessionManager, get_session_manager
from tldw_Server_API.app.core.AuthNZ.settings import (
    get_settings,
    is_single_user_mode,
    is_single_user_profile_mode,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import (
    authenticate_api_key_user,
    verify_jwt_and_fetch_user,
)
from tldw_Server_API.app.core.DB_Management.scope_context import set_scope
from tldw_Server_API.app.core.exceptions import InactiveUserError
from tldw_Server_API.app.core.External_Sources.connectors_service import get_policy
from tldw_Server_API.app.core.External_Sources.policy import get_default_policy_from_env
from tldw_Server_API.app.core.MCP_unified.monitoring import metrics
from tldw_Server_API.app.core.testing import is_test_mode as _is_test_mode
from tldw_Server_API.app.services.registration_service import RegistrationService, get_registration_service
from tldw_Server_API.app.services.storage_quota_service import StorageQuotaService, get_storage_service

# Test stub shared state (persist across dependency calls under TEST_MODE/pytest)
_TEST_SESSION_STATE: dict = {"sid": 1000, "sessions": {}}
_TEST_SESSION_LOCKS: "WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = WeakKeyDictionary()
_TEST_SESSION_LOCK_GUARD = threading.Lock()
_TEST_SESSION_STATE_GUARD = threading.Lock()
_TEST_EPHEMERAL_STATE: dict = {"values": {}}
_TEST_EPHEMERAL_STATE_GUARD = threading.Lock()

_SENSITIVE_USER_KEY_PATTERN = re.compile(
    r"(password|secret|token|api[_-]?key|ssn|totp|otp|mfa|backup_codes|recovery_codes)",
    re.IGNORECASE,
)


def _public_user_dict(user: Mapping[str, Any]) -> dict[str, Any]:
    """
    Return a sanitized shallow copy of a user mapping.

    The AuthNZ stack may temporarily cache full database rows (including secrets)
    in `request.state._auth_user`. This helper strips common secret-bearing keys
    (passwords, tokens, secrets, API keys, SSNs) so dependency returns never
    expose sensitive fields.
    """
    safe: dict[str, Any] = {}
    for key, value in dict(user).items():
        if isinstance(key, str) and _SENSITIVE_USER_KEY_PATTERN.search(key):
            continue
        safe[key] = value
    return safe


def _looks_like_jwt(token: Optional[str]) -> bool:
    if not isinstance(token, str):
        return False
    return token.count(".") == 2


async def _authenticate_api_key_from_request(request: Request, api_key: str) -> dict[str, Any]:
    test_mode = os.getenv("TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    if test_mode:
        # SECURITY: Warn loudly about TEST_MODE and block in production unless explicitly allowed
        allow_test_in_prod = os.getenv("ALLOW_TEST_MODE_IN_PRODUCTION", "").strip().lower() in {"1", "true", "yes", "on"}
        environment = os.getenv("ENVIRONMENT", "").strip().lower()
        prod_flag = os.getenv("tldw_production", "false").strip().lower() in {"1", "true", "yes", "on", "y"}
        is_production = environment in {"production", "prod"} or prod_flag
        if is_production:
            if not allow_test_in_prod:
                logger.critical(
                    "TEST_MODE is enabled in production environment! "
                    "This is a SEVERE security risk. Set ALLOW_TEST_MODE_IN_PRODUCTION=1 to override (NOT recommended)."
                )
                raise HTTPException(
                    status_code=500,
                    detail="Server configuration error"
                )
            else:
                logger.warning(
                    "TEST_MODE is enabled in production with explicit override. "
                    "This bypasses normal authentication and should only be used for debugging."
                )
        else:
            logger.debug("TEST_MODE is enabled for non-production environment")
        try:
            settings = get_settings()
        except Exception:
            settings = None
        allowed_keys: set[str] = set()
        test_key = os.getenv("SINGLE_USER_TEST_API_KEY")
        if test_key:
            allowed_keys.add(test_key)
        if settings and settings.SINGLE_USER_API_KEY:
            allowed_keys.add(settings.SINGLE_USER_API_KEY)
        if api_key in allowed_keys:
            client_ip = resolve_client_ip(request, settings)
            if settings and settings.AUTH_MODE == "single_user":
                if not is_single_user_ip_allowed(client_ip, settings):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or missing API Key",
                    )
            try:
                if settings and isinstance(settings.DATABASE_URL, str) and settings.DATABASE_URL.startswith("sqlite:///"):
                    from pathlib import Path as _Path

                    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables as _ensure_authnz_tables
                    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
                    _ensure_authnz_tables(_Path(db_path))
            except Exception as _ensure_err:
                logger.debug("AuthNZ test fallback: ensure_authnz_tables skipped/failed: {}", _ensure_err)
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
            user = _public_user_dict(user)
            try:
                request.state.user_id = fixed_id
                request.state.team_ids = []
                request.state.org_ids = []
            except Exception as state_exc:
                logger.debug(
                    "API key test-mode path: unable to attach state context: {}",
                    state_exc,
                )
            return user
    try:
        # Force API key manager resolution through this module so tests can
        # monkeypatch `auth_deps.get_api_key_manager` and assert error logging
        # does not leak exception messages outside TEST_MODE.
        await get_api_key_manager()
        user_obj = await authenticate_api_key_user(request, api_key)
        # Normalize User model to a plain dict for response serialization.
        if hasattr(user_obj, "model_dump"):
            user_dict = user_obj.model_dump()  # type: ignore[call-arg]
        elif hasattr(user_obj, "dict"):
            user_dict = user_obj.dict()  # type: ignore[call-arg]
        elif isinstance(user_obj, Mapping):
            user_dict = dict(user_obj)
        else:
            user_dict = {"id": getattr(user_obj, "id", None)}
        return _public_user_dict(user_dict)
    except HTTPException:
        # Propagate explicit HTTP errors unchanged (401/403, etc.)
        raise
    except Exception as e:
        if _is_test_mode():
            logger.exception("API key authentication error in get_current_user (TEST_MODE)")
        else:
            logger.error(
                "API key authentication error in get_current_user (type={})",
                type(e).__name__,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate API key",
        )


def _get_test_session_lock() -> asyncio.Lock:
    """
    Lazily initialize and return a test session lock scoped to the current event loop.

    The lock is created on first use within the currently running event loop
    instead of at module import time to avoid binding it to the wrong loop
    in test environments.
    """
    loop = asyncio.get_running_loop()
    with _TEST_SESSION_LOCK_GUARD:
        lock = _TEST_SESSION_LOCKS.get(loop)
        if lock is None:
            lock = asyncio.Lock()
            _TEST_SESSION_LOCKS[loop] = lock
        return lock


def reset_test_ephemeral_state() -> None:
    """Clear the test-only in-process ephemeral KV store (pytest/TEST_MODE)."""
    with _TEST_EPHEMERAL_STATE_GUARD:
        _TEST_EPHEMERAL_STATE["values"].clear()

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
    org_ids: Optional[list[int]],
    team_ids: Optional[list[int]],
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
        logger.debug(
            "Unable to establish content scope context: {}",
            exc,
        )

async def get_db_transaction() -> AsyncGenerator[Any, None]:
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

        # NOTE: This adapter normalizes asyncpg-style ($1, fetch*) and SQLite-style
        # query/return semantics for tests. If other modules need similar behavior,
        # it can be extracted into the DB_Management layer.
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
                    except Exception as exc:
                        logger.debug(
                            "Test DB adapter: sqlite commit failed: {}",
                            exc,
                        )
                        raise
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
                    except Exception as exc:
                        logger.debug(
                            "Test DB adapter: sqlite commit failed: {}",
                            exc,
                        )
                        raise

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
        import os as _os
        import sys as _sys

        force_real = _os.getenv("AUTHNZ_FORCE_REAL_SESSION_MANAGER", "").lower() in ("1", "true", "yes")
        if not force_real and (_os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes") or "pytest" in _sys.modules):
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
                    async with _get_test_session_lock():
                        with _TEST_SESSION_STATE_GUARD:
                            _TEST_SESSION_STATE["sid"] += 1
                            sid = _TEST_SESSION_STATE["sid"]
                            now = datetime.now(timezone.utc)
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

                async def update_session_tokens(
                    self,
                    _session_id: int = 0,
                    _access_token: str = "",
                    _refresh_token: str = "",
                    **_kwargs,
                ):
                    # No-op in stub
                    return True

                async def refresh_session(self, *_args, **kwargs):
                    return {
                        "session_id": kwargs.get("session_id") or 1,
                        "user_id": kwargs.get("user_id") or 1,
                        "expires_at": datetime.now(timezone.utc).isoformat(),
                    }

                async def get_user_sessions(self, user_id: int):
                    async with _get_test_session_lock():
                        with _TEST_SESSION_STATE_GUARD:
                            sessions = list(_TEST_SESSION_STATE["sessions"].values())
                        return [s for s in sessions if s.get("user_id") == user_id]

                async def revoke_session(self, session_id: int, *_args, **_kwargs):
                    async with _get_test_session_lock():
                        with _TEST_SESSION_STATE_GUARD:
                            sess = _TEST_SESSION_STATE["sessions"].get(session_id)
                            if sess is None:
                                return False
                            sess["is_revoked"] = True
                            sess["is_active"] = False
                            return True

                async def revoke_all_user_sessions(self, user_id: int):
                    async with _get_test_session_lock():
                        with _TEST_SESSION_STATE_GUARD:
                            changed = 0
                            for s in _TEST_SESSION_STATE["sessions"].values():
                                if s.get("user_id") == user_id:
                                    s["is_revoked"] = True
                                    s["is_active"] = False
                                    changed += 1
                            return changed

                async def store_ephemeral_value(self, key: str, value: str, ttl_seconds: int) -> None:
                    ttl = max(int(ttl_seconds), 1)
                    now = time.monotonic()
                    expires_at = now + ttl
                    with _TEST_EPHEMERAL_STATE_GUARD:
                        # Opportunistic pruning to keep long-running test suites bounded.
                        values = _TEST_EPHEMERAL_STATE["values"]
                        for k, (_v, exp) in list(values.items()):
                            if exp <= now:
                                values.pop(k, None)
                        values[key] = (value, expires_at)

                async def get_ephemeral_value(self, key: str) -> Optional[str]:
                    now = time.monotonic()
                    with _TEST_EPHEMERAL_STATE_GUARD:
                        entry = _TEST_EPHEMERAL_STATE["values"].get(key)
                        if not entry:
                            return None
                        value, expires_at = entry
                        if expires_at <= now:
                            _TEST_EPHEMERAL_STATE["values"].pop(key, None)
                            return None
                        return value

                async def delete_ephemeral_value(self, key: str) -> None:
                    with _TEST_EPHEMERAL_STATE_GUARD:
                        _TEST_EPHEMERAL_STATE["values"].pop(key, None)

            return _StubSessionManager()  # type: ignore[return-value]
    except Exception as exc:
        logger.debug(
            "get_session_manager_dep: test stub resolution failed; falling back to real SessionManager: {}",
            exc,
        )
    return await get_session_manager()


async def get_rate_limiter_dep(request: Request) -> RateLimiter:
    """Get AuthNZ rate limiter dependency (lockout only)."""
    _ = request
    return get_rate_limiter()


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
) -> dict[str, Any]:
    """
    Resolve and return the current authenticated user.

    Supports Bearer JWT authentication and API keys via `X-API-KEY` or
    Authorization Bearer (non-JWT tokens). If an upstream dependency already
    populated `request.state.auth` and
    `request.state._auth_user`, this function reuses that request-scoped cache to
    avoid repeating token/API-key validation within a single request.

    Args:
        request: FastAPI request object.
        response: FastAPI response object.
        credentials: Bearer token from Authorization header (if present).
        session_manager: Session manager instance.
        db_pool: Database pool instance.
        x_api_key: API key from `X-API-KEY` header (if present).

    Returns:
        User dictionary with all user information.

    Raises:
        HTTPException: If authentication fails.
    """
    # TEST_MODE diagnostics: log auth header presence
    try:
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            logger.info(
                "get_current_user: has_bearer={} has_api_key={} path={}",
                bool(credentials),
                bool(x_api_key),
                request.url.path,
            )
    except Exception as exc:
        logger.debug(
            "get_current_user: TEST_MODE auth header diagnostics failed; continuing without diagnostics: {}",
            exc,
        )

    # Fast-path: if an AuthPrincipal/AuthContext has already been resolved for this
    # request (e.g., via get_auth_principal or budget guards), reuse the cached user
    # representation instead of re-running JWT/API-key logic.
    try:
        existing_ctx = getattr(request.state, "auth", None)
        cached_user = getattr(request.state, "_auth_user", None)
        if isinstance(existing_ctx, AuthContext) and cached_user is not None:
            logger.debug("get_current_user: Reusing cached AuthPrincipal/_auth_user from request.state.")
            # Validate cached user type before processing; if it is not a mapping or
            # Pydantic-style model, fall through to standard auth.
            if not (isinstance(cached_user, Mapping) or hasattr(cached_user, "model_dump") or hasattr(cached_user, "dict")):
                logger.debug(
                    "get_current_user: cached _auth_user is not a mapping/Pydantic model; "
                    "skipping fast-path reuse."
                )
            else:
                # Normalize to a plain dict to preserve existing return shape
                if isinstance(cached_user, Mapping):
                    user_dict: dict[str, Any] = dict(cached_user)
                else:
                    dump = getattr(cached_user, "model_dump", None) or getattr(cached_user, "dict", None)
                    user_dict = dict(dump())
                safe_user = _public_user_dict(user_dict)
                # If the cached user was a full DB row mapping, replace the cache with
                # the sanitized representation to avoid re-exposing secrets later in
                # this request.
                try:
                    if isinstance(cached_user, Mapping):
                        request.state._auth_user = safe_user
                except Exception as exc:
                    logger.debug(
                        "Fast-path: unable to update request.state._auth_user with sanitized user: {}",
                        exc,
                    )
                # Ensure request.state.user_id is populated for downstream consumers
                try:
                    uid = safe_user.get("id")
                    if uid is not None:
                        request.state.user_id = int(uid)
                except Exception as exc:
                    logger.debug(
                        "Fast-path: unable to attach user_id to request.state: {}",
                        exc,
                    )
                # Scope context should already be set by upstream auth, but be defensive.
                # Prefer org/team ids from the existing principal, with request.state as fallback.
                try:
                    principal = getattr(existing_ctx, "principal", None)
                    org_ids = getattr(principal, "org_ids", None) if principal is not None else None
                    team_ids = getattr(principal, "team_ids", None) if principal is not None else None
                    _activate_scope_context(
                        request,
                        user_id=getattr(principal, "user_id", None),
                        org_ids=org_ids if org_ids is not None else getattr(request.state, "org_ids", None),
                        team_ids=team_ids if team_ids is not None else getattr(request.state, "team_ids", None),
                        is_admin=bool(getattr(principal, "is_admin", False)),
                    )
                except Exception as exc:
                    logger.debug(
                        "Fast-path: unable to (re)establish content scope context: {}",
                        exc,
                    )
                return safe_user
    except Exception as exc:
        # Fall through to standard auth behavior if any issue occurs
        logger.debug(
            "get_current_user: Fast-path AuthContext reuse failed, falling back to standard auth: {}",
            exc,
        )

    # Single-user compatibility: accept Authorization Bearer as API key when no X-API-KEY is present.
    if credentials and not x_api_key:
        try:
            settings = get_settings()
        except Exception:
            settings = None
        if settings and getattr(settings, "AUTH_MODE", None) == "single_user":
            x_api_key = credentials.credentials
            credentials = None

    bearer_token = credentials.credentials if credentials else None
    bearer_is_jwt = _looks_like_jwt(bearer_token) if bearer_token else False

    api_key_candidate = x_api_key
    if not api_key_candidate and bearer_token and not bearer_is_jwt:
        api_key_candidate = bearer_token

    # If Authorization is absent or not a JWT but API key present, attempt API-key auth.
    if api_key_candidate and (not credentials or not bearer_is_jwt):
        return await _authenticate_api_key_from_request(request, api_key_candidate)

    # Otherwise, require Bearer token
    if not credentials:
        # TEST_MODE: surface why we failed
        extra_headers = {"WWW-Authenticate": "Bearer"}
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            try:
                present_headers = ",".join(h for h in ("Authorization", "X-API-KEY") if request.headers.get(h)) or "none"
                extra_headers["X-TLDW-Auth-Reason"] = "missing-bearer"
                extra_headers["X-TLDW-Auth-Headers"] = present_headers
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "get_current_user: failed to set TEST_MODE missing-bearer diagnostic headers: {}",
                    exc,
                )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers=extra_headers
        )

    # Bearer token path (JWT-based authentication)
    token = credentials.credentials
    try:
        # Delegate JWT validation and user enrichment to the shared helper so
        # roles/permissions/admin flags stay aligned with AuthPrincipal/User flows.
        user_obj = await verify_jwt_and_fetch_user(request, token)
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        ) from exc
    except HTTPException as exc:
        # If a JWT fails but an explicit X-API-KEY is present, fall back to API key auth.
        if exc.status_code == status.HTTP_401_UNAUTHORIZED and x_api_key:
            try:
                return await _authenticate_api_key_from_request(request, x_api_key)
            except HTTPException:
                # If API key auth fails, continue with the JWT failure handling below.
                pass
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            # Normalize 401 semantics for callers: detail must contain
            # "Authentication required" and include WWW-Authenticate header.
            extra_headers = {"WWW-Authenticate": "Bearer"}
            if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
                try:
                    extra_headers["X-TLDW-Auth-Reason"] = f"auth-error:{exc.detail}"
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "get_current_user: failed to set TEST_MODE auth-error diagnostic header: {}",
                        exc,
                    )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers=extra_headers,
            ) from exc
        # Propagate non-401 HTTP errors unchanged.
        raise
    except Exception as e:
        if _is_test_mode():
            logger.exception("Authentication error in get_current_user (TEST_MODE)")
        else:
            logger.error(
                "Authentication error in get_current_user (type={})",
                type(e).__name__,
            )
        extra_headers = {"WWW-Authenticate": "Bearer"}
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            try:
                extra_headers["X-TLDW-Auth-Reason"] = f"auth-error:{e}"
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "get_current_user: failed to set TEST_MODE auth-error diagnostic header: {}",
                    exc,
                )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers=extra_headers,
        ) from e

    # Successful JWT authentication: normalize the User model to a public dict.
    if hasattr(user_obj, "model_dump"):
        user_dict = user_obj.model_dump()  # type: ignore[call-arg]
    elif hasattr(user_obj, "dict"):
        user_dict = user_obj.dict()  # type: ignore[call-arg]
    elif isinstance(user_obj, Mapping):
        user_dict = dict(user_obj)
    else:
        user_dict = {"id": getattr(user_obj, "id", None)}

    safe_user = _public_user_dict(user_dict)

    # Ensure request.state.user_id is populated for downstream consumers, even
    # though verify_jwt_and_fetch_user already attempts to do this.
    try:
        uid = safe_user.get("id")
        if uid is not None:
            request.state.user_id = int(uid)
    except Exception as state_exc:
        logger.debug(
            "JWT path: unable to attach user_id from verify_jwt_and_fetch_user: {}",
            state_exc,
        )

    return safe_user


#######################################################################################################################
#
# Claim-First Principal Dependencies


async def get_auth_principal(
    request: Request,
) -> AuthPrincipal:
    """
    FastAPI dependency that returns the AuthPrincipal for the current request.

    This delegates to the core auth_principal_resolver and reuses any existing
    AuthContext attached to request.state.auth when present.
    """
    principal = await _resolve_auth_principal(request)
    try:
        from tldw_Server_API.app.services.admin_system_ops_service import (
            get_maintenance_state as _get_maintenance_state,
        )

        state = _get_maintenance_state()
        if state.get("enabled"):
            if principal.is_admin:
                return principal
            allowlist_ids = set()
            for val in state.get("allowlist_user_ids") or []:
                try:
                    if val is not None:
                        allowlist_ids.add(int(val))
                except (TypeError, ValueError):
                    continue
            allowlist_emails = {
                str(val).strip().lower()
                for val in (state.get("allowlist_emails") or [])
                if val
            }
            if principal.user_id is not None and principal.user_id in allowlist_ids:
                return principal
            if principal.email and principal.email.lower() in allowlist_emails:
                return principal
            message = state.get("message") or "Service temporarily unavailable for maintenance."
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "maintenance_mode", "message": message},
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.debug("Maintenance guard skipped: {}", exc)
    return principal


def require_permissions(*permissions: str) -> Callable[[AuthPrincipal], Awaitable[AuthPrincipal]]:
    """
    Dependency factory that enforces required permission claims on the principal.

    Admin principals (principal.is_admin) are allowed regardless of specific
    permissions. On failure, raises HTTP 403 with a descriptive message.

    Note: Uses AND semantics - the principal must have all specified
    permissions (unlike require_roles, which uses OR semantics for roles).
    """

    perms = [str(p) for p in permissions if str(p).strip()]

    async def _checker(principal: AuthPrincipal = Depends(get_auth_principal)) -> AuthPrincipal:  # noqa: B008
        if principal.is_admin:
            return principal
        missing = [p for p in perms if p not in principal.permissions]
        if missing:
            if _is_test_mode():
                logger.debug("require_permissions denied principal; missing={}", missing)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: missing {', '.join(missing)}",
            )
        return principal

    return _checker


def require_api_key_scope(
    *scopes: str,
    allow_jwt_bypass: bool = True,
    allow_admin_bypass: bool = True,
) -> Callable[..., Awaitable[AuthPrincipal]]:
    """
    Dependency factory that enforces API key scope requirements.

    Creates a FastAPI dependency that verifies the authenticated principal
    has one of the required scopes. This is specifically for API key scope
    enforcement (separate from JWT token scopes or role-based permissions).
    If no scopes are provided, no additional scope constraint is applied.

    Args:
        *scopes: One or more scope strings that satisfy the requirement (OR logic).
                 Valid values: "read", "write", "admin", "service"
        allow_jwt_bypass: If True, JWT-authenticated users bypass this check (default: True)
        allow_admin_bypass: If True, principals with is_admin=True bypass this check (default: True)

    Returns:
        Dependency function that raises HTTP 403 if scope requirement not met

    Example:
        @router.get("/media/{id}")
        async def get_media(
            id: int,
            _: AuthPrincipal = Depends(require_api_key_scope("read")),
        ):
            ...

        @router.post("/media/process")
        async def process_media(
            request: MediaProcessRequest,
            _: AuthPrincipal = Depends(require_api_key_scope("write", "admin")),
        ):
            ...
    """
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import has_scope, normalize_scope

    required_scopes = frozenset(s.strip().lower() for s in scopes if s)

    async def _checker(
        request: Request,
        principal: AuthPrincipal = Depends(get_auth_principal),  # noqa: B008
    ) -> AuthPrincipal:
        if not required_scopes:
            return principal

        # Admin bypass
        if allow_admin_bypass and principal.is_admin:
            # AUDIT: Log when admin bypasses API key scope check for security visibility
            logger.info(
                "Admin user {} bypassing API key scope check for scopes {} on endpoint {}",
                principal.user_id, list(required_scopes), request.url.path
            )
            return principal

        # JWT bypass (for JWT-authenticated users without API key context)
        if allow_jwt_bypass and principal.kind == "user" and principal.api_key_id is None:
            return principal

        # API key scope check
        if principal.api_key_id is not None:
            # Retrieve scope from request.state (populated during auth)
            key_scope = getattr(request.state, "_api_key_scope", None)
            if key_scope is None:
                # Fallback: allow only for explicit single-user principals.
                if getattr(principal, "subject", None) == "single_user":
                    return principal
                # In multi-user mode, missing scope is an error
                if _is_test_mode():
                    logger.debug("require_api_key_scope: scope info unavailable for key {}", principal.api_key_id)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="API key scope information unavailable",
                )

            key_scopes = normalize_scope(key_scope)

            if not any(has_scope(key_scopes, rs) for rs in required_scopes):
                if _is_test_mode():
                    logger.debug(
                        "require_api_key_scope denied: key_scopes={}, required_any_of={}",
                        key_scopes, required_scopes
                    )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"API key lacks required scope. Required: {', '.join(required_scopes)}",
                )

        return principal

    return _checker


def require_roles(*roles: str) -> Callable[[AuthPrincipal], Awaitable[AuthPrincipal]]:
    """
    Dependency factory that enforces required role claims on the principal.

    Admin principals (principal.is_admin) are allowed regardless of specific
    roles. On failure, raises HTTP 403 with a descriptive message.

    Note: Uses OR semantics - the principal must have at least one of the
    specified roles (unlike require_permissions, which requires all listed
    permissions).
    """

    role_list = [str(r) for r in roles if str(r).strip()]

    async def _checker(principal: AuthPrincipal = Depends(get_auth_principal)) -> AuthPrincipal:  # noqa: B008
        if principal.is_admin:
            return principal
        if not role_list:
            return principal
        if not any(r in principal.roles for r in role_list):
            if _is_test_mode():
                logger.debug("require_roles denied principal; required_any_of={}", role_list)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(role_list)}",
            )
        return principal

    return _checker


async def require_service_principal(
    principal: AuthPrincipal = Depends(get_auth_principal),  # noqa: B008
) -> AuthPrincipal:
    """
    Dependency that enforces a service principal.

    Behavior:
    - Relies on get_auth_principal for authentication (401 on failure).
    - When a principal is present but principal.kind is not "service", raises
      HTTP 403 with a stable, descriptive message.
    - When principal.kind == "service", returns the principal unchanged.
    """
    if principal.kind != "service":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service principal required",
        )
    return principal


async def get_current_active_user(
    current_user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
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


async def get_user_org_policy(
    db: Any = Depends(get_db_transaction),  # noqa: B008
    principal: AuthPrincipal = Depends(get_auth_principal),  # noqa: B008
    current_user: dict[str, Any] = Depends(get_current_active_user),  # noqa: B008
) -> dict[str, Any]:
    """
    Deprecated compatibility shim for user-dict org policy lookups.

    New code should prefer ``get_org_policy_from_principal``. This helper
    now delegates to the claim-first resolver so org policy resolution stays
    consistent across all authentication flows.
    """
    return await get_org_policy_from_principal(
        db=db,
        principal=principal,
        current_user=current_user,
    )


async def _load_org_policy(db: Any, org_id: int) -> dict[str, Any]:
    """
    Internal helper to load an organization policy with consistent error handling.
    """
    try:
        pol = await get_policy(db, org_id)
    except Exception as exc:
        logger.exception(
            "Failed to load organization policy for org_id={}",
            org_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load organization policy",
        ) from exc
    else:
        if not pol:
            pol = get_default_policy_from_env(org_id)
        return pol


async def get_org_policy_from_principal(
    db: Any = Depends(get_db_transaction),  # noqa: B008
    principal: AuthPrincipal = Depends(get_auth_principal),  # noqa: B008
    current_user: dict[str, Any] = Depends(get_current_active_user),  # noqa: B008
) -> dict[str, Any]:
    """
    Resolve organization policy primarily from ``AuthPrincipal``, with fallbacks.

    Preference order:
    1. First org_id in ``principal.org_ids`` (claim-first).
    2. First org_id from ``current_user["org_memberships"]`` (legacy user dict).
    3. Synthetic org_id=1 in single-user mode (for environments without orgs).
    4. HTTP 400 when no organization can be resolved.

    This helper is the principal-first counterpart to ``get_user_org_policy`` and
    is intended for new code paths that already depend on ``get_auth_principal``.
    """
    def _should_use_synthetic_single_user_org(p: AuthPrincipal) -> bool:
        """
        Decide whether to fall back to a synthetic org_id=1 for single-user.

        Behaviour:
        - When ORG_POLICY_SINGLE_USER_PRINCIPAL is unset/true:
          prefer principal/profile-driven behaviour and only treat the
          environment as single-user for org-policy purposes when:
            * PROFILE indicates a single-user profile, and
            * the principal is explicitly marked as the single-user profile (subject/helper).
        - When the flag is explicitly disabled (\"0\"/\"false\"/\"off\"):
          preserve legacy behaviour using mode/profile helpers
          (is_single_user_mode or is_single_user_profile_mode).
        """
        flag = os.getenv("ORG_POLICY_SINGLE_USER_PRINCIPAL", "").strip().lower()
        if flag in {"0", "false", "off"}:
            # Explicit compatibility mode: defer to legacy mode/profile helpers.
            try:
                return bool(is_single_user_mode() or is_single_user_profile_mode())
            except Exception:
                return False

        try:
            single_profile = is_single_user_profile_mode()
        except Exception:
            single_profile = False

        if not single_profile:
            return False
        # Principal-first: only explicit single-user principals qualify. For the
        # org-policy fallback, we deliberately require the principal to be
        # tagged with subject \"single_user\" instead of relying on numeric
        # fixed-id fallbacks to avoid misclassifying arbitrary principals that
        # happen to share the single-user id.
        try:
            return getattr(p, "subject", None) == "single_user"
        except Exception:
            return False

    # 1) Claim-first: use principal.org_ids when available.
    org_ids = list(getattr(principal, "org_ids", []) or [])
    if org_ids:
        org_id = org_ids[0]
    else:
        # 2) Fallback to user org_memberships for compatibility.
        memberships = current_user.get("org_memberships") or []
        if memberships:
            org_id = memberships[0].get("org_id")
        elif _should_use_synthetic_single_user_org(principal):
            # Single-user environment: synthetic org_id=1 to mirror legacy behaviour.
            org_id = 1
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User has no organization memberships",
            )

    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization membership is missing org_id",
        )
    return await _load_org_policy(db, org_id)


async def require_admin(
    current_user: dict[str, Any] = Depends(get_current_active_user)  # noqa: B008
) -> dict[str, Any]:
    """
    Require admin role for access (legacy shim).

    This dependency is retained for backwards compatibility with older
    routes and tests that still rely on a user-dict based admin check.
    New endpoints MUST NOT use this helper and should instead depend on
    `get_auth_principal` together with `require_roles("admin")` and/or
    `require_permissions(...)` for claim-first authorization.

    Args:
        current_user: Current active user

    Returns:
        User dictionary if admin

    Raises:
        HTTPException: If user is not admin
    """
    # Prefer explicit admin-style claims over global mode checks so that both
    # single-user and multi-user profiles rely on the same RBAC surface:
    # - is_admin flag
    # - primary role == 'admin'
    # - roles list contains 'admin'
    is_admin_flag = bool(
        current_user.get("is_admin")
        or current_user.get("role") == "admin"
        or ("admin" in (current_user.get("roles") or []))
    )
    if not is_admin_flag:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return current_user


def require_role(role: str):
    # Legacy shim - do not use in new code.
    # Prefer claim-first helpers (get_auth_principal, require_roles, require_permissions)
    # for new endpoints. This dependency is retained only for existing routes that
    # still rely on get_current_active_user user dicts.
    """
    Create a dependency that requires a specific role

    Args:
        role: Required role name

    Returns:
        Dependency function that checks for the role
    """
    async def role_checker(
        current_user: dict[str, Any] = Depends(get_current_active_user)  # noqa: B008
    ) -> dict[str, Any]:
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
    response: Response,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session_manager: SessionManager = Depends(get_session_manager_dep),
    db_pool: DatabasePool = Depends(get_db_pool),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
) -> Optional[dict[str, Any]]:
    """
    Legacy shim - do not use in new code.

    Get current user if authenticated, None otherwise.

    This is useful for endpoints that have different behavior
    for authenticated vs unauthenticated users

    Args:
        request: FastAPI request object
        response: FastAPI response object
        credentials: Optional bearer token
        session_manager: Session manager instance
        db_pool: Database pool instance
        x_api_key: Optional API key from X-API-KEY header

    Returns:
        User dictionary if authenticated, None otherwise
    """
    if not credentials and not x_api_key:
        return None

    try:
        return await get_current_user(
            request=request,
            response=response,
            credentials=credentials,  # may be None if authenticating via X-API-KEY only
            session_manager=session_manager,
            db_pool=db_pool,
            x_api_key=x_api_key,
        )
    except HTTPException:
        return None


#######################################################################################################################
#
# Rate Limiting Dependencies

def _rg_enabled_for_request(request: Request) -> bool:
    state = getattr(request, "state", None)
    return bool(state is not None and getattr(state, "rg_policy_id", None))


async def check_rate_limit(request: Request, rate_limiter=None) -> None:
    """
    RG-first rate limit dependency with legacy fallback.

    When Resource Governor (RG) has already governed this request, this is a
    no-op. Otherwise it uses the legacy AuthNZ rate limiter (user-scoped when
    available, else IP-scoped).
    """
    # TODO(Q2-2026): remove legacy fallback after RG enabled in all production environments; track via metrics.record_rate_limit_fallback().
    if _rg_enabled_for_request(request):
        return

    settings = get_settings()
    if not getattr(settings, "RATE_LIMIT_ENABLED", True):
        return

    principal = None
    try:
        ctx = getattr(request.state, "auth", None)
        if isinstance(ctx, AuthContext):
            principal = ctx.principal
    except Exception:
        principal = None

    if is_single_user_principal(principal):
        return

    # Claim-first governor hook (primarily for test invariants)
    await get_auth_governor()

    # In test mode, bypass rate limiting entirely for deterministic tests.
    if _is_test_mode():
        return

    try:
        if rate_limiter is None:
            rate_limiter = get_rate_limiter()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        metrics.record_rate_limit_fallback()
        logger.warning(
            "Legacy rate limiter unavailable; skipping rate limit check; error={}",
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiter unavailable.",
        ) from exc

    if not getattr(rate_limiter, "enabled", False):
        return

    endpoint = request.url.path if getattr(request, "url", None) else "unknown"
    client_ip = (
        resolve_client_ip(request, settings)
        or (request.client.host if getattr(request, "client", None) else None)
        or "unknown"
    )
    user_id = getattr(request.state, "user_id", None)
    user_id_int: Optional[int] = None
    if user_id is not None:
        try:
            user_id_int = int(user_id)
        except (TypeError, ValueError):
            user_id_int = None
    try:
        if user_id_int is not None:
            allowed, meta = await rate_limiter.check_user_rate_limit(
                user_id_int,
                endpoint,
                limit=settings.RATE_LIMIT_PER_MINUTE,
                window_minutes=1,
            )
        else:
            allowed, meta = await rate_limiter.check_rate_limit(
                identifier=f"ip:{client_ip}",
                endpoint=endpoint,
                limit=settings.RATE_LIMIT_PER_MINUTE,
                window_minutes=1,
            )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        metrics.record_rate_limit_fallback()
        logger.warning(
            "Legacy rate limiter check failed; skipping rate limit check; error={}",
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiter unavailable.",
        ) from exc

    if not allowed:
        detail = meta.get("error") if isinstance(meta, dict) else None
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail or "Rate limit exceeded.",
        )


async def check_auth_rate_limit(request: Request, rate_limiter=None) -> None:
    """RG-first auth rate limit dependency with legacy fallback (IP-scoped)."""
    # TODO(Q2-2026): remove legacy fallback after RG enabled in all production environments; track via metrics.record_rate_limit_fallback().
    if _rg_enabled_for_request(request):
        return

    settings = get_settings()
    if not getattr(settings, "RATE_LIMIT_ENABLED", True):
        return

    principal = None
    try:
        ctx = getattr(request.state, "auth", None)
        if isinstance(ctx, AuthContext):
            principal = ctx.principal
    except Exception:
        principal = None

    if is_single_user_principal(principal):
        return

    # Claim-first governor hook (primarily for test invariants)
    await get_auth_governor()

    # In test mode, bypass rate limiting entirely for deterministic tests.
    if _is_test_mode():
        return

    try:
        if rate_limiter is None:
            rate_limiter = get_rate_limiter()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        metrics.record_rate_limit_fallback()
        logger.warning(
            "Legacy rate limiter unavailable; skipping auth rate limit check; error={}",
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiter unavailable.",
        ) from exc

    if not getattr(rate_limiter, "enabled", False):
        return

    endpoint = request.url.path if getattr(request, "url", None) else "auth"
    client_ip = (
        resolve_client_ip(request, settings)
        or (request.client.host if getattr(request, "client", None) else None)
        or "unknown"
    )
    try:
        allowed, meta = await rate_limiter.check_rate_limit(
            identifier=f"ip:{client_ip}",
            endpoint=f"auth:{endpoint}",
            limit=settings.RATE_LIMIT_PER_MINUTE,
            window_minutes=1,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        metrics.record_rate_limit_fallback()
        logger.warning(
            "Legacy auth rate limiter check failed; skipping auth rate limit check; error={}",
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiter unavailable.",
        ) from exc

    if not allowed:
        detail = meta.get("error") if isinstance(meta, dict) else None
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail or "Rate limit exceeded.",
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
            async with db_pool.acquire() as conn:
                c1 = await conn.execute(
                    "SELECT limit_per_min, burst FROM rbac_user_rate_limits WHERE user_id = ? AND resource = ?",
                    (user_id, resource)
                )
                user_limit = await c1.fetchone()
                c2 = await conn.execute(
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
            logger.debug(
                "RBAC rate-limit selected for user {}, resource {}: rpm={}, burst={}",
                user_id,
                resource,
                limit_per_min,
                burst,
            )
        else:
            logger.debug("RBAC rate-limit: no configured limits for user {}, resource {}", user_id, resource)
    except Exception as e:
        logger.debug("RBAC rate-limit selection failed: {}", e)


def rbac_rate_limit(resource: str):
    """Factory returning a dependency that logs selected RBAC limits for the given resource."""
    async def _dep(request: Request, db_pool: DatabasePool = Depends(get_db_pool)):
        await enforce_rbac_rate_limit(request, resource, db_pool)
    try:
        setattr(_dep, "_tldw_rate_limit_resource", resource)
    except Exception as exc:
        logger.debug(
            "rbac_rate_limit: unable to attach rate-limit metadata to dependency: {}",
            exc,
        )
    return _dep


#######################################################################################################################
#
# Scoped Virtual-Key Enforcement

_VK_USAGE: dict = {}
_VK_USAGE_LOCK = threading.Lock()


def _vk_usage_ttl_seconds() -> int:
    try:
        ttl = int(os.getenv("VK_USAGE_TTL_SECONDS", "3600"))
    except (TypeError, ValueError):
        ttl = 3600
    return max(ttl, 60)


def _vk_usage_check_and_increment(key: object, limit: int) -> bool:
    """Process-local quota fallback with TTL to avoid unbounded growth."""
    now = time.monotonic()
    ttl = _vk_usage_ttl_seconds()
    with _VK_USAGE_LOCK:
        # Opportunistic pruning on each fallback use.
        if _VK_USAGE:
            expired = [k for k, (_cnt, exp) in _VK_USAGE.items() if exp <= now]
            for k in expired:
                _VK_USAGE.pop(k, None)
        entry = _VK_USAGE.get(key)
        if entry:
            count, expires_at = entry
            if expires_at <= now:
                count = 0
        else:
            count = 0
        if count >= int(limit):
            return False
        _VK_USAGE[key] = (count + 1, now + ttl)
        return True


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
    - If the bearer token is not a JWT, enforce API key constraints using that token.
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
        except Exception as exc:  # noqa: BLE001
            # Best effort: if resolution fails, leave as-is; downstream code handles missing services.
            logger.debug(
                "require_token_scope: dependency resolution failed; continuing with provided services: {}",
                exc,
            )

        token = credentials.credentials if credentials else None
        token_is_jwt = _looks_like_jwt(token) if token else False

        # Optional admin bypass based on the resolved principal (not token claims).
        if allow_admin_bypass:
            principal = None
            try:
                ctx = getattr(request.state, "auth", None)
                if isinstance(ctx, AuthContext):
                    principal = ctx.principal
            except Exception:
                principal = None
            if principal is None and credentials:
                try:
                    resolver = get_auth_principal
                    try:
                        app = getattr(request, "app", None)
                        if app is not None:
                            override_fn = app.dependency_overrides.get(get_auth_principal)
                            if override_fn is not None:
                                resolver = override_fn
                    except Exception:
                        resolver = get_auth_principal

                    if resolver is get_auth_principal:
                        principal = await resolver(request)
                    else:
                        try:
                            sig = inspect.signature(resolver)
                            has_no_params = len(sig.parameters) == 0
                        except (TypeError, ValueError):
                            has_no_params = False
                        try:
                            result = resolver() if has_no_params else resolver(request)
                        except TypeError:
                            result = resolver()
                        if inspect.isawaitable(result):
                            result = await result
                        principal = result
                except HTTPException:
                    principal = None
                except Exception:
                    principal = None
            if principal is not None and principal.is_admin:
                return None

        # If we have Authorization bearer and it looks like a JWT, apply JWT-based checks.
        if token and token_is_jwt:
            try:
                payload = jwt_service.decode_access_token(token)
            except (InvalidTokenError, TokenExpiredError):
                # Defensive: malformed tokens should fall back to upstream auth handling.
                return None
            # Enforce revocation/blacklist checks for scoped JWTs.
            try:
                from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager

                session_manager = await get_session_manager()
                if await session_manager.is_token_blacklisted(token, payload.get("jti")):
                    raise HTTPException(status_code=401, detail="Token has been revoked")
            except HTTPException:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "require_token_scope: token revocation check failed; denying: {}",
                    exc,
                )
                raise HTTPException(status_code=401, detail="Could not validate credentials") from exc
            tok_scope = str(payload.get("scope") or "").strip()
            if tok_scope:
                try:
                    request.state._token_scope_enforced = True
                    request.state._token_scope_claim = tok_scope
                    request.state._token_scope_required = str(scope)
                except Exception:  # noqa: BLE001
                    logger.debug("require_token_scope: failed to attach scope enforcement marker to request.state")
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
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "require_token_scope: endpoint allowlist enforcement failed; continuing: {}",
                    exc,
                )

            # Enforce HTTP method allowlist
            try:
                am = payload.get("allowed_methods")
                if isinstance(am, list) and am:
                    method = str(getattr(request, "method", "")).upper()
                    if method and method not in [str(x).upper() for x in am]:
                        raise HTTPException(status_code=403, detail="Forbidden: method not permitted for token")
            except HTTPException:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "require_token_scope: method allowlist enforcement failed; continuing: {}",
                    exc,
                )

            # Enforce path prefix allowlist
            try:
                ap = payload.get("allowed_paths")
                if isinstance(ap, list) and ap:
                    path = getattr(getattr(request, "url", None), "path", None) or getattr(request, "scope", {}).get("path")
                    if path and not any(str(path).startswith(str(pfx)) for pfx in ap):
                        raise HTTPException(status_code=403, detail="Forbidden: path not permitted for token")
            except HTTPException:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "require_token_scope: path allowlist enforcement failed; continuing: {}",
                    exc,
                )

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
                            except Exception as err:
                                # Defensive: fall back to process-local counters if quota backend fails.
                                if not _vk_usage_check_and_increment(key, int(max_calls)):
                                    raise HTTPException(
                                        status_code=403,
                                        detail="Forbidden: token quota exceeded",
                                    ) from err
            except HTTPException:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "require_token_scope: token constraints evaluation failed; continuing: {}",
                    exc,
                )

            if require_schedule_match:
                try:
                    tok_sid = payload.get("schedule_id")
                except Exception:  # noqa: BLE001
                    tok_sid = None
                expected = None
                try:
                    expected = request.path_params.get(schedule_path_param)
                except Exception:  # noqa: BLE001
                    expected = None
                if expected is None:
                    try:
                        expected = request.headers.get(schedule_header)
                    except Exception:  # noqa: BLE001
                        expected = None
                if tok_sid is not None and expected is not None and str(tok_sid) != str(expected):
                    raise HTTPException(status_code=403, detail="Forbidden: schedule scope mismatch")

            return None

        # Fallback: X-API-KEY constraints enforcement (if header present and key is valid)
        try:
            api_key = request.headers.get("X-API-KEY") if getattr(request, "headers", None) else None
        except Exception:  # noqa: BLE001
            # Defensive: request headers access should never block the fallback path.
            api_key = None
        if not api_key and token and not token_is_jwt:
            api_key = token
        if api_key:
            try:
                from tldw_Server_API.app.core.AuthNZ.api_key_manager import (
                    VALID_SCOPE_VALUES as _VALID_SCOPE_VALUES,
                )
                from tldw_Server_API.app.core.AuthNZ.api_key_manager import (
                    has_scope as _has_scope,
                )
                from tldw_Server_API.app.core.AuthNZ.api_key_manager import (
                    normalize_scope as _normalize_scope,
                )

                def _required_scope_for_api_key(scope_value: str, method: str) -> Optional[str]:
                    scope_norm = str(scope_value or "").strip().lower()
                    if scope_norm in _VALID_SCOPE_VALUES:
                        return scope_norm
                    if method in {"GET", "HEAD", "OPTIONS"}:
                        return "read"
                    if method:
                        return "write"
                    return None

                api_mgr = await get_api_key_manager()
                client_ip = resolve_client_ip(request, get_settings())
                info = await api_mgr.validate_api_key(api_key=api_key, ip_address=client_ip)
                if not info:
                    # Let upstream auth fail; do not enforce here
                    return None
                # Admin bypass via scope 'admin'
                key_scopes = _normalize_scope(info.get("scope"))
                if allow_admin_bypass and (_has_scope(key_scopes, "admin") or _has_scope(key_scopes, "service")):
                    return None
                required_scope = _required_scope_for_api_key(scope, str(getattr(request, "method", "")).upper())
                if required_scope and not _has_scope(key_scopes, required_scope):
                    raise HTTPException(
                        status_code=403,
                        detail="Forbidden: API key lacks required scope",
                    )
                # Allowed endpoints from llm_allowed_endpoints
                allowed_eps = info.get("llm_allowed_endpoints")
                if isinstance(allowed_eps, str):
                    import json as _json
                    try:
                        allowed_eps = _json.loads(allowed_eps)
                    except (ValueError, TypeError):
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
                    except (ValueError, TypeError):
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
                                except Exception as err:
                                    # Defensive: fall back to process-local counters if quota backend fails.
                                    key = (f"apikey:{key_id}", str(count_as))
                                    if not _vk_usage_check_and_increment(key, int(quota)):
                                        raise HTTPException(
                                            status_code=403,
                                            detail="Forbidden: API key quota exceeded",
                                        ) from err
            except HTTPException:
                raise
            except Exception:  # noqa: BLE001
                # Best-effort: do not block if metadata not available
                return None
        return None

    try:
        setattr(_checker, "_tldw_endpoint_id", endpoint_id)
        setattr(_checker, "_tldw_scope_name", scope)
        setattr(_checker, "_tldw_token_scope", True)
        setattr(_checker, "_tldw_token_scope_required", str(scope))
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "require_token_scope: unable to attach metadata to dependency: {}",
            exc,
        )

    return _checker
#
# End of auth_deps.py
#######################################################################################################################
