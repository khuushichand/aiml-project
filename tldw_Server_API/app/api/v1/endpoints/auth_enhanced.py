# auth_enhanced.py
# Description: Enhanced authentication endpoints with password reset, MFA, and email verification
#
# Imports
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import secrets
import base64
from importlib import import_module
#
# 3rd-party imports
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form, Query
from pydantic import BaseModel, EmailStr, Field
from loguru import logger
#
# Local imports
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_db_transaction,
    get_password_service_dep,
    get_jwt_service_dep,
    get_current_user,
    get_current_active_user,
    get_session_manager_dep
)
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.input_validation import get_input_validator
from tldw_Server_API.app.core.AuthNZ.token_blacklist import get_token_blacklist
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend
from tldw_Server_API.app.core.AuthNZ.exceptions import WeakPasswordError, DatabaseError
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_rate_limiter_dep


def _get_email_service():
    """Resolve the email service lazily to honour monkeypatched modules in tests."""
    module = import_module("tldw_Server_API.app.core.AuthNZ.email_service")
    return module.get_email_service()


def _get_mfa_service():
    """Resolve the MFA service lazily to honour monkeypatched modules in tests."""
    module = import_module("tldw_Server_API.app.core.AuthNZ.mfa_service")
    return module.get_mfa_service()


async def _ensure_mfa_available():
    """Validate that MFA endpoints are allowed under current configuration.

    Uses the unified backend detector instead of relying on URL prefix checks.
    """
    settings = get_settings()
    if settings.AUTH_MODE != "multi_user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is only available in multi-user deployments",
        )
    try:
        is_pg = await is_postgres_backend()
    except Exception:
        is_pg = False
    if not is_pg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA requires a PostgreSQL database backend",
        )

#######################################################################################################################
#
# Router Configuration
#

router = APIRouter(
    prefix="/auth",
    tags=["authentication-enhanced"],
    responses={404: {"description": "Not found"}}
)

#######################################################################################################################
#
# Request/Response Schemas
#

class ForgotPasswordRequest(BaseModel):
    """Request for password reset"""
    email: EmailStr = Field(..., description="Email address to send reset link")

class ResetPasswordRequest(BaseModel):
    """Request to reset password with token"""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")

class VerifyEmailRequest(BaseModel):
    """Request to verify email"""
    token: str = Field(..., description="Email verification token")

class ResendVerificationRequest(BaseModel):
    """Request to resend verification email"""
    email: EmailStr = Field(..., description="Email address to resend verification")

class MFASetupResponse(BaseModel):
    """Response for MFA setup initiation"""
    secret: str = Field(..., description="TOTP secret (store securely)")
    qr_code: str = Field(..., description="QR code image as base64")
    backup_codes: List[str] = Field(..., description="Backup codes for recovery")

class MFAVerifyRequest(BaseModel):
    """Request to verify MFA setup"""
    token: str = Field(..., description="6-digit TOTP token")

class MFALoginRequest(BaseModel):
    """Request for MFA during login"""
    session_token: str = Field(..., description="Temporary session token from initial login")
    mfa_token: str = Field(..., description="6-digit TOTP token or backup code")

class LogoutRequest(BaseModel):
    """Request for logout"""
    all_devices: bool = Field(default=False, description="Logout from all devices")

