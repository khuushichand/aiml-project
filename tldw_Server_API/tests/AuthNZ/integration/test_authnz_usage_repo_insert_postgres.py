from __future__ import annotations

import pytest


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_authnz_usage_repo_insert_usage_log_postgres(test_db_pool):
    """AuthnzUsageRepo.insert_usage_log should insert rows on Postgres with bytes_in."""
    from tldw_Server_API.app.core.AuthNZ.repos.usage_repo import AuthnzUsageRepo

    pool = test_db_pool
    repo = AuthnzUsageRepo(pool)

    await repo.insert_usage_log(
        user_id=1,
        key_id=2,
        endpoint="POST:/usage-test",
        status=201,
        latency_ms=75,
        bytes_out=2048,
        bytes_in=1024,
        meta='{"ip": "10.0.0.1"}',
        request_id="req-postgres-insert",
    )

    row = await pool.fetchone(
        """
        SELECT user_id, key_id, endpoint, status, latency_ms,
               bytes, bytes_in, meta, request_id
        FROM usage_log
        WHERE request_id = $1
        """,
        "req-postgres-insert",
    )

    assert row is not None
    row = dict(row)
    assert int(row["user_id"]) == 1
    assert int(row["key_id"]) == 2
    assert row["endpoint"] == "POST:/usage-test"
    assert int(row["status"]) == 201
    assert int(row["latency_ms"]) == 75
    assert int(row["bytes"]) == 2048
    assert int(row["bytes_in"]) == 1024
    assert '"ip": "10.0.0.1"' in (row.get("meta") or "")
    assert row["request_id"] == "req-postgres-insert"

