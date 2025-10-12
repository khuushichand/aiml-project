import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_provider_model_allowlists_sqlite(tmp_path):
    # Configure SQLite for AuthNZ
    os.environ['AUTH_MODE'] = 'multi_user'
    os.environ['JWT_SECRET_KEY'] = 'test-secret-key-for-allowlists-12345678901234567890'
    db_path = tmp_path / 'users.db'
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'

    # Reset singletons
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(pool.db_path))

    # Create a user
    async with pool.transaction() as conn:
        await conn.execute(
            "INSERT INTO users (username, email, password_hash, is_active) VALUES (?, ?, ?, 1)",
            ("vkuser", "vkuser@example.com", "x"),
        )
    user_id = await pool.fetchval("SELECT id FROM users WHERE username = ?", "vkuser")

    # Create a virtual key with allowlists
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    mgr = APIKeyManager()
    await mgr.initialize()
    res = await mgr.create_virtual_key(
        user_id=user_id,
        name="vk-allowlist",
        allowed_endpoints=["chat.completions"],
        allowed_providers=["openai"],
        allowed_models=["gpt-4o-mini"],
        budget_day_tokens=100000,
    )
    vkey = res['key']

    # Prepare TestClient
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.config import settings as app_settings
    app_settings['CSRF_ENABLED'] = False

    with TestClient(app) as client:
        # Disallowed model
        r = client.post(
            "/api/v1/chat/completions",
            headers={"X-API-KEY": vkey, "Content-Type": "application/json", "X-LLM-Provider": "openai"},
            json={"model": "not-allowed", "messages": [{"role": "user", "content": "hi"}]}
        )
        assert r.status_code == 403
        assert "Model 'not-allowed' not allowed" in r.text

        # Disallowed provider
        r = client.post(
            "/api/v1/chat/completions",
            headers={"X-API-KEY": vkey, "Content-Type": "application/json", "X-LLM-Provider": "anthropic"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]}
        )
        assert r.status_code == 403
        assert "Provider 'anthropic' not allowed" in r.text
