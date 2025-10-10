import os
import pytest
import uuid
import hmac
import hashlib
import asyncio

import asyncpg
from fastapi.testclient import TestClient

# Skip this module unless explicitly enabled (requires Postgres + network)
RUN_PG_INTEGRATION = os.getenv("RUN_PG_INTEGRATION", "0").lower() in {"1", "true", "yes"}
pytestmark = pytest.mark.skipif(not RUN_PG_INTEGRATION, reason="Postgres integration tests disabled (set RUN_PG_INTEGRATION=1 to enable)")

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.settings import get_settings


def _hash_api_key(secret: str, api_key: str) -> str:
    key = secret[:32].encode() if len(secret) >= 32 else secret.encode()
    return hmac.new(key, api_key.encode(), hashlib.sha256).hexdigest()


def test_media_add_requires_media_create(isolated_test_environment):
    client, db_name = isolated_test_environment
    # Prepare: create a user without roles and an active API key for that user
    dsn = os.environ.get("DATABASE_URL")
    if not dsn or not dsn.startswith("postgresql"):
        pytest.skip("PostgreSQL DATABASE_URL not configured; skipping integration test")

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
            secret = os.environ.get("JWT_SECRET_KEY", "test-secret-key-for-testing-only")
            key_hash = _hash_api_key(secret, full_key)
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

    user_id, api_key = asyncio.get_event_loop().run_until_complete(_setup_user_and_key())

    # Attempt to call media add without media.create permission -> expect 403
    headers = {"X-API-KEY": api_key}
    r = client.post("/api/v1/media/add", headers=headers, json={})
    assert r.status_code == 403, r.text