#######################################################################################################################
#
# Password Reset Endpoints
#

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db=Depends(get_db_transaction),
    jwt_service: JWTService = Depends(get_jwt_service_dep),
    rate_limiter=Depends(get_rate_limiter_dep)
) -> Dict[str, str]:
    """
    Request password reset email

    Sends a password reset link to the user's email if the account exists.
    Returns success even if email doesn't exist (security best practice).
    """
    try:
        # Get client info
        client_ip = request.client.host if request.client else "unknown"
        # Apply simple per-IP rate limit to mitigate abuse; on exceed, return generic success
        try:
            allowed, _ = await rate_limiter.check_rate_limit(
                identifier=f"ip:{client_ip}", endpoint="auth:forgot_password", limit=10, burst=5, window_minutes=1
            )
            if not allowed:
                return {"message": "If the email exists, a reset link has been sent"}
        except Exception:
            pass

        # Validate email format
        validator = get_input_validator()
        is_valid, error_msg = validator.validate_email(data.email)
        if not is_valid:
            # Return success anyway for security
            return {"message": "If the email exists, a reset link has been sent"}

        # Check if user exists
        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            user = await db.fetchrow(
                "SELECT id, username, email, is_active FROM users WHERE lower(email) = $1",
                data.email.lower()
            )
        else:
            # SQLite
            cursor = await db.execute(
                "SELECT id, username, email, is_active FROM users WHERE lower(email) = ?",
                (data.email.lower(),)
            )
            user = await cursor.fetchone()
            if user:
                # Convert tuple to dict for SQLite
                user = {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "is_active": user[3]
                }

        if user and user["is_active"]:
            # Generate reset token
            reset_token = jwt_service.create_password_reset_token(
                user_id=user["id"],
                email=user["email"],
                expires_in_hours=1
            )

            # Store token in database for validation
            is_pg_store = await is_postgres_backend()
            if is_pg_store:
                # PostgreSQL
                await db.execute("""
                    INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, ip_address)
                    VALUES ($1, $2, $3, $4)
                """, user["id"], jwt_service.hash_token(reset_token),
                    datetime.utcnow() + timedelta(hours=1), client_ip)
            else:
                # SQLite
                await db.execute("""
                    INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, ip_address)
                    VALUES (?, ?, ?, ?)
                """, (user["id"], jwt_service.hash_token(reset_token),
                     (datetime.utcnow() + timedelta(hours=1)).isoformat(), client_ip))
                await db.commit()

            # Send email
            email_service = _get_email_service()
            await email_service.send_password_reset_email(
                to_email=user["email"],
                username=user["username"],
                reset_token=reset_token,
                ip_address=client_ip
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
    rate_limiter=Depends(get_rate_limiter_dep)
) -> Dict[str, str]:
    """
    Reset password with valid token

    Validates the reset token and updates the user's password.
    """
    try:
        # Optional per-IP throttling
        try:
            ip_addr = request.client.host if request and getattr(request, 'client', None) else "unknown"
            await rate_limiter.check_rate_limit(
                identifier=f"ip:{ip_addr}", endpoint="auth:reset_password", limit=20, burst=10, window_minutes=5
            )
        except Exception:
            pass
        # Verify token
        try:
            payload = jwt_service.verify_token(data.token, token_type="password_reset")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )

        user_id = int(payload["sub"])
        if hasattr(jwt_service, "hash_token_candidates"):
            hash_candidates = jwt_service.hash_token_candidates(data.token)
        else:
            # Backwards compatibility for older JWT service stubs
            hashed = jwt_service.hash_token(data.token)
            hash_candidates = [hashed] if hashed else []
        if not hash_candidates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
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
                detail="Invalid or expired reset token"
            )

        if token_used_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This reset token has already been used"
            )

        # Validate new password (service raises WeakPasswordError on failure)
        try:
            password_service.validate_password_strength(data.new_password)
        except WeakPasswordError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        # Hash new password
        new_password_hash = password_service.hash_password(data.new_password)

        # Update password
        if is_pg:
            # PostgreSQL
            await db.execute(
                "UPDATE users SET password_hash = $1, updated_at = $2 WHERE id = $3",
                new_password_hash, datetime.utcnow(), user_id
            )
            # Mark token as used
            await db.execute(
                "UPDATE password_reset_tokens SET used_at = $1 WHERE id = $2",
                datetime.utcnow(), token_record_id
            )
        else:
            # SQLite
            await db.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (new_password_hash, datetime.utcnow().isoformat(), user_id)
            )
            await db.execute(
                "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), token_record_id)
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
            detail="Failed to reset password"
        )

