from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.monitoring_repo import AuthnzMonitoringRepo


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_authnz_monitoring_repo_postgres_basic(
    isolated_test_environment: tuple[TestClient, str],
) -> None:
    """AuthnzMonitoringRepo should aggregate metrics on Postgres."""
    client, db_name = isolated_test_environment
    assert client is not None
    assert db_name

    pool = await get_db_pool()
    repo = AuthnzMonitoringRepo(pool)

    now = datetime.now(timezone.utc)

    # Seed a few metric audit rows via the repo.
    await repo.insert_metric_audit_log(
        action="metric_auth_success",
        details_json="{}",
        created_at=now - timedelta(minutes=10),
    )
    await repo.insert_metric_audit_log(
        action="metric_auth_failure",
        details_json="{}",
        created_at=now - timedelta(minutes=5),
    )
    await repo.insert_metric_audit_log(
        action="metric_rate_limit_hit",
        details_json="{}",
        created_at=now - timedelta(minutes=2),
    )

    cutoff = now - timedelta(minutes=30)
    summary = await repo.get_metrics_window_summary(cutoff)
    assert summary["successful_auths"] >= 1
    assert summary["failed_auths"] >= 1
    assert summary["rate_limit_hits"] >= 1

    # Seed sessions and api_keys for count helpers.
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (username, email, password_hash, role, is_active, is_verified)
            VALUES ($1, $2, $3, $4, TRUE, TRUE)
            """,
            "monitor-user",
            "monitor@example.com",
            "hashed",
            "admin",
        )
        user_id = await conn.fetchval(
            "SELECT id FROM users WHERE username = $1",
            "monitor-user",
        )
        assert user_id is not None

        await conn.execute(
            """
            INSERT INTO sessions (user_id, token_hash, expires_at, is_revoked)
            VALUES ($1, $2, $3, FALSE)
            """,
            int(user_id),
            "session-hash",
            now + timedelta(hours=1),
        )
        await conn.execute(
            """
            INSERT INTO api_keys (user_id, key_hash, key_prefix, status)
            VALUES ($1, $2, $3, 'active')
            """,
            int(user_id),
            "key-hash",
            "prefix",
        )

    active_sessions = await repo.get_active_sessions_count(now)
    active_keys = await repo.get_active_api_keys_count()
    assert active_sessions >= 1
    assert active_keys >= 1

    # Security alerts round-trip through audit_logs.
    await repo.insert_metric_audit_log(
        action="metric_security_alert",
        details_json='{"labels":{"alert_type":"test_pg","severity":"high"}}',
        created_at=now,
    )
    alerts = await repo.get_recent_security_alerts(limit=5)
    assert alerts
    assert alerts[0]["action"] == "metric_security_alert"
