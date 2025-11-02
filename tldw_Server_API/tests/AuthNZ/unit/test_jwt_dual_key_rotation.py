import pytest

from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.settings import Settings


def _svc(secret: str, secondary: str | None = None) -> JWTService:
    return JWTService(
        settings=Settings(
            AUTH_MODE="multi_user",
            JWT_SECRET_KEY=secret,
            JWT_SECONDARY_SECRET=secondary,
            JWT_ALGORITHM="HS256",
            ACCESS_TOKEN_EXPIRE_MINUTES=5,
            REFRESH_TOKEN_EXPIRE_DAYS=1,
        )
    )


def test_dual_key_decode_fallback_hs256():
    primary = "A" * 40
    secondary = "B" * 40

    # Encode with secondary-only service
    enc = _svc(secondary)
    token = enc.create_access_token(user_id=1, username="u", role="user")

    # Decode with primary service that has secondary fallback configured
    dec = _svc(primary, secondary)
    payload = dec.verify_token(token, token_type="access")

    assert payload["sub"] == "1"
    assert payload["type"] == "access"
