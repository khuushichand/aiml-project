from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tldw_Server_API.app.core.AuthNZ.byok_rotation import rotate_byok_secrets
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
    build_secret_payload,
    decrypt_byok_payload,
    dumps_envelope,
    encrypt_byok_payload,
    loads_envelope,
)
from tldw_Server_API.app.core.AuthNZ.repos.user_provider_secrets_repo import (
    AuthnzUserProviderSecretsRepo,
)
from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB, reset_users_db


def _b64_key(byte_char: bytes) -> str:
    return base64.b64encode(byte_char * 32).decode("ascii")


@pytest.mark.asyncio
async def test_byok_rotation_reencrypts_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "users.db"
    old_key = _b64_key(b"a")
    new_key = _b64_key(b"b")

    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", old_key)

    reset_settings()
    await reset_db_pool()
    await reset_users_db()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(pool.db_path))
    users_db = UsersDB(pool)
    await users_db.initialize()
    user = await users_db.create_user(
        username="byok-rotate-user",
        email="byok-rotate@example.com",
        password_hash="hashed",
        role="user",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        storage_quota_mb=5120,
        uuid_value=uuid.uuid4(),
    )

    payload = build_secret_payload("sk-rotate-test")
    encrypted_blob = dumps_envelope(encrypt_byok_payload(payload))

    repo = AuthnzUserProviderSecretsRepo(pool)
    await repo.upsert_secret(
        user_id=int(user["id"]),
        provider="openai",
        encrypted_blob=encrypted_blob,
        key_hint="test",
        metadata=None,
        updated_at=datetime.now(timezone.utc),
    )

    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", new_key)
    monkeypatch.setenv("BYOK_SECONDARY_ENCRYPTION_KEY", old_key)
    reset_settings()

    summary = await rotate_byok_secrets(batch_size=10)
    assert summary.tables["user_provider_secrets"].updated == 1

    monkeypatch.setenv("BYOK_SECONDARY_ENCRYPTION_KEY", "")
    reset_settings()

    row = await pool.fetchone(
        "SELECT encrypted_blob FROM user_provider_secrets WHERE user_id = ? AND provider = ?",
        (int(user["id"]), "openai"),
    )
    assert row
    decrypted = decrypt_byok_payload(loads_envelope(row["encrypted_blob"]))
    assert decrypted["api_key"] == "sk-rotate-test"
