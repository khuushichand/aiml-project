# v1-endpoint-deps.py
# Description: This file is to serve as a sink for dependencies across the v1 endpoints.
# Imports
#
# 3rd-party Libraries
from fastapi import Header, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from loguru import logger
from starlette import status

#
# Local Imports
#
#######################################################################################################################
#
# Static Variables
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
#
# Functions:

async def verify_token(
    request: Request,
    Token: str = Header(None),
    x_api_key: str = Header(None, alias="X-API-KEY")
):  # Check both Token and X-API-KEY headers
    if not getattr(verify_token, "_deprecated_warned", False):
        logger.warning(
            "verify_token dependency is deprecated and now returns HTTP 410. "
            "Migrate callers to get_auth_principal/get_request_user."
        )
        setattr(verify_token, "_deprecated_warned", True)

    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Deprecated auth dependency: verify_token has been removed. "
            "Use get_auth_principal/get_request_user from AuthNZ dependencies."
        ),
        headers={"Deprecation": "true"},
    )


#
# End of v1-endpoint-deps.py
#######################################################################################################################