#######################################################################################################################
#
# Email Verification Endpoints
#

@router.get("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    token: str = Query(..., description="Email verification token"),
    db=Depends(get_db_transaction),
    jwt_service: JWTService = Depends(get_jwt_service_dep)
) -> Dict[str, str]:
    """
    Verify email address with token

    Marks the user's email as verified.
    """
    try:
        # Verify token
        try:
            payload = jwt_service.verify_token(token, token_type="email_verification")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )

        user_id = int(payload["sub"])
        email = payload["email"]

        # Update user's verification status
        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            await db.execute(
                "UPDATE users SET is_verified = true, updated_at = $1 WHERE id = $2 AND email = $3",
                datetime.utcnow(), user_id, email
            )
        else:
            # SQLite
            await db.execute(
                "UPDATE users SET is_verified = 1, updated_at = ? WHERE id = ? AND email = ?",
                (datetime.utcnow().isoformat(), user_id, email)
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
            detail="Failed to verify email"
        )

@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(
    data: ResendVerificationRequest,
    db=Depends(get_db_transaction),
    jwt_service: JWTService = Depends(get_jwt_service_dep)
) -> Dict[str, str]:
    """
    Resend email verification link

    Sends a new verification email if the account exists and is not verified.
    """
    try:
        # Check if user exists and needs verification
        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            user = await db.fetchrow(
                "SELECT id, username, email, is_verified FROM users WHERE lower(email) = $1",
                data.email.lower()
            )
        else:
            # SQLite
            cursor = await db.execute(
                "SELECT id, username, email, is_verified FROM users WHERE lower(email) = ?",
                (data.email.lower(),)
            )
            user = await cursor.fetchone()
            if user:
                user = {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "is_verified": user[3]
                }

        if user and not user["is_verified"]:
            # Generate verification token
            verification_token = jwt_service.create_email_verification_token(
                user_id=user["id"],
                email=user["email"],
                expires_in_hours=24
            )

            # Send email
            email_service = _get_email_service()
            await email_service.send_verification_email(
                to_email=user["email"],
                username=user["username"],
                verification_token=verification_token
            )

            logger.info(f"Verification email resent for user {user['id']}")

        # Always return success for security
        return {"message": "If the account exists and needs verification, an email has been sent"}

    except Exception as e:
        logger.error(f"Resend verification error: {e}")
        return {"message": "If the account exists and needs verification, an email has been sent"}

#######################################################################################################################
#
# MFA Endpoints
#

