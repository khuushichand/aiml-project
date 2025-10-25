from datetime import datetime

import pytest

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.session_manager import SessionManager
from tldw_Server_API.app.core.AuthNZ.settings import Settings, reset_settings
from tldw_Server_API.app.core.AuthNZ.token_blacklist import TokenBlacklist


@pytest.mark.asyncio
async def test_revoke_all_user_tokens_counts_tokens(tmp_path):
    reset_settings()
    db_path = tmp_path / "token_blacklist_counts.sqlite"
    settings = Settings(
        AUTH_MODE="multi_user",
        DATABASE_URL=f"sqlite:///{db_path}",
        JWT_SECRET_KEY="token-blacklist-secret-1234567890abcd",
        ENABLE_REGISTRATION=True,
        REQUIRE_REGISTRATION_CODE=False,
        RATE_LIMIT_ENABLED=False,
    )

    pool = DatabasePool(settings)
    await pool.initialize()

    async with pool.transaction() as conn:
        await conn.execute(
            """
            INSERT INTO users (id, username, email, password_hash, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (
                1,
                "charlie",
                "charlie@example.com",
                "hashed-password",
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat(),
            ),
        )

    session_manager = SessionManager(db_pool=pool, settings=settings)
    await session_manager.initialize()

    jwt_service = JWTService(settings=settings)
    access_token = jwt_service.create_access_token(user_id=1, username="charlie", role="user")
    refresh_token = jwt_service.create_refresh_token(user_id=1, username="charlie")

    await session_manager.create_session(
        user_id=1,
        access_token=access_token,
        refresh_token=refresh_token,
        ip_address="127.0.0.1",
        user_agent="pytest-suite",
    )

    blacklist = TokenBlacklist(db_pool=pool, settings=settings)
    count = await blacklist.revoke_all_user_tokens(user_id=1, reason="test-revoke", revoked_by=99)

    assert count == 2

    rows = await pool.fetchall(
        "SELECT token_type FROM token_blacklist WHERE user_id = ? ORDER BY token_type",
        1,
    )
    token_types = []
    for row in rows:
        if isinstance(row, dict):
            token_types.append(row["token_type"])
        else:
            try:
                token_types.append(row["token_type"])
            except (TypeError, KeyError):
                token_types.append(row[0])
    assert token_types == ["access", "refresh"]

    await session_manager.shutdown()
    await pool.close()
    reset_settings()
