from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.repos.mfa_repo import AuthnzMfaRepo
from tldw_Server_API.app.core.AuthNZ.settings import Settings


@pytest.mark.asyncio
async def test_authnz_mfa_repo_basic_sqlite(tmp_path: Path):
    """AuthnzMfaRepo should update and read MFA fields on SQLite."""
    db_path = tmp_path / "authnz_mfa_repo.sqlite"
    settings = Settings(
        AUTH_MODE="multi_user",
        DATABASE_URL=f"sqlite:///{db_path}",
        JWT_SECRET_KEY="test-secret-key-32-characters-minimum!",
        ENABLE_REGISTRATION=True,
        REQUIRE_REGISTRATION_CODE=False,
        RATE_LIMIT_ENABLED=False,
    )

    pool = DatabasePool(settings)
    await pool.initialize()

    try:
        # Ensure MFA-related columns exist on users
        column_rows = await pool.fetchall("PRAGMA table_info(users)")
        column_names = {
            row["name"] if isinstance(row, dict) else row[1] for row in column_rows
        }
        required_columns = {
            "two_factor_enabled": "INTEGER DEFAULT 0",
            "totp_secret": "TEXT",
            "backup_codes": "TEXT",
            "updated_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        }
        for column, decl in required_columns.items():
            if column not in column_names:
                await pool.execute(f"ALTER TABLE users ADD COLUMN {column} {decl}")

        async with pool.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, username, email, password_hash, is_active)
                VALUES (?, ?, ?, ?, 1)
                """,
                (1, "mfa-user", "mfa@example.com", "hashed-password"),
            )

        repo = AuthnzMfaRepo(pool)
        now = datetime.now(timezone.utc)

        await repo.set_mfa_config(
            user_id=1,
            encrypted_secret="enc-secret",
            backup_codes_json='["code1","code2"]',
            updated_at=now,
        )

        encrypted = await repo.get_encrypted_totp_secret(1)
        assert encrypted == "enc-secret"

        status_row = await repo.get_mfa_status_row(1)
        assert status_row is not None
        assert bool(status_row.get("two_factor_enabled"))
        assert bool(status_row.get("has_secret"))
        assert bool(status_row.get("has_backup_codes"))

        # Repo should expose raw backup_codes JSON and allow updates
        raw_codes = await repo.get_backup_codes_json(1)
        assert raw_codes == '["code1","code2"]'

        await repo.update_backup_codes_json(
            user_id=1,
            backup_codes_json='["code2"]',
        )
        raw_codes_updated = await repo.get_backup_codes_json(1)
        assert raw_codes_updated == '["code2"]'

        await repo.clear_mfa_config(user_id=1, updated_at=now)

        encrypted_after = await repo.get_encrypted_totp_secret(1)
        assert encrypted_after is None

        status_after = await repo.get_mfa_status_row(1)
        assert status_after is not None
        assert not bool(status_after.get("two_factor_enabled"))
        assert not bool(status_after.get("has_secret"))
        assert not bool(status_after.get("has_backup_codes"))
    finally:
        await pool.close()
