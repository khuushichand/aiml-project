# auth.py
# Description: Authentication endpoints for user login, logout, refresh, and registration
#
# Imports
from typing import Dict, Any, Optional, List
import os
import base64
import json
import secrets
from datetime import datetime, timezone, timedelta
from importlib import import_module
#
# 3rd-party imports
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form, Query
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
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
    UserResponse,
    SessionResponse,
    MFAChallengeResponse,
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
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.session_manager import SessionManager
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter
from tldw_Server_API.app.core.AuthNZ.input_validation import get_input_validator
from tldw_Server_API.app.core.AuthNZ.token_blacklist import get_token_blacklist
from tldw_Server_API.app.core.AuthNZ.orgs_teams import list_memberships_for_user
from tldw_Server_API.app.services.registration_service import RegistrationService
from tldw_Server_API.app.core.AuthNZ.auth_governor import get_auth_governor
from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings, get_profile
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.Audit.unified_audit_service import (
    AuditEventType,
    AuditContext
)
from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
    get_or_create_audit_service_for_user_id,
)
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
    InvalidRegistrationCodeError,
    DatabaseError,
    SessionError,
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

def _get_email_service():
    """Resolve the email service lazily to honor monkeypatched modules in tests."""
    module = import_module("tldw_Server_API.app.core.AuthNZ.email_service")
    return module.get_email_service()


def _get_mfa_service():
    """Resolve the MFA service lazily to honor monkeypatched modules in tests."""
    module = import_module("tldw_Server_API.app.core.AuthNZ.mfa_service")
    return module.get_mfa_service()


async def _ensure_mfa_available():
    """Validate MFA endpoints are allowed under current configuration."""
    settings = get_settings()
    if settings.AUTH_MODE != "multi_user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is only available in multi-user deployments",
        )
    try:
        is_pg = await is_postgres_backend()
    except Exception:
        logger.debug("Failed to determine database backend for MFA check", exc_info=True)
        is_pg = False
    if not is_pg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA requires a PostgreSQL database backend",
        )


def _mfa_setup_cache_key(user_id: int) -> str:
    return f"mfa:setup:{user_id}"


def _get_mfa_setup_ttl_seconds() -> int:
    try:
        ttl = int(os.getenv("MFA_SETUP_TTL_SECONDS", "600"))
    except (TypeError, ValueError):
        ttl = 600
    return max(ttl, 60)

def _mfa_login_cache_key(session_token: str) -> str:
    return f"mfa:login:{session_token}"


def _get_mfa_login_ttl_seconds() -> int:
    try:
        ttl = int(os.getenv("MFA_LOGIN_TTL_SECONDS", "600"))
    except (TypeError, ValueError):
        ttl = 600
    return max(ttl, 60)


#######################################################################################################################
#
# Enhanced Auth Schemas

class ForgotPasswordRequest(BaseModel):
    """Request for password reset."""
    email: EmailStr = Field(..., description="Email address to send reset link")


class ResetPasswordRequest(BaseModel):
    """Request to reset password with token."""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")


class VerifyEmailRequest(BaseModel):
    """Request to verify email."""
    token: str = Field(..., description="Email verification token")


class ResendVerificationRequest(BaseModel):
    """Request to resend verification email."""
    email: EmailStr = Field(..., description="Email address to resend verification")


class MFASetupResponse(BaseModel):
    """Response for MFA setup initiation."""
    secret: str = Field(..., description="TOTP secret (store securely)")
    qr_code: str = Field(..., description="QR code image as base64")
    backup_codes: List[str] = Field(..., description="Backup codes for recovery")


class MFAVerifyRequest(BaseModel):
    """Request to verify MFA setup."""
    token: str = Field(..., description="6-digit TOTP token")


class MFALoginRequest(BaseModel):
    """Request for MFA during login."""
    session_token: str = Field(..., description="Temporary session token from initial login")
    mfa_token: str = Field(..., description="6-digit TOTP token or backup code")


class LogoutRequest(BaseModel):
    """Request for logout."""
    all_devices: bool = Field(default=False, description="Logout from all devices")


#######################################################################################################################
#
# Register endpoint diagnostics (test-only)

async def _build_scope_claims(user_id: int) -> Dict[str, Any]:
    try:
        memberships = await list_memberships_for_user(int(user_id))
    except Exception:
        return {}

    team_ids = sorted({m.get("team_id") for m in memberships if m.get("team_id") is not None})
    org_ids = sorted({m.get("org_id") for m in memberships if m.get("org_id") is not None})

    claims: Dict[str, Any] = {}
    if team_ids:
        claims["team_ids"] = team_ids
    if org_ids:
        claims["org_ids"] = org_ids
    if len(team_ids) == 1:
        claims["active_team_id"] = team_ids[0]
    if len(org_ids) == 1:
        claims["active_org_id"] = org_ids[0]
    return claims

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
        scope_claims = await _build_scope_claims(int(current_user.get("id")))
        if scope_claims:
            add_claims.update(scope_claims)
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
        if settings.PII_REDACT_LOGS:
            logger.exception("Failed to mint self virtual key [redacted]")
        else:
            logger.exception(
                "Failed to mint self virtual key for user_id={} scope={} ttl_minutes={} error_type={}",
                current_user.get("id"),
                body.scope,
                body.ttl_minutes,
                type(e).__name__,
            )
        raise HTTPException(status_code=500, detail="Failed to mint token") from e

