# auth.py
# Description: Authentication endpoints for user login, logout, refresh, and registration
#
# Imports
from typing import Dict, Any, Optional
import os
from datetime import datetime
#
# 3rd-party imports
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger
import time
from tldw_Server_API.app.core.Metrics.metrics_logger import log_counter, log_histogram
#
# Local imports
from tldw_Server_API.app.api.v1.schemas.auth_schemas import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegistrationResponse,
    MessageResponse,
    UserResponse
)
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_db_transaction,
    get_password_service_dep,
    get_jwt_service_dep,
    get_session_manager_dep,
    get_rate_limiter_dep,
    get_registration_service_dep,
    get_current_user,
    get_current_active_user,
    check_auth_rate_limit
)
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, is_postgres_backend
from tldw_Server_API.app.core.AuthNZ.csrf_protection import (
    global_settings as _csrf_globals,
)
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService, get_jwt_service
from tldw_Server_API.app.core.AuthNZ.session_manager import SessionManager
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter
from tldw_Server_API.app.core.AuthNZ.input_validation import get_input_validator
from tldw_Server_API.app.services.registration_service import RegistrationService
from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.Audit.unified_audit_service import (
    AuditEventType,
    AuditContext
)
from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    UserNotFoundError,
    AccountInactiveError,
    InvalidTokenError,
    TokenExpiredError,
    RegistrationError,
    DuplicateUserError,
    WeakPasswordError,
    InvalidRegistrationCodeError
)
from tldw_Server_API.app.services.auth_service import (
    fetch_user_by_login_identifier,
    update_user_password_hash,
    update_user_last_login,
    fetch_active_user_by_id,
)

#######################################################################################################################
#
# Router Configuration

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={404: {"description": "Not found"}}
)


#######################################################################################################################
#
# Register endpoint diagnostics (test-only)

async def _register_runtime_diag(request: Request, response: Response):
    """Small request-time diagnostic for tests.

    When TEST_MODE is enabled, annotate the response with:
    - X-TLDW-DB: 'postgres' or 'sqlite' based on get_db_pool()
    - X-TLDW-CSRF-Enabled: 'true' or 'false' from runtime settings
    - X-TLDW-Register-Duration-ms: handler duration in ms (set after return)
    """
    test_mode = os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes")
    if not test_mode:
        # No-op when not in test mode
        return

    start_ts = time.perf_counter()
    try:
        # Resolve DB pool and set backend header
        pool = await get_db_pool()
        db_backend = "postgres" if getattr(pool, "pool", None) is not None else "sqlite"
        response.headers["X-TLDW-DB"] = db_backend

        # Reflect runtime CSRF state exposed via global settings
        csrf_enabled = _csrf_globals.get("CSRF_ENABLED", None)
        response.headers["X-TLDW-CSRF-Enabled"] = "true" if bool(csrf_enabled) else "false"
    finally:
        # Use a background callback via request.state to add duration later
        request.state._register_diag_start = start_ts

def _finalize_register_diag(request: Request, response: Response):
    """Attach handler duration header if start was captured by the diagnostic dep."""
    try:
        start_ts = getattr(request.state, "_register_diag_start", None)
        if start_ts is None:
            return
        dur_ms = int((time.perf_counter() - start_ts) * 1000)
        response.headers["X-TLDW-Register-Duration-ms"] = str(dur_ms)
    except Exception:
        # Diagnostics must never interfere with the response
        pass


#######################################################################################################################
#
# Login Endpoint

async def _login_runtime_diag(request: Request, response: Response):
    """Diagnostics for login (TEST_MODE only): annotate DB backend and CSRF state, capture start time."""
    test_mode = os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes")
    if not test_mode:
        return
    import time as _t
    try:
        pool = await get_db_pool()
        db_backend = "postgres" if getattr(pool, "pool", None) is not None else "sqlite"
        response.headers["X-TLDW-DB"] = db_backend
        csrf_enabled = _csrf_globals.get("CSRF_ENABLED", None)
        response.headers["X-TLDW-CSRF-Enabled"] = "true" if bool(csrf_enabled) else "false"
    finally:
        request.state._login_diag_start = _t.perf_counter()

