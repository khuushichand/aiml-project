# v1-endpoint-deps.py
# Description: This file is to serve as a sink for dependencies across the v1 endpoints.
# Imports
#
# 3rd-party Libraries
from fastapi import Header, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from loguru import logger
from starlette import status
from typing import Optional

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.AuthNZ.settings import get_settings as get_auth_settings
from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
from tldw_Server_API.app.core.AuthNZ.exceptions import InvalidTokenError, TokenExpiredError
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager

#
# Local Imports
#
#######################################################################################################################
#
# Static Variables
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
#
# Functions:

def _normalize_header_value(value):
    """Return string header value or None; ignore FastAPI Header param objects when called directly."""
    return value if isinstance(value, str) else None


async def verify_token(
    request: Request,
    Token: str = Header(None),
    x_api_key: str = Header(None, alias="X-API-KEY")
):  # Check both Token and X-API-KEY headers
    # Ensure we only work with raw strings even when called directly in tests
    Token = _normalize_header_value(Token)
    x_api_key = _normalize_header_value(x_api_key)

    if settings.get("SINGLE_USER_MODE"):
        # Single-user mode: prefer X-API-KEY; allow Token for legacy direct tests
        if not x_api_key and not Token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token (X-API-KEY required).")

        if x_api_key:
            # Compare against AuthNZ settings singleton (NEW tests use this value)
            try:
                expected_key = get_auth_settings().SINGLE_USER_API_KEY
            except Exception:
                expected_key = None
            if not expected_key:
                logger.critical("SINGLE_USER_API_KEY missing from AuthNZ settings in single-user mode.")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server authentication misconfigured (API key missing).")
            if x_api_key != expected_key:
                logger.warning("Invalid X-API-KEY provided in single-user mode.")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token.")
        else:
            if Token:
                logger.warning("Deprecated header 'Token' used; switch to 'Authorization: Bearer' or 'X-API-KEY'.")
            # Legacy path: Token header is compared against core config dict (older tests patch this)
            expected_token = settings.get("SINGLE_USER_API_KEY")
            if not expected_token:
                logger.critical("SINGLE_USER_API_KEY is not configured in core settings for single-user mode.")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server authentication misconfigured (API key missing).")
            if Token != expected_token:
                got_preview = Token[:10] + "..." if isinstance(Token, str) else "<non-string>"
                exp_preview = expected_token[:5] + "..." if isinstance(expected_token, str) else "<non-string>"
                logger.warning(f"Invalid token received. Expected: '{exp_preview}', Got: '{got_preview}'")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token.")

    else:
        # Multi-user mode: accept either a JWT token (Token header) or an X-API-KEY validated against the DB
        if Token:
            logger.warning("Deprecated header 'Token' used; switch to 'Authorization: Bearer'.")
            jwt_service = get_jwt_service()
            try:
                payload = jwt_service.decode_access_token(Token)
                user_id = payload.get("user_id") or payload.get("sub")
                if not user_id:
                    logger.warning("JWT token missing user_id/sub claim")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token: missing user information"
                    )
                logger.debug(f"JWT token validated for user_id: {user_id}")
            except (InvalidTokenError, TokenExpiredError) as e:
                logger.warning(f"JWT validation failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid or expired token: {e}"
                )
            except Exception as e:
                logger.error(f"Unexpected error validating JWT: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error validating authentication token"
                )
        elif x_api_key:
            try:
                api_mgr = await get_api_key_manager()
                client_ip = None
                client = getattr(request, "client", None)
                if client is not None:
                    client_ip = getattr(client, "host", None)
                key_info = await api_mgr.validate_api_key(x_api_key, ip_address=client_ip)
                if not key_info:
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
                # Success: we don't attach user here; endpoints that need it should use get_current_user
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error validating API key: {e}")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication (Token or X-API-KEY)")

    return True


#
# End of v1-endpoint-deps.py
#######################################################################################################################
