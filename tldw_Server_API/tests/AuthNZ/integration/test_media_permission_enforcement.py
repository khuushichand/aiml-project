import os
import uuid
import hmac
import asyncio

import asyncpg
import pytest
from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
from tldw_Server_API.app.core.AuthNZ.db_config import AuthDatabaseConfig
from tldw_Server_API.app.core.AuthNZ.crypto_utils import derive_hmac_key_candidates


pytestmark = pytest.mark.integration


def _hash_api_key(api_key: str) -> str:
    keys = derive_hmac_key_candidates()
    if not keys:
        raise RuntimeError("No HMAC key candidates available")
    return hmac.new(keys[0], api_key.encode(), "sha256").hexdigest()


def test_media_add_requires_media_create(isolated_test_environment):
    client, _db_name = isolated_test_environment
    # Prepare: create a user without roles and an active API key for that user
    dsn = get_settings().DATABASE_URL
    assert dsn and dsn.startswith("postgresql"), "AuthNZ Postgres test fixture not configured"

    async def _setup_user_and_key():
        conn = await asyncpg.connect(dsn)
        try:
            # Create user without any roles
            user_uuid = str(uuid.uuid4())
            row = await conn.fetchrow(
                """
                INSERT INTO users (uuid, username, email, password_hash, role, is_active, is_verified)
                VALUES ($1, $2, $3, $4, 'user', true, true)
                RETURNING id
                """,
                user_uuid,
                f"permtest_{user_uuid[:8]}",
                f"permtest_{user_uuid[:8]}@example.com",
                "unused",
            )
            user_id = row["id"]

            # Generate API key and insert hashed record
            full_key = f"tldw_{uuid.uuid4().hex}"
            key_hash = _hash_api_key(full_key)
            await conn.execute(
                """
                INSERT INTO api_keys (user_id, key_hash, key_prefix, name, scope, status)
                VALUES ($1, $2, $3, $4, $5, 'active')
                """,
                user_id,
                key_hash,
                "tldw_",
                "perm test",
                "read",
            )
            # Ensure RBAC tables exist for permission overrides (tests run against ephemeral DB)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS permissions (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    description TEXT,
                    category VARCHAR(100)
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_permissions (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
                    granted BOOLEAN NOT NULL DEFAULT TRUE,
                    expires_at TIMESTAMP,
                    PRIMARY KEY (user_id, permission_id)
                )
                """
            )
            await conn.execute(
                """
                INSERT INTO permissions (name, description, category)
                VALUES ('media.create', 'Create media', 'media')
                ON CONFLICT (name) DO NOTHING
                """
            )
            await conn.execute(
                """
                INSERT INTO user_permissions (user_id, permission_id, granted)
                SELECT $1, id, FALSE
                FROM permissions
                WHERE name = 'media.create'
                ON CONFLICT (user_id, permission_id)
                DO UPDATE SET granted = EXCLUDED.granted
                """,
                user_id,
            )
            return user_id, full_key
        finally:
            await conn.close()

    user_id, api_key = asyncio.run(_setup_user_and_key())

    # Attempt to call media add without media.create permission -> expect 403
    headers = {"X-API-KEY": api_key}
    previous_mode = os.environ.get("AUTH_MODE")
    config = AuthDatabaseConfig()
    try:
        os.environ["AUTH_MODE"] = "multi_user"
        reset_settings()
        config.settings = get_settings()
        config.reset()
        assert get_settings().AUTH_MODE == "multi_user"
        # Provide minimal valid payload so request passes validation and hits permission check
        payload = {
            "media_type": "video",
            "urls": "https://example.com/test.mp4",
        }
        # Endpoint expects multipart/form-data, so submit via form fields
        r = client.post("/api/v1/media/add", headers=headers, data=payload)
        assert r.status_code == 403, r.text
    finally:
        if previous_mode is None:
            os.environ.pop("AUTH_MODE", None)
        else:
            os.environ["AUTH_MODE"] = previous_mode
        reset_settings()
        config.settings = get_settings()
        config.reset()
