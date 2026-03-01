from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _setup_env(tmp_path) -> None:
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = "unit-test-router-analytics-endpoints"
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'users_test_router_analytics_endpoints.db'}"


async def _seed_router_rows() -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool

    pool = await get_db_pool()
    await pool.execute(
        "INSERT OR IGNORE INTO users (uuid, username, email, password_hash, is_active) VALUES (?,?,?,?,1)",
        str(uuid.uuid4()),
        "router_endpoints_user",
        "router_endpoints_user@example.com",
        "x",
    )
    user_id = int(await pool.fetchval("SELECT id FROM users WHERE username = ?", "router_endpoints_user"))

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
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key_hash TEXT,
            key_prefix TEXT,
            name TEXT,
            status TEXT DEFAULT 'active'
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

    key_cols = {row["name"] for row in await pool.fetchall("PRAGMA table_info(api_keys)")}
    if "llm_budget_day_tokens" not in key_cols:
        await pool.execute("ALTER TABLE api_keys ADD COLUMN llm_budget_day_tokens INTEGER")
    if "llm_budget_month_tokens" not in key_cols:
        await pool.execute("ALTER TABLE api_keys ADD COLUMN llm_budget_month_tokens INTEGER")
    if "llm_budget_day_usd" not in key_cols:
        await pool.execute("ALTER TABLE api_keys ADD COLUMN llm_budget_day_usd REAL")
    if "llm_budget_month_usd" not in key_cols:
        await pool.execute("ALTER TABLE api_keys ADD COLUMN llm_budget_month_usd REAL")

    await pool.execute(
        """
        INSERT OR REPLACE INTO api_keys (
            id, user_id, key_hash, name, status,
            llm_budget_day_tokens, llm_budget_month_tokens, llm_budget_day_usd, llm_budget_month_usd
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        201,
        user_id,
        "hash-201",
        "Admin",
        "active",
        500,
        5000,
        5.0,
        50.0,
    )
    await pool.execute(
        """
        INSERT OR REPLACE INTO api_keys (
            id, user_id, key_hash, name, status,
            llm_budget_day_tokens, llm_budget_month_tokens, llm_budget_day_usd, llm_budget_month_usd
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        202,
        user_id,
        "hash-202",
        "Ops",
        "active",
        10,
        100,
        0.01,
        1.0,
    )

    await pool.execute(
        """
        INSERT INTO llm_usage_log (
            user_id, key_id, endpoint, operation, provider, model, status, latency_ms,
            prompt_tokens, completion_tokens, total_tokens, prompt_cost_usd, completion_cost_usd, total_cost_usd,
            currency, estimated, request_id, remote_ip, user_agent, token_name, conversation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        user_id,
        201,
        "/api/v1/chat/completions",
        "chat",
        "openai",
        "gpt-4o-mini",
        200,
        600,
        100,
        40,
        140,
        0.0,
        0.0,
        0.0,
        "USD",
        0,
        "router-endpoint-1",
        "127.0.0.1",
        "curl/8.8.0",
        "Admin",
        "conv-1",
    )
    await pool.execute(
        """
        INSERT INTO llm_usage_log (
            user_id, key_id, endpoint, operation, provider, model, status, latency_ms,
            prompt_tokens, completion_tokens, total_tokens, prompt_cost_usd, completion_cost_usd, total_cost_usd,
            currency, estimated, request_id, remote_ip, user_agent, token_name, conversation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        user_id,
        202,
        "/api/v1/chat/completions",
        "chat",
        "groq",
        "llama-3.3-70b",
        500,
        300,
        20,
        0,
        20,
        0.0,
        0.0,
        0.0,
        "USD",
        1,
        "router-endpoint-2",
        None,
        None,
        None,
        "conv-2",
    )


@pytest.mark.asyncio
async def test_router_analytics_endpoints_status_breakdowns_meta(monkeypatch, tmp_path):
    _setup_env(tmp_path)

    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.session_manager import reset_session_manager
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    await reset_db_pool()
    reset_settings()
    await reset_session_manager()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        await _seed_router_rows()

        status_resp = client.get("/api/v1/admin/router-analytics/status", params={"range": "1h"})
        assert status_resp.status_code == 200, status_resp.text
        status_payload = status_resp.json()
        assert status_payload["kpis"]["requests"] == 2
        assert status_payload["providers_available"] == 2
        assert status_payload["providers_online"] == 1
        assert "data_window" in status_payload

        breakdowns_resp = client.get(
            "/api/v1/admin/router-analytics/status/breakdowns",
            params={"range": "1h"},
        )
        assert breakdowns_resp.status_code == 200, breakdowns_resp.text
        breakdowns_payload = breakdowns_resp.json()
        assert isinstance(breakdowns_payload["providers"], list)
        assert any(row["key"] == "openai" for row in breakdowns_payload["providers"])
        assert any(row["key"] == "unknown" for row in breakdowns_payload["remote_ips"])

        meta_resp = client.get("/api/v1/admin/router-analytics/meta")
        assert meta_resp.status_code == 200, meta_resp.text
        meta_payload = meta_resp.json()
        assert any(option["value"] == "openai" for option in meta_payload["providers"])

        quota_resp = client.get("/api/v1/admin/router-analytics/quota", params={"range": "1h"})
        assert quota_resp.status_code == 200, quota_resp.text
        quota_payload = quota_resp.json()
        assert quota_payload["summary"]["keys_total"] >= 1
        assert "items" in quota_payload
        keyed = {int(row["key_id"]): row for row in quota_payload["items"]}
        assert 202 in keyed