@router.post(
    "/login",
    response_model=TokenResponse | MFAChallengeResponse,
    dependencies=[Depends(check_auth_rate_limit)],
    responses={status.HTTP_202_ACCEPTED: {"model": MFAChallengeResponse}},
)
async def login(
    request: Request,
    response: Response,
    _diag=Depends(_login_runtime_diag),  # noqa: B008
    form_data: OAuth2PasswordRequestForm = Depends(),
    db=Depends(get_db_transaction),
    jwt_service: JWTService = Depends(get_jwt_service_dep),
    password_service: PasswordService = Depends(get_password_service_dep),
    session_manager: SessionManager = Depends(get_session_manager_dep),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    settings: Settings = Depends(get_settings)
) -> TokenResponse | MFAChallengeResponse:
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
    auth_gov = await get_auth_governor()
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
            is_locked, lockout_expires = await auth_gov.check_lockout(
                client_ip,
                attempt_type="login",
                rate_limiter=rate_limiter,
            )
        if is_locked:
            logger.warning(f"Login attempt from locked IP: {client_ip}")
            log_counter("auth_login_locked_ip")
            retry_after_seconds = 900
            if isinstance(lockout_expires, datetime):
                try:
                    from datetime import timezone as _tz

                    now = datetime.now(lockout_expires.tzinfo or _tz.utc)
                    retry_after_seconds = max(0, int((lockout_expires - now).total_seconds()))
                except Exception as exc:
                    # Fallback to default retry_after_seconds, but keep it observable.
                    logger.debug(
                        f"login: failed to compute lockout expiry; using default Retry-After: {exc}"
                    )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please try again later.",
                headers={"Retry-After": str(retry_after_seconds)}
            )

        # Sanitize input (lightweight). For login, avoid strict validation to not block
        # legitimate existing accounts (e.g., reserved usernames like 'admin').
        login_identifier = form_data.username.strip()

        # Helper to attempt audit logging without hard dependency (safe no-op in tests)
        async def _safe_audit_log_login(user_id: int, username: str, ip: str, ua: str, success: bool):
            try:
                svc = await get_or_create_audit_service_for_user_id(user_id)
                await svc.log_login(
                    user_id=user_id,
                    username=username,
                    ip_address=ip,
                    user_agent=ua,
                    success=success,
                )
                # Persist immediately for observability (tests/admin tools) without relying on background loops.
                flush_on_login = os.getenv("AUDIT_FLUSH_ON_LOGIN", "").lower() in {"1", "true", "yes", "on"}
                test_mode = os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
                if flush_on_login or test_mode:
                    await svc.flush()
            except Exception as exc:
                # Never block auth on audit issues
                logger.debug(
                    "Login audit failed for user_id={}: {}",
                    user_id,
                    exc,
                    exc_info=True,
                )

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
                await auth_gov.record_auth_failure(
                    identifier=client_ip,
                    attempt_type="login",
                    rate_limiter=rate_limiter,
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
                ip_result = await auth_gov.record_auth_failure(
                    identifier=client_ip,
                    attempt_type="login",
                    rate_limiter=rate_limiter,
                )
                user_result = await auth_gov.record_auth_failure(
                    identifier=user['username'],
                    attempt_type="login",
                    rate_limiter=rate_limiter,
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

        # Determine whether MFA is required (multi-user + PostgreSQL only).
        mfa_required = False
        if settings.AUTH_MODE == "multi_user":
            try:
                is_pg = await is_postgres_backend()
            except Exception:
                logger.debug("Failed to determine database backend for MFA login check", exc_info=True)
                is_pg = False
            if is_pg:
                try:
                    mfa_service = _get_mfa_service()
                    mfa_status = await mfa_service.get_user_mfa_status(int(user["id"]))
                    mfa_required = bool(mfa_status.get("enabled"))
                except Exception as exc:
                    logger.debug(
                        "MFA status lookup failed during login; treating as disabled: {}",
                        exc,
                    )

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

            if mfa_required:
                session_token = secrets.token_urlsafe(32)
                ttl_seconds = _get_mfa_login_ttl_seconds()
                payload = {
                    "user_id": int(user["id"]),
                    "session_id": int(session_id),
                }
                try:
                    await session_manager.store_ephemeral_value(
                        _mfa_login_cache_key(session_token),
                        json.dumps(payload),
                        ttl_seconds,
                    )
                except Exception as exc:
                    logger.error("Failed to cache MFA login session: {}", exc)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to initiate MFA login",
                    ) from exc
                response.status_code = status.HTTP_202_ACCEPTED
                log_counter("auth_login_mfa_required")
                try:
                    _finalize_login_diag(request, response)
                except Exception:
                    pass
                return MFAChallengeResponse(
                    session_token=session_token,
                    mfa_required=True,
                    expires_in=ttl_seconds,
                    message="MFA required. Submit your TOTP or backup code.",
                )

            # Create JWT tokens with session_id
            scope_claims = await _build_scope_claims(int(user["id"]))
            add_claims = dict(scope_claims)
            add_claims["session_id"] = session_id
            access_token = jwt_service.create_access_token(
                user_id=user['id'],
                username=user['username'],
                role=user['role'],
                additional_claims=add_claims
            )

            refresh_token = jwt_service.create_refresh_token(
                user_id=user['id'],
                username=user['username'],
                additional_claims=add_claims
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
            try:
                await rate_limiter.reset_failed_attempts(client_ip, "login")
                await rate_limiter.reset_failed_attempts(user['username'], "login")
            except Exception as rl_exc:
                # Guardrails must not break successful logins; log and continue.
                logger.debug(f"rate_limiter.reset_failed_attempts failed: {rl_exc}")

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
                response.headers["X-TLDW-Login-Error"] = "internal-error"
                _finalize_login_diag(request, response)
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred during login"
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
    data: Optional[LogoutRequest] = None,
    request: Request = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    session_manager: SessionManager = Depends(get_session_manager_dep),
    jwt_service: JWTService = Depends(get_jwt_service_dep),
) -> MessageResponse:
    """
    Logout current session or all sessions.

    Revokes the current token and optionally all user tokens/sessions.
    """
    start_time = time.perf_counter()
    log_counter("auth_logout_attempt")
    try:
        all_devices = bool(getattr(data, "all_devices", False)) if data is not None else False

        def _user_id_from(obj: Any) -> int:
            if isinstance(obj, dict):
                return int(obj.get("id") or obj.get("user_id") or 0)
            return int(getattr(obj, "id", 0) or 0)

        user_id = _user_id_from(current_user)

        # Attempt to revoke tokens based on the Authorization header.
        auth_header = request.headers.get("Authorization", "") if request is not None else ""
        token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
        blacklist = get_token_blacklist()
        payload = {}
        if token:
            try:
                payload = jwt_service.verify_token(token)
            except Exception:
                payload = {}

        if all_devices:
            # Revoke all tokens and sessions.
            count = await blacklist.revoke_all_user_tokens(
                user_id=user_id,
                reason="User requested logout from all devices",
            )
            try:
                await session_manager.revoke_all_user_sessions(user_id=user_id)
            except Exception as cleanup_exc:
                logger.error(f"Failed to revoke user sessions during logout-all: {cleanup_exc}")
            message = f"Logged out from {count} device(s)"
        else:
            # Revoke current access token and session.
            if token:
                try:
                    jti = jwt_service.extract_jti(token)
                except Exception:
                    jti = None
                if jti:
                    try:
                        exp = payload.get("exp")
                        expires_at = datetime.utcfromtimestamp(exp) if exp else datetime.utcnow()
                        await blacklist.revoke_token(
                            jti=jti,
                            expires_at=expires_at,
                            user_id=user_id,
                            token_type="access",
                            reason="User logout",
                        )
                    except Exception as revoke_exc:
                        logger.debug(f"Failed to revoke access token for logout: {revoke_exc}")
                session_id = payload.get("session_id")
                if session_id is not None:
                    try:
                        await session_manager.revoke_session(
                            session_id=session_id,
                            revoked_by=user_id,
                            reason="User logout",
                        )
                    except Exception as cleanup_exc:
                        logger.error(f"Failed to revoke session {session_id} during logout: {cleanup_exc}")
                else:
                    # Fallback to full session revoke if the token lacks a session id.
                    try:
                        await session_manager.revoke_all_user_sessions(user_id=user_id)
                    except Exception as cleanup_exc:
                        logger.error(f"Failed to revoke user sessions during logout: {cleanup_exc}")

            message = "Successfully logged out"

        # PII-aware logging
        try:
            _settings = get_settings()
        except Exception:
            _settings = None
        if _settings and getattr(_settings, 'PII_REDACT_LOGS', False):
            logger.info("User logged out [redacted]")
        else:
            logger.info(f"User logged out: {user_id}")

        log_counter("auth_logout_success")
        log_histogram("auth_logout_duration", time.perf_counter() - start_time)
        return MessageResponse(message=message, details={"user_id": user_id})

    except Exception as e:
        logger.error(f"Logout error: {e}")
        log_counter("auth_logout_error")
        log_histogram("auth_logout_duration", time.perf_counter() - start_time)
        # Even on error, return a generic logout message to avoid client lock-in.
        return MessageResponse(message="Successfully logged out", details={"user_id": None})


#######################################################################################################################
#
# Session Management (auth-scoped)

@router.get("/sessions", response_model=List[SessionResponse])
async def list_user_sessions(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    session_manager: SessionManager = Depends(get_session_manager_dep)
) -> List[SessionResponse]:
    """
    List all active sessions for the current user.
    """
    try:
        sessions = await session_manager.get_user_sessions(current_user['id'])

        return [
            SessionResponse(
                id=session['id'],
                ip_address=session.get('ip_address'),
                user_agent=session.get('user_agent'),
                created_at=session['created_at'],
                last_activity=session['last_activity'],
                expires_at=session['expires_at']
            )
            for session in sessions
        ]

    except Exception as e:
        logger.error(f"Failed to list user sessions: {e}")
        # In test mode, surface the underlying error to aid debugging
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve sessions: {e}"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions"
        )


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def revoke_session(
    session_id: int,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    session_manager: SessionManager = Depends(get_session_manager_dep)
) -> MessageResponse:
    """
    Revoke a specific session for the current user.
    """
    try:
        # Get session to verify ownership
        sessions = await session_manager.get_user_sessions(current_user['id'])
        session_ids = [s['id'] for s in sessions]

        if session_id not in session_ids:
            # Return success for idempotency - session is already not active
            logger.info(
                f"Session {session_id} not found for user {current_user['id']} - treating as already revoked"
            )
            return MessageResponse(
                message="Session revoked successfully",
                details={"session_id": session_id, "note": "Session was already inactive or did not exist"}
            )

        # Revoke the session
        await session_manager.revoke_session(
            session_id,
            revoked_by=current_user['id'],
            reason="User requested revocation"
        )

        logger.info(f"User {current_user['username']} revoked session {session_id}")

        return MessageResponse(
            message="Session revoked successfully",
            details={"session_id": session_id}
        )

    except HTTPException:
        raise
    except SessionError as e:
        logger.error(f"Failed to revoke session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session"
        )
    except Exception as e:
        logger.error(f"Unexpected error revoking session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while revoking the session"
        )


