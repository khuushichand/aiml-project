import os
import uuid
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_api_key_rotation_marks_old_key_and_links():
    # Configure environment for SQLite multi-user mode
    os.environ["AUTH_MODE"] = "multi_user"
    os.environ["JWT_SECRET_KEY"] = "x" * 64
    db_dir = Path("Databases")
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / f"test_api_key_rotation_{uuid.uuid4().hex}.sqlite"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager, APIKeyStatus

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(pool.db_path))

    # Create test user
    async with pool.transaction() as conn:
        await conn.execute(
            """
            INSERT INTO users (username, email, password_hash, is_active)
            VALUES (?, ?, ?, 1)
            """,
            ("rotate_user", "rotate@example.com", "hash"),
        )
    user_id = await pool.fetchval(
        "SELECT id FROM users WHERE username = ?", "rotate_user"
    )

    mgr = APIKeyManager(pool)
    await mgr.initialize()

    created = await mgr.create_api_key(user_id=user_id, name="primary")
    rotated = await mgr.rotate_api_key(created["id"], user_id, expires_in_days=30)

    # Ensure a new key was created and linked
    assert rotated["id"] != created["id"]
    assert rotated["key"].startswith("tldw_")

    # Old key should be marked as rotated and reference the new key
    old_row = await pool.fetchone(
        "SELECT status, rotated_to FROM api_keys WHERE id = ?", created["id"]
    )
    assert dict(old_row)["status"] == APIKeyStatus.ROTATED.value
    assert dict(old_row)["rotated_to"] == rotated["id"]

    # New key should carry back-reference to the original
    new_row = await pool.fetchone(
        "SELECT rotated_from FROM api_keys WHERE id = ?", rotated["id"]
    )
    assert dict(new_row)["rotated_from"] == created["id"]

    # Cleanup test database artifacts
    try:
        if db_path.exists():
            db_path.unlink()
        wal = db_path.with_suffix(".sqlite-wal")
        shm = db_path.with_suffix(".sqlite-shm")
        for extra in (wal, shm):
            if extra.exists():
                extra.unlink()
    except Exception:
        pass
