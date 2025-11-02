from __future__ import annotations

import os
import uuid
import pytest

from tldw_Server_API.app.core.Usage.usage_tracker import log_llm_usage


async def _ensure_llm_tables(pool):
    if pool.pool:
        await pool.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_usage_log (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                key_id INTEGER,
                endpoint TEXT,
                operation TEXT,
                provider TEXT,
                model TEXT,
                status INTEGER,
                latency_ms INTEGER,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                prompt_cost_usd DOUBLE PRECISION,
                completion_cost_usd DOUBLE PRECISION,
                total_cost_usd DOUBLE PRECISION,
                currency TEXT,
                estimated BOOLEAN,
                request_id TEXT
            )
            """
        )
    else:
        await pool.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                key_id INTEGER,
                endpoint TEXT,
                operation TEXT,
                provider TEXT,
                model TEXT,
                status INTEGER,
                latency_ms INTEGER,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                prompt_cost_usd REAL,
                completion_cost_usd REAL,
                total_cost_usd REAL,
                currency TEXT,
                estimated INTEGER,
                request_id TEXT
            )
            """
        )


@pytest.mark.asyncio
async def test_usage_tracker_inserts_sqlite(monkeypatch):
    # Force SQLite single-user temp DB
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "ut-key-" + uuid.uuid4().hex)
    dburl = f"sqlite:///./Databases/users_test_ut_{uuid.uuid4().hex}.sqlite"
    monkeypatch.setenv("DATABASE_URL", dburl)

    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.AuthNZ.session_manager import reset_session_manager

    reset_settings()
    await reset_db_pool()
    await reset_session_manager()

    pool = await get_db_pool()
    await _ensure_llm_tables(pool)

    # Insert a usage row
    await log_llm_usage(
        user_id=1,
        key_id=None,
        endpoint="POST:/api/v1/chat/completions",
        operation="chat",
        provider="openai",
        model="gpt-3.5-turbo",
        status=200,
        latency_ms=123,
        prompt_tokens=1000,
        completion_tokens=500,
        request_id="req-xyz",
    )

    # Verify row exists with costs populated
    if pool.pool:
        row = await pool.fetchone("SELECT prompt_tokens, completion_tokens, total_cost_usd FROM llm_usage_log WHERE request_id = $1", "req-xyz")
    else:
        row = await pool.fetchone("SELECT prompt_tokens, completion_tokens, total_cost_usd FROM llm_usage_log WHERE request_id = ?", "req-xyz")

    assert row is not None
    pt = int(row["prompt_tokens"]) if isinstance(row, dict) else int(row[0])
    ct = int(row["completion_tokens"]) if isinstance(row, dict) else int(row[1])
    cost = float(row["total_cost_usd"]) if isinstance(row, dict) else float(row[2])
    assert pt == 1000 and ct == 500
    assert cost > 0.0