@router.post("/sessions/revoke-all", response_model=MessageResponse)
async def revoke_all_sessions(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    session_manager: SessionManager = Depends(get_session_manager_dep)
) -> MessageResponse:
    """
    Revoke all sessions for the current user.
    """
    try:
        count = await session_manager.revoke_all_user_sessions(
            current_user['id'],
            reason="User requested logout from all devices"
        )

        logger.info(f"User {current_user['username']} revoked all {count} sessions")

        return MessageResponse(
            message=f"Successfully revoked {count} sessions",
            details={"sessions_revoked": count}
        )

    except Exception as e:
        logger.error(f"Failed to revoke all sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke sessions"
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
            scope_claims = await _build_scope_claims(int(user["id"]))
            add_claims = dict(scope_claims)
            if session_id:
                add_claims["session_id"] = session_id
            if not add_claims:
                add_claims = None
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
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        log_counter("auth_refresh_unexpected_error")
        log_histogram("auth_refresh_duration", time.perf_counter() - start_time)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                response.headers["X-TLDW-Refresh-Stage"] = "unexpected"
                response.headers["X-TLDW-Refresh-Reason"] = "internal-error"
                response.headers["X-TLDW-Refresh-Duration-ms"] = str(int((time.perf_counter() - start_time) * 1000))
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during token refresh"
        )


