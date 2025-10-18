import os
import uuid
import hmac
import asyncio

import asyncpg
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import derive_hmac_key


def _hash_api_key(api_key: str) -> str:
    hmac_key = derive_hmac_key()
    return hmac.new(hmac_key, api_key.encode(), "sha256").hexdigest()


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
            return user_id, full_key
        finally:
            await conn.close()

    user_id, api_key = asyncio.run(_setup_user_and_key())

    # Attempt to call media add without media.create permission -> expect 403
    headers = {"X-API-KEY": api_key}
    r = client.post("/api/v1/media/add", headers=headers, json={})
    assert r.status_code == 403, r.text