def _finalize_login_diag(request: Request, response: Response):
    try:
        import time as _t
        start_ts = getattr(request.state, "_login_diag_start", None)
        if start_ts is None:
            return
        dur_ms = int((_t.perf_counter() - start_ts) * 1000)
        response.headers["X-TLDW-Login-Duration-ms"] = str(dur_ms)
    except Exception:
        pass


# ---------------- Self-service virtual keys (scoped JWT) ----------------
from pydantic import BaseModel, Field
from typing import List


class SelfVirtualKeyRequest(BaseModel):
    ttl_minutes: int = Field(60, ge=1, le=1440)
    scope: str = Field("workflows")
    schedule_id: Optional[str] = None
    allowed_endpoints: Optional[List[str]] = None
    allowed_methods: Optional[List[str]] = None
    allowed_paths: Optional[List[str]] = None
    max_calls: Optional[int] = Field(None, ge=0)
    max_runs: Optional[int] = Field(None, ge=0)
    not_before: Optional[str] = Field(None, description="Optional ISO timestamp when token becomes valid")


@router.post("/virtual-key")
async def mint_self_virtual_key(
    body: SelfVirtualKeyRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Mint a short-lived, scoped JWT for the current user.

    This is intended for automation and integrations to act on behalf of the
    requesting user with constrained scope, time window, and optional endpoint
    allowlists.
    """
    if settings.AUTH_MODE != "multi_user":
        raise HTTPException(status_code=400, detail="Virtual keys require multi-user mode")
    try:
        svc = JWTService(settings)
        add_claims: Dict[str, Any] = {}
        if body.allowed_endpoints:
            add_claims["allowed_endpoints"] = [str(x) for x in body.allowed_endpoints]
        if body.allowed_methods:
            add_claims["allowed_methods"] = [str(x).upper() for x in body.allowed_methods]
        if body.allowed_paths:
            add_claims["allowed_paths"] = [str(x) for x in body.allowed_paths]
        if body.max_calls is not None:
            add_claims["max_calls"] = int(body.max_calls)
        if body.max_runs is not None:
            add_claims["max_runs"] = int(body.max_runs)
        if body.not_before:
            # Store as standard JWT 'nbf' if parseable; otherwise ignore
            try:
                from datetime import datetime
                nbf_dt = datetime.fromisoformat(str(body.not_before).replace("Z", "+00:00"))
                add_claims["nbf"] = int(nbf_dt.timestamp())
            except Exception:
                pass
        token = svc.create_virtual_access_token(
            user_id=int(current_user.get("id")),
            username=str(current_user.get("username") or current_user.get("email") or "user"),
            role=("admin" if bool(current_user.get("is_admin")) else str(current_user.get("role") or "user")),
            scope=str(body.scope or "workflows"),
            ttl_minutes=int(body.ttl_minutes),
            schedule_id=(str(body.schedule_id) if body.schedule_id else None),
            additional_claims=add_claims or None,
        )
        from datetime import datetime, timedelta
        exp = datetime.utcnow() + timedelta(minutes=int(body.ttl_minutes))
        return {
            "token": token,
            "expires_at": exp.isoformat(),
            "scope": str(body.scope or "workflows"),
            "schedule_id": (str(body.schedule_id) if body.schedule_id else None),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mint self virtual key: {e}")
        raise HTTPException(status_code=500, detail="Failed to mint token")

@router.post("/login", response_model=TokenResponse, dependencies=[Depends(check_auth_rate_limit)])
async def login(
    request: Request,
    response: Response,
    _diag=Depends(_login_runtime_diag),
    form_data: OAuth2PasswordRequestForm = Depends(),
    db=Depends(get_db_transaction),
    jwt_service: JWTService = Depends(get_jwt_service_dep),
    password_service: PasswordService = Depends(get_password_service_dep),
    session_manager: SessionManager = Depends(get_session_manager_dep),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    settings: Settings = Depends(get_settings)
) -> TokenResponse:
    """
    OAuth2 compatible login endpoint

    Authenticates user with username/password and returns JWT tokens.
    Compatible with OAuth2PasswordRequestForm for standard OAuth2 clients.

    Args:
        form_data: OAuth2 form with username and password

    Returns:
        TokenResponse with access_token, refresh_token, and expiry

    Raises:
        HTTPException: 401 if credentials invalid, 403 if account inactive
    """
    start_time = time.perf_counter()
    log_counter("auth_login_attempt")
    try:
        # Get client info
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "Unknown")
        # PII-aware logging
        if settings.PII_REDACT_LOGS:
            logger.info("Login attempt [redacted]")
        else:
            logger.info(f"Login attempt for user: {form_data.username} from IP: {client_ip}")

        # Check if IP is locked out (only when rate limiting is enabled)
        is_locked = False
        lockout_expires = None
        if getattr(rate_limiter, 'enabled', False):
            is_locked, lockout_expires = await rate_limiter.check_lockout(client_ip)
        if is_locked:
            logger.warning(f"Login attempt from locked IP: {client_ip}")
            log_counter("auth_login_locked_ip")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed login attempts. Please try again later.",
                headers={"Retry-After": str(int((lockout_expires - datetime.utcnow()).total_seconds()))}
            )

        # Sanitize input (lightweight). For login, avoid strict validation to not block
        # legitimate existing accounts (e.g., reserved usernames like 'admin').
        login_identifier = form_data.username.strip()

        # Helper to attempt audit logging without hard dependency (safe no-op in tests)
        async def _safe_audit_log_login(user_id: int, username: str, ip: str, ua: str, success: bool):
            try:
                from tldw_Server_API.app.core.Audit.unified_audit_service import UnifiedAuditService
                from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
                svc = UnifiedAuditService(db_path=str(DatabasePaths.get_audit_db_path(user_id)))
                await svc.initialize()
                await svc.log_login(
                    user_id=user_id,
                    username=username,
                    ip_address=ip,
                    user_agent=ua,
                    success=success,
                )
            except Exception:
                # Never block auth on audit issues
                pass

        # Fetch user from database using sanitized identifier
        user = await fetch_user_by_login_identifier(db, login_identifier)

        # Check if user exists
        if not user:
            # Log failed attempt
            if settings.PII_REDACT_LOGS:
                logger.warning("Failed login: user not found [redacted]")
            else:
                logger.warning(f"Failed login: User not found - {login_identifier}")

            # Track failed attempt by IP (only when rate limiting is enabled)
            if getattr(rate_limiter, 'enabled', False):
                await rate_limiter.record_failed_attempt(
                    identifier=client_ip,
                    attempt_type="login"
                )

            log_counter("auth_login_user_not_found")
            # finalize diag headers in test mode for visibility
            try:
                _finalize_login_diag(request, response)
            except Exception:
                pass
            extra_headers = {"WWW-Authenticate": "Bearer"}
            if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
                extra_headers["X-TLDW-Login-Reason"] = "user-not-found"
                # Stage marker to aid triage in test runs
                extra_headers["X-TLDW-Login-Stage"] = "user_fetch"
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers=extra_headers
            )

        # Convert to dict if needed; guard against stray AsyncMock/awaitables in tests
        import inspect as _inspect
        if _inspect.isawaitable(user):
            try:
                user = await user  # resolve unexpected awaitables from mocks
            except Exception:
                pass
        # user already normalized to dict in service

        # Verify password
        is_test_mode = os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes")
        is_valid, needs_rehash = password_service.verify_password(form_data.password, user['password_hash'])
        # In TEST_MODE, double-check with a fresh PasswordService to rule out stale settings
        if not is_valid and is_test_mode:
            try:
                fresh_ps = PasswordService(settings)
                is_valid2, needs_rehash2 = fresh_ps.verify_password(form_data.password, user['password_hash'])
                if is_valid2:
                    is_valid = True
                    needs_rehash = needs_rehash2
                    password_service = fresh_ps
                    # annotate header to indicate re-verify succeeded
                    try:
                        response.headers["X-TLDW-Login-Reverify"] = "ok"
                    except Exception:
                        pass
            except Exception:
                # fall back to original result
                pass
        if not is_valid:
            # Log failed attempt
            if settings.PII_REDACT_LOGS:
                logger.warning("Failed login: invalid password [redacted]")
            else:
                logger.warning(f"Failed login: Invalid password for user {user['username']}")

            # Audit log failed login
            await _safe_audit_log_login(
                user_id=user['id'],
                username=user['username'],
                ip=client_ip,
                ua=user_agent,
                success=False,
            )

            # Track failed attempt by IP and username
            ip_result = {"is_locked": False, "remaining_attempts": 5}
            user_result = {"is_locked": False, "remaining_attempts": 5}
            if getattr(rate_limiter, 'enabled', False):
                ip_result = await rate_limiter.record_failed_attempt(
                    identifier=client_ip,
                    attempt_type="login"
                )
                user_result = await rate_limiter.record_failed_attempt(
                    identifier=user['username'],
                    attempt_type="login"
                )

            # Provide informative error if locked out
            if ip_result['is_locked'] or user_result['is_locked']:
                log_counter("auth_login_locked_user")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many failed login attempts. Account temporarily locked.",
                    headers={"Retry-After": "900"}  # 15 minutes
                )

            # Otherwise generic error
            remaining = min(ip_result.get('remaining_attempts', 5), user_result.get('remaining_attempts', 5))
            logger.info(f"Remaining login attempts: {remaining}")

            log_counter("auth_login_invalid_password")
            try:
                _finalize_login_diag(request, response)
            except Exception:
                pass
            extra_headers = {"WWW-Authenticate": "Bearer"}
            if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
                extra_headers["X-TLDW-Login-Reason"] = "invalid-password"
                # Stage marker to aid triage in test runs
                extra_headers["X-TLDW-Login-Stage"] = "verify_password"
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers=extra_headers
            )

        # Check if account is active
        if not user['is_active']:
            logger.warning(f"Failed login: Inactive account - {user['username']}")
            log_counter("auth_login_inactive_account")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Please contact support."
            )

        # If password needs rehashing, update it
        if needs_rehash:
            new_hash = password_service.hash_password(form_data.password)
            await update_user_password_hash(db, int(user['id']), new_hash)
            logger.info(f"Updated password hash for user {user['username']} with new parameters")

        # Create session first to get session_id
        user_agent = request.headers.get("User-Agent", "Unknown")

        # Generate tokens based on auth mode
        if settings.AUTH_MODE == "single_user":
            # For single-user mode, return simple tokens
            access_token = f"single-user-token-{user['id']}"
            refresh_token = f"single-user-refresh-{user['id']}"

            # Create session with tokens
            session_info = await session_manager.create_session(
                user_id=user['id'],
                access_token=access_token,
                refresh_token=refresh_token,
                ip_address=client_ip,
                user_agent=user_agent
            )
        else:
            # For multi-user mode, create a temporary session first
            # Use unique placeholders to avoid duplicate token hash constraints
            import secrets
            temp_access = f"temp_access_{secrets.token_urlsafe(16)}"
            temp_refresh = f"temp_refresh_{secrets.token_urlsafe(16)}"

            temp_session_info = await session_manager.create_session(
                user_id=user['id'],
                access_token=temp_access,  # Will update with actual token
                refresh_token=temp_refresh,  # Will update with actual token
                ip_address=client_ip,
                user_agent=user_agent
            )

            session_id = temp_session_info['session_id']

            # Create JWT tokens with session_id
            access_token = jwt_service.create_access_token(
                user_id=user['id'],
                username=user['username'],
                role=user['role'],
                additional_claims={"session_id": session_id}
            )

            refresh_token = jwt_service.create_refresh_token(
                user_id=user['id'],
                username=user['username'],
                additional_claims={"session_id": session_id}
            )

            # Update session with actual tokens
            await session_manager.update_session_tokens(
                session_id=session_id,
                access_token=access_token,
                refresh_token=refresh_token
            )

            session_info = temp_session_info

        # Update last login time
        await update_user_last_login(db, int(user['id']), datetime.utcnow())

        # Log successful login
        if settings.PII_REDACT_LOGS:
            logger.info("Successful login [redacted]")
        else:
            logger.info(f"Successful login for user: {user['username']} (ID: {user['id']})")

        # Reset failed login attempts on successful login
        if getattr(rate_limiter, 'enabled', False):
            await rate_limiter.reset_failed_attempts(client_ip, "login")
            await rate_limiter.reset_failed_attempts(user['username'], "login")

        # Audit log successful login
        await _safe_audit_log_login(
            user_id=user['id'],
            username=user['username'],
            ip=client_ip,
            ua=user_agent,
            success=True,
        )

        log_counter("auth_login_success")
        log_histogram("auth_login_duration", time.perf_counter() - start_time)
        result = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        try:
            _finalize_login_diag(request, response)
        except Exception:
            pass
        return result

    except HTTPException:
        log_counter("auth_login_http_error")
        log_histogram("auth_login_duration", time.perf_counter() - start_time)
        raise
    except Exception as e:
        logger.exception("Login error")
        log_counter("auth_login_unexpected_error")
        log_histogram("auth_login_duration", time.perf_counter() - start_time)
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):  # expose details in tests
            try:
                response.headers["X-TLDW-Login-Error"] = str(e)
                _finalize_login_diag(request, response)
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Login error: {e}"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login"
        )


#######################################################################################################################
#
# Logout Endpoint

@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: Dict[str, Any] = Depends(get_current_user),
    session_manager: SessionManager = Depends(get_session_manager_dep),
    jwt_service: JWTService = Depends(get_jwt_service_dep)
) -> MessageResponse:
    """
    Logout current user and invalidate tokens

    Invalidates the current session and blacklists the tokens.

    Returns:
        MessageResponse confirming logout
    """
    start_time = time.perf_counter()
    log_counter("auth_logout_attempt")
    try:
        # Get session from current token
        # Note: We'll need to pass session_id in JWT payload
        # For now, invalidate all sessions for the user
        await session_manager.revoke_all_user_sessions(current_user['id'])

        # PII-aware logging
        try:
            _settings = get_settings()
        except Exception:
            _settings = None
        if _settings and getattr(_settings, 'PII_REDACT_LOGS', False):
            logger.info("User logged out [redacted]")
        else:
            logger.info(f"User logged out: {current_user['username']} (ID: {current_user['id']})")

        log_counter("auth_logout_success")
        log_histogram("auth_logout_duration", time.perf_counter() - start_time)
        return MessageResponse(
            message="Successfully logged out",
            details={"user_id": current_user['id']}
        )

    except Exception as e:
        logger.error(f"Logout error: {e}")
        log_counter("auth_logout_error")
        log_histogram("auth_logout_duration", time.perf_counter() - start_time)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during logout"
        )


#######################################################################################################################
#
# Token Refresh Endpoint

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    response: Response,
    jwt_service: JWTService = Depends(get_jwt_service_dep),
    session_manager: SessionManager = Depends(get_session_manager_dep),
    db=Depends(get_db_transaction),
    settings: Settings = Depends(get_settings)
) -> TokenResponse:
    """
    Refresh access token using refresh token

    Args:
        request: RefreshTokenRequest with refresh token

    Returns:
        TokenResponse with new access_token

    Raises:
        HTTPException: 401 if refresh token invalid or expired
    """
    start_time = time.perf_counter()
    log_counter("auth_refresh_attempt")
    try:
        # TEST_MODE diagnostics (set DB and CSRF headers for easier triage)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                from tldw_Server_API.app.core.AuthNZ.database import get_db_pool as _get_pool
                pool = await _get_pool()
                db_backend = "postgres" if getattr(pool, "pool", None) is not None else "sqlite"
                from tldw_Server_API.app.core.AuthNZ.csrf_protection import global_settings as _csrf_globals
                response.headers["X-TLDW-DB"] = db_backend
                response.headers["X-TLDW-CSRF-Enabled"] = "true" if bool(_csrf_globals.get("CSRF_ENABLED", None)) else "false"
            except Exception:
                pass

        # Handle based on auth mode
        if settings.AUTH_MODE == "single_user":
            # Simple token validation for single-user mode
            if not request.refresh_token.startswith("single-user-refresh-"):
                if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
                    try:
                        response.headers["X-TLDW-Refresh-Stage"] = "validate"
                        response.headers["X-TLDW-Refresh-Reason"] = "invalid-format"
                    except Exception:
                        pass
                raise InvalidTokenError("Invalid refresh token format")
            user_id = int(request.refresh_token.split("-")[-1])
        else:
            # JWT validation for multi-user mode
            try:
                payload = jwt_service.decode_refresh_token(request.refresh_token)
            except Exception as _e:
                if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
                    try:
                        response.headers["X-TLDW-Refresh-Stage"] = "decode"
                        response.headers["X-TLDW-Refresh-Reason"] = f"invalid-token:{type(_e).__name__}"
                    except Exception:
                        pass
                raise

            # Check if token is blacklisted
            if await session_manager.is_token_blacklisted(request.refresh_token, payload.get("jti")):
                if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
                    try:
                        response.headers["X-TLDW-Refresh-Stage"] = "blacklist"
                        response.headers["X-TLDW-Refresh-Reason"] = "revoked"
                    except Exception:
                        pass
                raise InvalidTokenError("Refresh token has been revoked")

            # JWT standard uses 'sub' for subject (user ID)
            user_id = payload.get("sub") or payload.get("user_id")
            if not user_id:
                if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
                    try:
                        response.headers["X-TLDW-Refresh-Stage"] = "decode"
                        response.headers["X-TLDW-Refresh-Reason"] = "missing-user-id"
                    except Exception:
                        pass
                raise InvalidTokenError("Invalid refresh token payload")

            # Convert to int if it's a string
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
                    try:
                        response.headers["X-TLDW-Refresh-Stage"] = "decode"
                        response.headers["X-TLDW-Refresh-Reason"] = "invalid-user-id"
                    except Exception:
                        pass
                raise InvalidTokenError("Invalid user ID in refresh token")
            # Capture session association when present
            session_id = payload.get("session_id")

        # Fetch user
        user = await fetch_active_user_by_id(db, user_id)

        if not user:
            if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
                try:
                    response.headers["X-TLDW-Refresh-Stage"] = "fetch-user"
                    response.headers["X-TLDW-Refresh-Reason"] = "user-not-found"
                except Exception:
                    pass
            raise UserNotFoundError(f"User {user_id}")

        # Convert to dict
        if not isinstance(user, dict):
            if hasattr(user, 'keys'):
                user = dict(user)
            else:
                columns = ['id', 'uuid', 'username', 'email', 'password_hash', 'role']
                user = dict(zip(columns[:len(user)], user))

        # Generate new tokens based on auth mode and session linkage
        if settings.AUTH_MODE == "single_user":
            new_access_token = f"single-user-token-{user['id']}"
            new_refresh_token = request.refresh_token  # no rotation in single-user mode
        else:
            # Access token always refreshed; preserve session_id claim when available
            add_claims = {"session_id": session_id} if session_id else None
            new_access_token = jwt_service.create_access_token(
                user_id=user['id'],
                username=user['username'],
                role=user['role'],
                additional_claims=add_claims
            )
            # Rotate refresh token if enabled
            new_refresh_token = request.refresh_token
            if getattr(settings, "ROTATE_REFRESH_TOKENS", False):
                new_refresh_token = jwt_service.create_refresh_token(
                    user_id=user['id'],
                    username=user['username'],
                    additional_claims=add_claims
                )
            # Update backing session to reflect new token(s)
            try:
                await session_manager.refresh_session(
                    refresh_token=request.refresh_token,
                    new_access_token=new_access_token,
                    new_refresh_token=(new_refresh_token if new_refresh_token != request.refresh_token else None)
                )
            except Exception as _sess_e:
                # Treat missing/invalid session mapping as invalid token usage
                if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
                    try:
                        response.headers.setdefault("X-TLDW-Refresh-Stage", "session")
                        response.headers.setdefault("X-TLDW-Refresh-Reason", f"session-error:{type(_sess_e).__name__}")
                    except Exception:
                        pass
                raise InvalidTokenError("Invalid or expired session for refresh token")

            # Always blacklist the prior refresh token's JTI to prevent reuse
            try:
                from datetime import datetime as _dt
                from tldw_Server_API.app.core.AuthNZ.token_blacklist import get_token_blacklist as _get_bl
                old_jti = payload.get("jti") if isinstance(payload, dict) else None
                old_exp = payload.get("exp") if isinstance(payload, dict) else None
                if old_jti and isinstance(old_exp, (int, float)) and new_refresh_token != request.refresh_token:
                    expires_at = _dt.utcfromtimestamp(old_exp)
                    bl = _get_bl()
                    # Best-effort revoke; do not fail refresh if blacklist write fails
                    await bl.revoke_token(
                        jti=old_jti,
                        expires_at=expires_at,
                        user_id=int(user['id']),
                        token_type="refresh",
                        reason="refresh-rotated",
                        revoked_by=None,
                        ip_address=(request.client.host if request and getattr(request, 'client', None) else None),
                    )
            except Exception as _bl_e:
                try:
                    logger.debug(f"Refresh: blacklist prior token best-effort failed: {_bl_e}")
                except Exception:
                    pass

        if settings.PII_REDACT_LOGS:
            logger.info("Token refreshed [redacted]")
        else:
            logger.info(f"Token refreshed for user: {user['username']} (ID: {user['id']})")

        log_counter("auth_refresh_success")
        log_histogram("auth_refresh_duration", time.perf_counter() - start_time)
        # TEST_MODE: include simple duration metric header (non-breaking)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                response.headers["X-TLDW-Refresh-Duration-ms"] = str(int((time.perf_counter() - start_time) * 1000))
            except Exception:
                pass
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    except (TokenExpiredError, InvalidTokenError) as e:
        logger.warning(f"Token refresh failed: {e}")
        log_counter("auth_refresh_token_error", labels={"type": type(e).__name__})
        log_histogram("auth_refresh_duration", time.perf_counter() - start_time)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                response.headers.setdefault("X-TLDW-Refresh-Stage", "error")
                response.headers.setdefault("X-TLDW-Refresh-Reason", type(e).__name__)
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        log_counter("auth_refresh_unexpected_error")
        log_histogram("auth_refresh_duration", time.perf_counter() - start_time)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                response.headers["X-TLDW-Refresh-Stage"] = "unexpected"
                response.headers["X-TLDW-Refresh-Reason"] = str(e)
                response.headers["X-TLDW-Refresh-Duration-ms"] = str(int((time.perf_counter() - start_time) * 1000))
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during token refresh"
        )


#######################################################################################################################
#
# Registration Endpoint

@router.post("/register", response_model=RegistrationResponse, dependencies=[Depends(check_auth_rate_limit)])
async def register(
    request: RegisterRequest,
    response: Response,
    _diag=Depends(_register_runtime_diag),
    registration_service: RegistrationService = Depends(get_registration_service_dep)
) -> RegistrationResponse:
    """
    Register a new user

    Creates a new user account with the provided credentials.
    May require a registration code if configured.

    Args:
        request: RegisterRequest with user details

    Returns:
        RegistrationResponse with user information

    Raises:
        HTTPException: 400 if validation fails, 409 if user exists
    """
    start_time = time.perf_counter()
    log_counter("auth_register_attempt")
    try:
        # Register the user
        user_info = await registration_service.register_user(
            username=request.username,
            email=request.email,
            password=request.password,
            registration_code=request.registration_code
        )

        logger.info(f"New user registered: {user_info['username']} (ID: {user_info['user_id']})")

        # If using SQLite for AuthNZ, generate a per-user API key so UI can present it
        api_key_value = None
        try:
            settings = get_settings()
            if isinstance(settings.DATABASE_URL, str) and settings.DATABASE_URL.startswith("sqlite"):
                api_mgr = await get_api_key_manager()
                key_result = await api_mgr.create_api_key(
                    user_id=int(user_info['user_id']),
                    name="Default API Key",
                    description="Auto-generated on registration",
                    scope="write",
                    expires_in_days=365
                )
                api_key_value = key_result.get('key')
        except Exception as _e:
            logger.warning(f"Failed to auto-generate API key for new user {user_info['user_id']}: {_e}")

        log_counter("auth_register_success")
        log_histogram("auth_register_duration", time.perf_counter() - start_time)
        # Attach diagnostics (if enabled)
        _finalize_register_diag(request, response)
        return RegistrationResponse(
            message="Registration successful",
            user_id=user_info['user_id'],
            username=user_info['username'],
            email=user_info['email'],
            requires_verification=not user_info['is_verified'],
            api_key=api_key_value
        )

    except DuplicateUserError as e:
        logger.warning(f"Registration failed - duplicate user: {e}")
        log_counter("auth_register_duplicate")
        log_histogram("auth_register_duration", time.perf_counter() - start_time)
        # Attach diagnostics (if enabled)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                response.headers["X-TLDW-Register-Error"] = str(e)
            except Exception:
                pass
        _finalize_register_diag(request, response)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except WeakPasswordError as e:
        logger.warning(f"Registration failed - weak password: {e}")
        log_counter("auth_register_weak_password")
        log_histogram("auth_register_duration", time.perf_counter() - start_time)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                response.headers["X-TLDW-Register-Error"] = str(e)
            except Exception:
                pass
        _finalize_register_diag(request, response)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except InvalidRegistrationCodeError as e:
        logger.warning(f"Registration failed - invalid code: {e}")
        log_counter("auth_register_invalid_code")
        log_histogram("auth_register_duration", time.perf_counter() - start_time)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                response.headers["X-TLDW-Register-Error"] = str(e)
            except Exception:
                pass
        _finalize_register_diag(request, response)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RegistrationError as e:
        logger.error(f"Registration error: {e}")
        log_counter("auth_register_error")
        log_histogram("auth_register_duration", time.perf_counter() - start_time)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                response.headers["X-TLDW-Register-Error"] = str(e)
            except Exception:
                pass
        _finalize_register_diag(request, response)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Check if it's a transaction error wrapping a duplicate user error
        error_msg = str(e).lower()
        if "username already exists" in error_msg or "email already exists" in error_msg:
            logger.warning(f"Registration failed - duplicate user (wrapped): {e}")
            if "username" in error_msg:
                detail = "Username already exists"
            else:
                detail = "Email already exists"
            log_counter("auth_register_duplicate_wrapped")
            log_histogram("auth_register_duration", time.perf_counter() - start_time)
            if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
                try:
                    response.headers["X-TLDW-Register-Error"] = str(e)
                except Exception:
                    pass
            _finalize_register_diag(request, response)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail
            )

        logger.error(f"Unexpected registration error: {e}")
        log_counter("auth_register_unexpected_error")
        log_histogram("auth_register_duration", time.perf_counter() - start_time)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                response.headers["X-TLDW-Register-Error"] = str(e)
            except Exception:
                pass
        duration = time.perf_counter() - start_time
        _finalize_register_diag(request, response)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                pool = await get_db_pool()
                db_backend = "postgres" if getattr(pool, "pool", None) is not None else "sqlite"
            except Exception:
                db_backend = "unknown"
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": f"Registration error: {e}"},
                headers={
                    "X-TLDW-DB": db_backend,
                    "X-TLDW-CSRF-Enabled": "true" if bool(_csrf_globals.get("CSRF_ENABLED", None)) else "false",
                    "X-TLDW-Register-Error": str(e),
                    "X-TLDW-Register-Duration-ms": str(int(duration * 1000)),
                },
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during registration"
        )


#######################################################################################################################
#
# Test Endpoint

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> UserResponse:
    """
    Get current user information

    Returns:
        UserResponse with current user details
    """
    # Ensure UUID is a string
    user_uuid = current_user.get('uuid')
    if user_uuid and not isinstance(user_uuid, str):
        user_uuid = str(user_uuid)

    return UserResponse(
        id=current_user['id'],
        uuid=user_uuid or '',  # Provide empty string if missing
        username=current_user['username'],
        email=current_user['email'],
        role=current_user['role'],
        is_active=current_user.get('is_active', True),
        is_verified=current_user.get('is_verified', True),
        created_at=current_user.get('created_at', datetime.utcnow()),
        last_login=current_user.get('last_login'),
        storage_quota_mb=current_user.get('storage_quota_mb', 1000),
        storage_used_mb=current_user.get('storage_used_mb', 0.0)
    )


#
# End of auth.py
#######################################################################################################################