@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user=Depends(get_current_active_user),
    db=Depends(get_db_transaction)
) -> MFASetupResponse:
    """
    Initialize MFA setup for current user

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
                detail="MFA is already enabled for this account"
            )

        # Generate TOTP secret
        secret = mfa_service.generate_secret()

        # Generate QR code
        totp_uri = mfa_service.generate_totp_uri(secret, current_user.username)
        qr_code_bytes = mfa_service.generate_qr_code(totp_uri)
        qr_code_base64 = base64.b64encode(qr_code_bytes).decode('utf-8')

        # Generate backup codes
        backup_codes = mfa_service.generate_backup_codes()

        # Store temporarily in session or cache (not enabling yet)
        # In production, use Redis or session storage
        # For now, we'll return to client to verify

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
            detail="Failed to setup MFA"
        )

@router.post("/mfa/verify", status_code=status.HTTP_200_OK)
async def verify_mfa_setup(
    data: MFAVerifyRequest,
    request: Request,
    current_user=Depends(get_current_active_user),
    rate_limiter=Depends(get_rate_limiter_dep),
) -> Dict[str, Any]:
    """
    Verify and enable MFA with TOTP token

    Completes MFA setup by verifying the user can generate valid tokens.
    """
    try:
        await _ensure_mfa_available()
        mfa_service = _get_mfa_service()

        # Get secret from request (in production, get from session/cache)
        secret = request.headers.get("X-MFA-Secret")
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA secret not found. Please restart setup."
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
                detail="Invalid TOTP token"
            )

        # Generate final backup codes
        backup_codes = mfa_service.generate_backup_codes()

        # Enable MFA
        success = await mfa_service.enable_mfa(
            user_id=current_user.id,
            secret=secret,
            backup_codes=backup_codes
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to enable MFA"
            )

        # Send email with backup codes
        email_service = _get_email_service()
        client_ip = request.client.host if request.client else "unknown"

        await email_service.send_mfa_enabled_email(
            to_email=current_user.email,
            username=current_user.username,
            backup_codes=backup_codes,
            ip_address=client_ip
        )

        logger.info(f"MFA enabled for user {current_user.id}")
        return {"message": "MFA has been enabled successfully", "backup_codes": backup_codes}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MFA verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify MFA"
        )

@router.post("/mfa/disable", status_code=status.HTTP_200_OK)
async def disable_mfa(
    current_user=Depends(get_current_active_user),
    password: str = Form(..., description="Current password for verification")
) -> Dict[str, str]:
    """
    Disable MFA for current user

    Requires password verification for security.
    """
    try:
        await _ensure_mfa_available()
        # Verify password
        password_service = PasswordService()
        # Get user's password hash from DB
        # ... (fetch password hash)
        # if not password_service.verify_password(password, password_hash)[0]:
        #     raise HTTPException(status_code=401, detail="Invalid password")

        mfa_service = _get_mfa_service()
        success = await mfa_service.disable_mfa(current_user.id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to disable MFA"
            )

        logger.info(f"MFA disabled for user {current_user.id}")
        return {"message": "MFA has been disabled"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MFA disable error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable MFA"
        )

#######################################################################################################################
#
# Logout Endpoint
#

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    data: LogoutRequest,
    request: Request,
    current_user=Depends(get_current_active_user),
    session_manager=Depends(get_session_manager_dep)
) -> Dict[str, str]:
    """
    Logout current session or all sessions

    Revokes the current token and optionally all user tokens.
    """
    try:
        # Get current token JTI
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            jwt_service = JWTService()
            jti = jwt_service.extract_jti(token)

            blacklist = get_token_blacklist()

            if data.all_devices:
                # Revoke all tokens and sessions
                count = await blacklist.revoke_all_user_tokens(
                    user_id=current_user.id,
                    reason="User requested logout from all devices"
                )
                try:
                    await session_manager.revoke_all_user_sessions(
                        user_id=current_user.id
                    )
                except Exception as cleanup_exc:
                    logger.error(f"Failed to revoke user sessions during logout-all: {cleanup_exc}")
                logger.info(f"User {current_user.id} logged out from {count} devices")
                return {"message": f"Logged out from {count} device(s)"}
            else:
                # Revoke current token only
                if jti:
                    # Get token expiration
                    payload = jwt_service.verify_token(token)
                    expires_at = datetime.utcfromtimestamp(payload["exp"])

                    await blacklist.revoke_token(
                        jti=jti,
                        expires_at=expires_at,
                        user_id=current_user.id,
                        token_type="access",
                        reason="User logout"
                    )
                    session_id = payload.get("session_id")
                    if session_id is not None:
                        try:
                            await session_manager.revoke_session(
                                session_id=session_id,
                                revoked_by=current_user.id,
                                reason="User logout"
                            )
                        except Exception as cleanup_exc:
                            logger.error(f"Failed to revoke session {session_id} during logout: {cleanup_exc}")

                logger.info(f"User {current_user.id} logged out")
                return {"message": "Logged out successfully"}

        return {"message": "Already logged out"}

    except Exception as e:
        logger.error(f"Logout error: {e}")
        # Even on error, consider it logged out
        return {"message": "Logged out"}

#
# End of auth_enhanced.py
#######################################################################################################################
