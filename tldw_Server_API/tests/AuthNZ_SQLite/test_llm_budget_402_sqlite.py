import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_llm_budget_middleware_returns_402_on_overage(tmp_path):
    # Configure SQLite for AuthNZ
    os.environ['AUTH_MODE'] = 'multi_user'
    os.environ['JWT_SECRET_KEY'] = 'test-secret-key-for-budget-402-12345678901234567890'
    db_path = tmp_path / 'users.db'
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'

    # Reset singletons and ensure schema
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
            ("budgetuser", "budgetuser@example.com", "x"),
        )
    user_id = await pool.fetchval("SELECT id FROM users WHERE username = ?", "budgetuser")

    # Create a virtual key with small daily token budget and allow chat.completions
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    mgr = APIKeyManager()
    await mgr.initialize()
    vk = await mgr.create_virtual_key(
        user_id=user_id,
        name="vk-budget",
        allowed_endpoints=["chat.completions"],
        budget_day_tokens=100,
    )
    key_id = vk['id']
    vkey = vk['key']

    # Insert usage that exceeds the daily token budget (150 >= 100)
    async with pool.transaction() as conn:
        await conn.execute(
            """
            INSERT INTO llm_usage_log (
                ts, user_id, key_id, endpoint, operation, provider, model, status, latency_ms,
                prompt_tokens, completion_tokens, total_tokens,
                prompt_cost_usd, completion_cost_usd, total_cost_usd, currency, estimated
            ) VALUES (
                CURRENT_TIMESTAMP, ?, ?, 'api', 'chat', 'openai', 'gpt-4o-mini', 200, 100,
                50, 100, 150,
                0.02, 0.04, 0.06, 'USD', 0
            )
            """,
            (user_id, key_id),
        )

    # Prepare TestClient and disable CSRF for this test
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.config import settings as app_settings
    app_settings['CSRF_ENABLED'] = False

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/chat/completions",
            headers={"X-API-KEY": vkey, "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]}
        )
        assert r.status_code == 402, r.text
        assert "budget_exceeded" in r.text

