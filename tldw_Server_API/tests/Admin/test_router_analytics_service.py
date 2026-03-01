from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_router_analytics_service


def _setup_env(tmp_path) -> None:
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = "unit-test-router-analytics"
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'users_test_router_analytics_service.db'}"


async def _ensure_router_usage_seed_rows() -> int:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool

    pool = await get_db_pool()
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE,
            username TEXT UNIQUE,
            email TEXT,
            password_hash TEXT,
            is_active INTEGER DEFAULT 1
        )
        """
    )
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
            request_id TEXT,
            remote_ip TEXT,
            user_agent TEXT,
            token_name TEXT,
            conversation_id TEXT
        )
        """
    )

    cols = {row["name"] for row in await pool.fetchall("PRAGMA table_info(llm_usage_log)")}
    if "remote_ip" not in cols:
        await pool.execute("ALTER TABLE llm_usage_log ADD COLUMN remote_ip TEXT")
    if "user_agent" not in cols:
        await pool.execute("ALTER TABLE llm_usage_log ADD COLUMN user_agent TEXT")
    if "token_name" not in cols:
        await pool.execute("ALTER TABLE llm_usage_log ADD COLUMN token_name TEXT")
    if "conversation_id" not in cols:
        await pool.execute("ALTER TABLE llm_usage_log ADD COLUMN conversation_id TEXT")

    user_uuid = str(uuid.uuid4())
    await pool.execute(
        "INSERT OR IGNORE INTO users (uuid, username, email, password_hash, is_active) VALUES (?,?,?,?,1)",
        user_uuid,
        "router_analytics_user",
        "router_analytics_user@example.com",
        "x",
    )
    user_id = int(await pool.fetchval("SELECT id FROM users WHERE username = ?", "router_analytics_user"))

    # Fixed UTC timestamps keep range math deterministic for tests.
    await pool.execute(
        """
        INSERT INTO llm_usage_log (
            ts, user_id, key_id, endpoint, operation, provider, model, status, latency_ms,
            prompt_tokens, completion_tokens, total_tokens, prompt_cost_usd, completion_cost_usd, total_cost_usd,
            currency, estimated, request_id, remote_ip, user_agent, token_name, conversation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        "2026-03-01 10:20:00",
        user_id,
        11,
        "/api/v1/chat/completions",
        "chat",
        "openai",
        "gpt-4o-mini",
        200,
        1000,
        10,
        20,
        30,
        0.01,
        0.02,
        0.03,
        "USD",
        0,
        "req-1",
        "127.0.0.1",
        "curl/8.8.0",
        "Admin",
        "conv-1",
    )
    await pool.execute(
        """
        INSERT INTO llm_usage_log (
            ts, user_id, key_id, endpoint, operation, provider, model, status, latency_ms,
            prompt_tokens, completion_tokens, total_tokens, prompt_cost_usd, completion_cost_usd, total_cost_usd,
            currency, estimated, request_id, remote_ip, user_agent, token_name, conversation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        "2026-03-01 10:25:00",
        user_id,
        12,
        "/api/v1/chat/completions",
        "chat",
        "groq",
        "llama-3.3-70b",
        200,
        500,
        30,
        10,
        40,
        0.03,
        0.01,
        0.04,
        "USD",
        0,
        "req-2",
        "10.0.0.5",
        "python-httpx/1.0",
        "Ops",
        "conv-2",
    )
    await pool.execute(
        """
        INSERT INTO llm_usage_log (
            ts, user_id, key_id, endpoint, operation, provider, model, status, latency_ms,
            prompt_tokens, completion_tokens, total_tokens, prompt_cost_usd, completion_cost_usd, total_cost_usd,
            currency, estimated, request_id, remote_ip, user_agent, token_name, conversation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        "2026-03-01 10:26:00",
        user_id,
        12,
        "/api/v1/chat/completions",
        "chat",
        "groq",
        "llama-3.3-70b",
        500,
        200,
        5,
        0,
        5,
        0.0,
        0.0,
        0.0,
        "USD",
        1,
        "req-3",
        "10.0.0.5",
        "python-httpx/1.0",
        "Ops",
        "conv-2",
    )
    await pool.execute(
        """
        INSERT INTO llm_usage_log (
            ts, user_id, key_id, endpoint, operation, provider, model, status, latency_ms,
            prompt_tokens, completion_tokens, total_tokens, prompt_cost_usd, completion_cost_usd, total_cost_usd,
            currency, estimated, request_id, remote_ip, user_agent, token_name, conversation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        "2026-03-01 10:27:00",
        user_id,
        13,
        "/api/v1/chat/completions",
        "chat",
        "anthropic",
        "claude-3.5",
        503,
        300,
        7,
        2,
        9,
        0.0,
        0.0,
        0.0,
        "USD",
        1,
        "req-4",
        None,
        None,
        None,
        "conv-3",
    )
    return user_id


def _single_user_principal(user_id: int) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=user_id,
        subject="single_user",
        roles=["admin"],
        permissions=["*"],
        is_admin=True,
    )


@pytest.mark.asyncio
async def test_router_analytics_status_and_breakdowns_sqlite(monkeypatch, tmp_path):
    _setup_env(tmp_path)
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.session_manager import reset_session_manager
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    await reset_db_pool()
    reset_settings()
    await reset_session_manager()
    user_id = await _ensure_router_usage_seed_rows()
    pool = await get_db_pool()
    principal = _single_user_principal(user_id)

    monkeypatch.setattr(
        admin_router_analytics_service,
        "_utcnow",
        lambda: datetime(2026, 3, 1, 10, 30, tzinfo=timezone.utc),
    )

    status = await admin_router_analytics_service.get_router_analytics_status(
        principal=principal,
        db=pool,
        range_value="1h",
        org_id=None,
        provider=None,
        model=None,
        token_id=None,
        granularity=None,
    )

    assert status.kpis.requests == 4
    assert status.kpis.prompt_tokens == 52
    assert status.kpis.generated_tokens == 32
    assert status.kpis.total_tokens == 84
    assert status.kpis.avg_latency_ms == pytest.approx(500.0)
    assert status.kpis.avg_gen_toks_per_s == pytest.approx(16.0)
    assert status.providers_available == 3
    assert status.providers_online == 2
    assert len(status.series) == 4

    breakdowns = await admin_router_analytics_service.get_router_analytics_status_breakdowns(
        principal=principal,
        db=pool,
        range_value="1h",
        org_id=None,
        provider=None,
        model=None,
        token_id=None,
        granularity=None,
    )
    providers = {row.key: row.requests for row in breakdowns.providers}
    assert providers["groq"] == 2
    assert providers["openai"] == 1
    assert providers["anthropic"] == 1
    assert any(row.key == "unknown" and row.requests == 1 for row in breakdowns.remote_ips)
    assert any(row.key == "unknown" and row.requests == 1 for row in breakdowns.user_agents)
    assert any(row.key == "unknown" and row.requests == 1 for row in breakdowns.token_names)

    meta = await admin_router_analytics_service.get_router_analytics_meta(
        principal=principal,
        db=pool,
    )
    provider_values = {option.value for option in meta.providers}
    token_values = {option.value for option in meta.tokens}
    assert {"openai", "groq", "anthropic"} <= provider_values
    assert {"Admin", "Ops", "unknown"} <= token_values


@pytest.mark.asyncio
async def test_router_analytics_status_honors_provider_and_token_filters(monkeypatch, tmp_path):
    _setup_env(tmp_path)
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.session_manager import reset_session_manager
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    await reset_db_pool()
    reset_settings()
    await reset_session_manager()
    user_id = await _ensure_router_usage_seed_rows()
    pool = await get_db_pool()
    principal = _single_user_principal(user_id)

    monkeypatch.setattr(
        admin_router_analytics_service,
        "_utcnow",
        lambda: datetime(2026, 3, 1, 10, 30, tzinfo=timezone.utc),
    )

    by_provider = await admin_router_analytics_service.get_router_analytics_status(
        principal=principal,
        db=pool,
        range_value="1h",
        org_id=None,
        provider="groq",
        model=None,
        token_id=None,
        granularity=None,
    )
    assert by_provider.kpis.requests == 2
    assert by_provider.kpis.prompt_tokens == 35

    by_token = await admin_router_analytics_service.get_router_analytics_status(
        principal=principal,
        db=pool,
        range_value="1h",
        org_id=None,
        provider=None,
        model=None,
        token_id=11,
        granularity=None,
    )
    assert by_token.kpis.requests == 1
    assert by_token.kpis.total_tokens == 30
