from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.mfa_repo import AuthnzMfaRepo


@pytest.mark.asyncio
async def test_authnz_mfa_repo_basic_sqlite(isolated_test_environment: tuple) -> None:
    """AuthnzMfaRepo should update and read MFA fields on SQLite."""
    _client, _db_name = isolated_test_environment
    pool = await get_db_pool()

    # Ensure MFA-related columns exist on users for the selected backend.
    if getattr(pool, "pool", None):
        pg_required = {
            "two_factor_enabled": "BOOLEAN DEFAULT FALSE",
            "totp_secret": "TEXT",
            "backup_codes": "TEXT",
            "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        }
        for column, decl in pg_required.items():
            await pool.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column} {decl}")
    else:
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
        if hasattr(conn, "fetchrow"):
            await conn.execute(
                """
                INSERT INTO users (id, username, email, password_hash, is_active)
                VALUES ($1, $2, $3, $4, TRUE)
                """,
                1,
                "mfa-user",
                "mfa@example.com",
                "hashed-password",
            )
        else:
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