#######################################################################################################################
#
# Password Reset Endpoints

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db=Depends(get_db_transaction),
    jwt_service: JWTService = Depends(get_jwt_service_dep),
    rate_limiter=Depends(get_rate_limiter_dep),
) -> Dict[str, str]:
    """
    Request password reset email.

    Sends a password reset link to the user's email if the account exists.
    Returns success even if email doesn't exist (security best practice).
    """
    try:
        # Get client info
        client_ip = request.client.host if request.client else "unknown"
        # Apply simple per-IP rate limit to mitigate abuse; on exceed, return generic success
        try:
            allowed, _ = await rate_limiter.check_rate_limit(
                identifier=f"ip:{client_ip}", endpoint="auth:forgot_password", limit=10, window_minutes=1
            )
            if not allowed:
                return {"message": "If the email exists, a reset link has been sent"}
        except Exception:
            pass

        # Validate email format
        validator = get_input_validator()
        is_valid, _error_msg = validator.validate_email(data.email)
        if not is_valid:
            # Return success anyway for security
            return {"message": "If the email exists, a reset link has been sent"}

        # Check if user exists
        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            user = await db.fetchrow(
                "SELECT id, username, email, is_active FROM users WHERE lower(email) = $1",
                data.email.lower(),
            )
        else:
            # SQLite
            cursor = await db.execute(
                "SELECT id, username, email, is_active FROM users WHERE lower(email) = ?",
                (data.email.lower(),),
            )
            user = await cursor.fetchone()
            if user:
                # Convert tuple to dict for SQLite
                user = {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "is_active": user[3],
                }

        if user and user["is_active"]:
            # Generate reset token
            reset_token = jwt_service.create_password_reset_token(
                user_id=user["id"],
                email=user["email"],
                expires_in_hours=1,
            )

            # Store token in database for validation
            is_pg_store = await is_postgres_backend()
            if is_pg_store:
                # PostgreSQL
                await db.execute(
                    """
                    INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, ip_address)
                    VALUES ($1, $2, $3, $4)
                    """,
                    user["id"],
                    jwt_service.hash_password_reset_token(reset_token),
                    datetime.utcnow() + timedelta(hours=1),
                    client_ip,
                )
            else:
                # SQLite
                await db.execute(
                    """
                    INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, ip_address)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        user["id"],
                        jwt_service.hash_password_reset_token(reset_token),
                        (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                        client_ip,
                    ),
                )
                await db.commit()

            # Send email
            email_service = _get_email_service()
            await email_service.send_password_reset_email(
                to_email=user["email"],
                username=user["username"],
                reset_token=reset_token,
                ip_address=client_ip,
            )

            logger.info(f"Password reset requested for user {user['id']} from IP {client_ip}")

        # Always return success for security
        return {"message": "If the email exists, a reset link has been sent"}

    except Exception as e:
        logger.error(f"Password reset error: {e}")
        # Still return success for security
        return {"message": "If the email exists, a reset link has been sent"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    data: ResetPasswordRequest,
    db=Depends(get_db_transaction),
    jwt_service: JWTService = Depends(get_jwt_service_dep),
    password_service: PasswordService = Depends(get_password_service_dep),
    request: Request = None,
    rate_limiter=Depends(get_rate_limiter_dep),
) -> Dict[str, str]:
    """
    Reset password with valid token.

    Validates the reset token and updates the user's password.
    """
    try:
        # Optional per-IP throttling
        try:
            ip_addr = request.client.host if request and getattr(request, "client", None) else "unknown"
            await rate_limiter.check_rate_limit(
                identifier=f"ip:{ip_addr}", endpoint="auth:reset_password", limit=20, window_minutes=5
            )
        except Exception:
            pass
        # Verify token
        try:
            payload = jwt_service.verify_token(data.token, token_type="password_reset")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token",
            )

        user_id = int(payload["sub"])
        if hasattr(jwt_service, "hash_password_reset_token_candidates"):
            hash_candidates = jwt_service.hash_password_reset_token_candidates(data.token)
        elif hasattr(jwt_service, "hash_password_reset_token"):
            hashed = jwt_service.hash_password_reset_token(data.token)
            hash_candidates = [hashed] if hashed else []
        elif hasattr(jwt_service, "hash_token_candidates"):
            # Backwards compatibility for older JWT service stubs
            hash_candidates = jwt_service.hash_token_candidates(data.token)
        else:
            hash_candidates = []
        if not hash_candidates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token",
            )

        # Check if token was already used
        is_pg = await is_postgres_backend()
        token_record_id: Optional[int] = None
        token_used_at: Optional[Any] = None
        if is_pg:
            # PostgreSQL
            record = await db.fetchrow(
                """
                SELECT id, used_at
                FROM password_reset_tokens
                WHERE user_id = $1 AND token_hash = ANY($2::text[])
                ORDER BY expires_at DESC
                LIMIT 1
                """,
                user_id,
                hash_candidates,
            )
            if record:
                token_record_id = record["id"]
                token_used_at = record["used_at"]
        else:
            # SQLite
            placeholders = ",".join("?" for _ in hash_candidates)
            params = [user_id, *hash_candidates]
            cursor = await db.execute(
                f"""
                SELECT id, used_at
                FROM password_reset_tokens
                WHERE user_id = ? AND token_hash IN ({placeholders})
                ORDER BY expires_at DESC
                LIMIT 1
                """,
                tuple(params),
            )
            row = await cursor.fetchone()
            if row:
                token_record_id = row[0]
                token_used_at = row[1]

        if not token_record_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token",
            )

        if token_used_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This reset token has already been used",
            )

        # Validate new password (service raises WeakPasswordError on failure)
        try:
            password_service.validate_password_strength(data.new_password)
        except WeakPasswordError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        # Hash new password
        new_password_hash = password_service.hash_password(data.new_password)

        # Update password
        if is_pg:
            # PostgreSQL
            await db.execute(
                "UPDATE users SET password_hash = $1, updated_at = $2 WHERE id = $3",
                new_password_hash,
                datetime.utcnow(),
                user_id,
            )
            # Mark token as used
            await db.execute(
                "UPDATE password_reset_tokens SET used_at = $1 WHERE id = $2",
                datetime.utcnow(),
                token_record_id,
            )
        else:
            # SQLite
            await db.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (new_password_hash, datetime.utcnow().isoformat(), user_id),
            )
            await db.execute(
                "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), token_record_id),
            )
            await db.commit()

        # Revoke all existing sessions for security
        blacklist = get_token_blacklist()
        await blacklist.revoke_all_user_tokens(user_id, "Password reset")

        if get_settings().PII_REDACT_LOGS:
            logger.info("Password reset completed for authenticated user (details redacted)")
        else:
            logger.info(f"Password reset completed for user {user_id}")
        return {"message": "Password has been reset successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password",
        )


# Email Verification Endpoints

@router.get("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    token: str = Query(..., description="Email verification token"),
    db=Depends(get_db_transaction),
    jwt_service: JWTService = Depends(get_jwt_service_dep),
) -> Dict[str, str]:
    """
    Verify email address with token.

    Marks the user's email as verified.
    """
    try:
        # Verify token
        try:
            payload = jwt_service.verify_token(token, token_type="email_verification")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token",
            )

        user_id = int(payload["sub"])
        email = payload["email"]

        # Update user's verification status
        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            await db.execute(
                "UPDATE users SET is_verified = true, updated_at = $1 WHERE id = $2 AND email = $3",
                datetime.utcnow(),
                user_id,
                email,
            )
        else:
            # SQLite
            await db.execute(
                "UPDATE users SET is_verified = 1, updated_at = ? WHERE id = ? AND email = ?",
                (datetime.utcnow().isoformat(), user_id, email),
            )
            await db.commit()

        if get_settings().PII_REDACT_LOGS:
            logger.info("Email verified for authenticated user (details redacted)")
        else:
            logger.info(f"Email verified for user {user_id}")
        return {"message": "Email verified successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify email",
        )


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(
    data: ResendVerificationRequest,
    db=Depends(get_db_transaction),
    jwt_service: JWTService = Depends(get_jwt_service_dep),
) -> Dict[str, str]:
    """
    Resend email verification link.

    Sends a new verification email if the account exists and is not verified.
    """
    try:
        # Check if user exists and needs verification
        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            user = await db.fetchrow(
                "SELECT id, username, email, is_verified FROM users WHERE lower(email) = $1",
                data.email.lower(),
            )
        else:
            # SQLite
            cursor = await db.execute(
                "SELECT id, username, email, is_verified FROM users WHERE lower(email) = ?",
                (data.email.lower(),),
            )
            user = await cursor.fetchone()
            if user:
                user = {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "is_verified": user[3],
                }

        if user and not user["is_verified"]:
            # Generate verification token
            verification_token = jwt_service.create_email_verification_token(
                user_id=user["id"],
                email=user["email"],
                expires_in_hours=24,
            )

            # Send email
            email_service = _get_email_service()
            await email_service.send_verification_email(
                to_email=user["email"],
                username=user["username"],
                verification_token=verification_token,
            )

            logger.info(f"Verification email resent for user {user['id']}")

        # Always return success for security
        return {"message": "If the account exists and needs verification, an email has been sent"}

    except Exception as e:
        logger.error(f"Resend verification error: {e}")
        return {"message": "If the account exists and needs verification, an email has been sent"}


# MFA Endpoints

@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user=Depends(get_current_active_user),
    db=Depends(get_db_transaction),
    session_manager: SessionManager = Depends(get_session_manager_dep),
) -> MFASetupResponse:
    """
    Initialize MFA setup for current user.

    Generates TOTP secret and backup codes but doesn't enable MFA yet.
    User must verify with a TOTP token first.
    """
    try:
        await _ensure_mfa_available()
        mfa_service = _get_mfa_service()

        # Check if MFA is already enabled
        try:
            mfa_status = await mfa_service.get_user_mfa_status(current_user.id)
        except DatabaseError as exc:
            logger.debug("MFA status lookup failed due to database error; assuming disabled: {}", exc)
            mfa_status = {"enabled": False}
        if mfa_status["enabled"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is already enabled for this account",
            )

        # Generate TOTP secret
        secret = mfa_service.generate_secret()

        # Generate QR code
        totp_uri = mfa_service.generate_totp_uri(secret, current_user.username)
        qr_code_bytes = mfa_service.generate_qr_code(totp_uri)
        qr_code_base64 = base64.b64encode(qr_code_bytes).decode("utf-8")

        # Generate backup codes
        backup_codes = mfa_service.generate_backup_codes()

        try:
            await session_manager.store_ephemeral_value(
                _mfa_setup_cache_key(current_user.id),
                secret,
                _get_mfa_setup_ttl_seconds(),
            )
        except Exception as exc:
            logger.error("Failed to cache MFA setup secret: {}", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to setup MFA",
            )

        return MFASetupResponse(
            secret=secret,
            qr_code=f"data:image/png;base64,{qr_code_base64}",
            backup_codes=backup_codes,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MFA setup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to setup MFA",
        )


@router.post("/mfa/verify", status_code=status.HTTP_200_OK)
async def verify_mfa_setup(
    data: MFAVerifyRequest,
    request: Request,
    current_user=Depends(get_current_active_user),
    rate_limiter=Depends(get_rate_limiter_dep),
    session_manager: SessionManager = Depends(get_session_manager_dep),
) -> Dict[str, Any]:
    """
    Verify and enable MFA with TOTP token.

    Completes MFA setup by verifying the user can generate valid tokens.
    """
    try:
        await _ensure_mfa_available()
        mfa_service = _get_mfa_service()

        secret = await session_manager.get_ephemeral_value(_mfa_setup_cache_key(current_user.id))
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA setup not found or expired. Please restart setup.",
            )

        # Basic per-user rate limit for MFA verification attempts
        try:
            allowed, _meta = await rate_limiter.check_user_rate_limit(current_user.id, endpoint="auth:mfa_verify")
            if not allowed:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts")
        except HTTPException:
            raise
        except Exception:
            pass
        # Verify TOTP token
        if not mfa_service.verify_totp(secret, data.token):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid TOTP token",
            )

        # Generate final backup codes
        backup_codes = mfa_service.generate_backup_codes()

        # Enable MFA
        success = await mfa_service.enable_mfa(
            user_id=current_user.id,
            secret=secret,
            backup_codes=backup_codes,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to enable MFA",
            )

        await session_manager.delete_ephemeral_value(_mfa_setup_cache_key(current_user.id))

        # Send email with backup codes
        email_service = _get_email_service()
        client_ip = request.client.host if request.client else "unknown"

        await email_service.send_mfa_enabled_email(
            to_email=current_user.email,
            username=current_user.username,
            backup_codes=backup_codes,
            ip_address=client_ip,
        )

        logger.info(f"MFA enabled for user {current_user.id}")
        return {"message": "MFA has been enabled successfully", "backup_codes": backup_codes}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MFA verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify MFA",
        )


@router.post("/mfa/disable", status_code=status.HTTP_200_OK)
async def disable_mfa(
    current_user=Depends(get_current_active_user),
    password: str = Form(..., description="Current password for verification"),
    db=Depends(get_db_transaction),
    password_service: PasswordService = Depends(get_password_service_dep),
) -> Dict[str, str]:
    """
    Disable MFA for current user.

    Requires password verification for security.
    """
    try:
        await _ensure_mfa_available()
        user_id = getattr(current_user, "id", None)
        if user_id is None and isinstance(current_user, dict):
            user_id = current_user.get("id")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        user_record = await fetch_active_user_by_id(db, int(user_id))
        if not isinstance(user_record, dict):
            try:
                user_record = dict(user_record) if user_record is not None else None
            except Exception:
                user_record = None
        if not user_record:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        password_hash = user_record.get("password_hash")
        if not isinstance(password_hash, str) or not password_hash:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        try:
            password_service.hasher.verify(password_hash, password)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            ) from None

        mfa_service = _get_mfa_service()
        success = await mfa_service.disable_mfa(int(user_id))

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to disable MFA",
            )

        logger.info(f"MFA disabled for user {current_user.id}")
        return {"message": "MFA has been disabled"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MFA disable error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable MFA",
        )


@router.post("/mfa/login", response_model=TokenResponse)
async def mfa_login(
    data: MFALoginRequest,
    request: Request,
    response: Response,
    db=Depends(get_db_transaction),
    jwt_service: JWTService = Depends(get_jwt_service_dep),
    session_manager: SessionManager = Depends(get_session_manager_dep),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """
    Complete login with MFA token.
    """
    start_time = time.perf_counter()
    log_counter("auth_mfa_login_attempt")
    try:
        await _ensure_mfa_available()

        cache_key = _mfa_login_cache_key(data.session_token)
        payload_raw = await session_manager.get_ephemeral_value(cache_key)
        if not payload_raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA session expired or invalid",
            )
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            payload = {}

        session_id = payload.get("session_id")
        user_id = payload.get("user_id")
        if not session_id or not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA session expired or invalid",
            )

        user_id = int(user_id)
        session_id = int(session_id)

        # Basic per-user rate limit for MFA login attempts
        try:
            allowed, _meta = await rate_limiter.check_user_rate_limit(user_id, endpoint="auth:mfa_login")
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many MFA attempts. Please try again later.",
                )
        except HTTPException:
            raise
        except Exception:
            pass

        user = await fetch_active_user_by_id(db, user_id)
        if not isinstance(user, dict):
            try:
                user = dict(user) if user is not None else None
            except Exception:
                user = None
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        mfa_service = _get_mfa_service()
        mfa_status = await mfa_service.get_user_mfa_status(user_id)
        if not mfa_status.get("enabled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is not enabled for this account",
            )

        secret = await mfa_service.get_user_totp_secret(user_id)
        token_ok = False
        if secret and mfa_service.verify_totp(secret, data.mfa_token):
            token_ok = True
        else:
            token_ok = await mfa_service.verify_backup_code(user_id, data.mfa_token)

        if not token_ok:
            log_counter("auth_mfa_login_invalid_token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        scope_claims = await _build_scope_claims(user_id)
        add_claims = dict(scope_claims)
        add_claims["session_id"] = session_id
        access_token = jwt_service.create_access_token(
            user_id=user_id,
            username=user.get("username", ""),
            role=user.get("role", "user"),
            additional_claims=add_claims,
        )
        refresh_token = jwt_service.create_refresh_token(
            user_id=user_id,
            username=user.get("username", ""),
            additional_claims=add_claims,
        )

        await session_manager.update_session_tokens(
            session_id=session_id,
            access_token=access_token,
            refresh_token=refresh_token,
        )

        await update_user_last_login(db, user_id, datetime.utcnow())

        # Audit log successful login
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "Unknown")
        async def _safe_audit_log_login(user_id: int, username: str, ip: str, ua: str, success: bool):
            try:
                svc = await get_or_create_audit_service_for_user_id(user_id)
                await svc.log_login(
                    user_id=user_id,
                    username=username,
                    ip_address=ip,
                    user_agent=ua,
                    success=success,
                )
                flush_on_login = os.getenv("AUDIT_FLUSH_ON_LOGIN", "").lower() in {"1", "true", "yes", "on"}
                test_mode = os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
                if flush_on_login or test_mode:
                    await svc.flush()
            except Exception as exc:
                logger.debug(
                    "MFA login audit failed for user_id={}: {}",
                    user_id,
                    exc,
                    exc_info=True,
                )

        await _safe_audit_log_login(
            user_id=user_id,
            username=str(user.get("username", "")),
            ip=client_ip,
            ua=user_agent,
            success=True,
        )

        # Reset failed login attempts on successful MFA login
        if getattr(rate_limiter, 'enabled', False):
            try:
                await rate_limiter.reset_failed_attempts(client_ip, "login")
                await rate_limiter.reset_failed_attempts(user.get("username", ""), "login")
            except Exception as rl_exc:
                logger.debug(f"rate_limiter.reset_failed_attempts failed: {rl_exc}")

        try:
            await session_manager.delete_ephemeral_value(cache_key)
        except Exception:
            pass

        log_counter("auth_login_success")
        log_counter("auth_mfa_login_success")
        log_histogram("auth_login_duration", time.perf_counter() - start_time)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    except HTTPException:
        log_counter("auth_mfa_login_http_error")
        log_histogram("auth_login_duration", time.perf_counter() - start_time)
        raise
    except Exception as e:
        logger.error(f"MFA login error: {e}")
        log_counter("auth_mfa_login_unexpected_error")
        log_histogram("auth_login_duration", time.perf_counter() - start_time)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete MFA login",
        )


#######################################################################################################################
#
# Registration Endpoint

@router.post("/register", response_model=RegistrationResponse, dependencies=[Depends(check_auth_rate_limit)])
async def register(
    payload: RegisterRequest,
    http_request: Request,
    response: Response,
    _diag=Depends(_register_runtime_diag),  # noqa: B008
    registration_service: RegistrationService = Depends(get_registration_service_dep)
) -> RegistrationResponse:
    """
    Register a new user

    Creates a new user account with the provided credentials.
    May require a registration code if configured.

    Args:
        payload: RegisterRequest with user details

    Returns:
        RegistrationResponse with user information

    Raises:
        HTTPException: 400 if validation fails, 409 if user exists
    """
    start_time = time.perf_counter()
    log_counter("auth_register_attempt")
    settings = get_settings()
    try:
        # Hard constraint for local-single-user profile: do not allow
        # registration of additional users beyond the bootstrapped admin.
        profile = get_profile()
        if isinstance(profile, str) and profile.strip().lower() in {"local-single-user", "single_user"}:
            if getattr(settings, "PII_REDACT_LOGS", False):
                logger.warning("Registration attempt rejected in local-single-user profile [redacted]")
            else:
                logger.warning(
                    "Registration attempt rejected in local-single-user profile for username={}",
                    payload.username,
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User registration is not allowed in local-single-user profile",
            )

        # Register the user
        user_info = await registration_service.register_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            registration_code=payload.registration_code,
        )

        logger.info(f"New user registered: {user_info['username']} (ID: {user_info['user_id']})")

        # If using SQLite for AuthNZ, generate a per-user API key so UI can present it
        api_key_value = None
        try:
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
        _finalize_register_diag(http_request, response)

        async def _safe_audit_log_registration_code() -> None:
            try:
                code_id = user_info.get("registration_code_id")
                if not payload.registration_code or code_id is None:
                    return
                svc = await get_or_create_audit_service_for_user_id(int(user_info["user_id"]))
                correlation_id = (
                    http_request.headers.get("X-Correlation-ID")
                    or getattr(http_request.state, "correlation_id", None)
                )
                request_id = (
                    http_request.headers.get("X-Request-ID")
                    or getattr(http_request.state, "request_id", None)
                    or ""
                )
                ctx = AuditContext(
                    user_id=str(user_info["user_id"]),
                    correlation_id=correlation_id,
                    request_id=request_id,
                    ip_address=(http_request.client.host if http_request.client else None),
                    user_agent=http_request.headers.get("user-agent"),
                    endpoint=str(http_request.url.path),
                    method=http_request.method,
                )
                await svc.log_event(
                    event_type=AuditEventType.DATA_UPDATE,
                    context=ctx,
                    resource_type="registration_code",
                    resource_id=str(code_id),
                    action="registration_code.redeemed",
                    metadata={
                        "registration_code_id": code_id,
                        "org_id": user_info.get("registration_code_org_id"),
                        "org_role": user_info.get("registration_code_org_role"),
                        "team_id": user_info.get("registration_code_team_id"),
                    },
                )
            except Exception as exc:
                logger.debug("Registration code audit failed: {}", exc)

        await _safe_audit_log_registration_code()
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
                response.headers["X-TLDW-Register-Error"] = "duplicate-user"
            except Exception:
                pass
        _finalize_register_diag(http_request, response)
        detail = "Username or email already exists."
        if payload.registration_code:
            detail = (
                "Username or email already exists. If you're joining an organization, "
                "log in and accept the invite at /webui/accept-invite.html "
                "or POST /api/v1/orgs/invites/accept."
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail
        ) from e
    except WeakPasswordError as e:
        logger.warning(f"Registration failed - weak password: {e}")
        log_counter("auth_register_weak_password")
        log_histogram("auth_register_duration", time.perf_counter() - start_time)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                response.headers["X-TLDW-Register-Error"] = "weak-password"
            except Exception:
                pass
        _finalize_register_diag(http_request, response)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password does not meet requirements."
        ) from e
    except InvalidRegistrationCodeError as e:
        logger.warning(f"Registration failed - invalid code: {e}")
        log_counter("auth_register_invalid_code")
        log_histogram("auth_register_duration", time.perf_counter() - start_time)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                response.headers["X-TLDW-Register-Error"] = "invalid-registration-code"
            except Exception:
                pass
        _finalize_register_diag(http_request, response)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid registration code."
        ) from e
    except RegistrationError as e:
        logger.error(f"Registration error: {e}")
        log_counter("auth_register_error")
        log_histogram("auth_register_duration", time.perf_counter() - start_time)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                response.headers["X-TLDW-Register-Error"] = "registration-error"
            except Exception:
                pass
        _finalize_register_diag(http_request, response)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed."
        ) from e
    except HTTPException:
        # Propagate explicit HTTPException responses (for example the
        # local-single-user profile guard) without wrapping them as 500.
        _finalize_register_diag(http_request, response)
        raise
    except Exception as e:
        logger.error(f"Unexpected registration error: {e}")
        log_counter("auth_register_unexpected_error")
        log_histogram("auth_register_duration", time.perf_counter() - start_time)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                response.headers["X-TLDW-Register-Error"] = "internal-error"
            except Exception:
                pass
        duration = time.perf_counter() - start_time
        _finalize_register_diag(http_request, response)
        if os.getenv("TEST_MODE", "").lower() in ("1","true","yes"):
            try:
                pool = await get_db_pool()
                db_backend = "postgres" if getattr(pool, "pool", None) is not None else "sqlite"
            except Exception:
                db_backend = "unknown"
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "An error occurred during registration"},
                headers={
                    "X-TLDW-DB": db_backend,
                    "X-TLDW-CSRF-Enabled": "true" if bool(_csrf_globals.get("CSRF_ENABLED", None)) else "false",
                    "X-TLDW-Register-Error": "internal-error",
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
    return UserResponse(
        id=current_user['id'],
        uuid=current_user.get('uuid') or None,
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
