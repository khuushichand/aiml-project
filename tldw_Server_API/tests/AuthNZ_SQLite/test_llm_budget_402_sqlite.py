import os
from datetime import datetime, timedelta
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


@pytest.mark.asyncio
async def test_llm_budget_middleware_blocks_disallowed_endpoint_sqlite(tmp_path):
    os.environ['AUTH_MODE'] = 'multi_user'
    os.environ['JWT_SECRET_KEY'] = 'test-secret-key-for-endpoint-403-12345678901234567890'
    db_path = tmp_path / 'users_endpoint.db'
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'

    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(pool.db_path))

    async with pool.transaction() as conn:
        await conn.execute(
            "INSERT INTO users (username, email, password_hash, is_active) VALUES (?, ?, ?, 1)",
            ("endpointuser", "endpointuser@example.com", "x"),
        )
    user_id = await pool.fetchval("SELECT id FROM users WHERE username = ?", "endpointuser")

    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    mgr = APIKeyManager()
    await mgr.initialize()
    vk = await mgr.create_virtual_key(
        user_id=user_id,
        name="vk-endpoint",
        allowed_endpoints=["chat.completions"],
        budget_day_tokens=1000,
    )
    vkey = vk['key']

    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.config import settings as app_settings
    app_settings['CSRF_ENABLED'] = False

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/embeddings",
            headers={"X-API-KEY": vkey, "Content-Type": "application/json"},
            json={"model": "text-embedding-3-small", "input": "hello"},
        )
        assert r.status_code == 403, r.text
        assert "Endpoint 'embeddings' not allowed" in r.text


@pytest.mark.asyncio
async def test_llm_budget_middleware_enforces_usd_budgets_sqlite(tmp_path):
    os.environ['AUTH_MODE'] = 'multi_user'
    os.environ['JWT_SECRET_KEY'] = 'test-secret-key-for-usd-402-12345678901234567890'
    db_path = tmp_path / 'users_usd.db'
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'

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
            ("usduser", "usduser@example.com", "x"),
        )
    user_id = await pool.fetchval("SELECT id FROM users WHERE username = ?", "usduser")

    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    mgr = APIKeyManager()
    await mgr.initialize()

    # Daily USD budget scenario
    vk_day = await mgr.create_virtual_key(
        user_id=user_id,
        name="vk-usd-day",
        allowed_endpoints=["chat.completions"],
        budget_day_usd=0.05,
    )
    key_day = vk_day['key']
    key_day_id = vk_day['id']

    async with pool.transaction() as conn:
        await conn.execute(
            """
            INSERT INTO llm_usage_log (
                ts, user_id, key_id, endpoint, operation, provider, model, status, latency_ms,
                prompt_tokens, completion_tokens, total_tokens,
                prompt_cost_usd, completion_cost_usd, total_cost_usd, currency, estimated
            ) VALUES (
                CURRENT_TIMESTAMP, ?, ?, 'api', 'chat', 'openai', 'gpt-4o-mini', 200, 120,
                50, 50, 100,
                0.03, 0.04, 0.07, 'USD', 0
            )
            """,
            (user_id, key_day_id),
        )

    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.config import settings as app_settings
    app_settings['CSRF_ENABLED'] = False

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/chat/completions",
            headers={"X-API-KEY": key_day, "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 402, r.text
        assert "budget_exceeded" in r.text

    # Monthly USD budget scenario (no daily limit set)
    vk_month = await mgr.create_virtual_key(
        user_id=user_id,
        name="vk-usd-month",
        allowed_endpoints=["chat.completions"],
        budget_month_usd=0.10,
    )
    key_month = vk_month['key']
    key_month_id = vk_month['id']

    month_ts = datetime.utcnow().replace(microsecond=0) - timedelta(days=2)
    async with pool.transaction() as conn:
        await conn.execute(
            """
            INSERT INTO llm_usage_log (
                ts, user_id, key_id, endpoint, operation, provider, model, status, latency_ms,
                prompt_tokens, completion_tokens, total_tokens,
                prompt_cost_usd, completion_cost_usd, total_cost_usd, currency, estimated
            ) VALUES (
                ?, ?, ?, 'api', 'chat', 'openai', 'gpt-4o-mini', 200, 90,
                30, 30, 60,
                0.02, 0.10, 0.12, 'USD', 0
            )
            """,
            (month_ts.isoformat(), user_id, key_month_id),
        )

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/chat/completions",
            headers={"X-API-KEY": key_month, "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "ping"}]},
        )
        assert r.status_code == 402, r.text
        assert "budget_exceeded" in r.text
