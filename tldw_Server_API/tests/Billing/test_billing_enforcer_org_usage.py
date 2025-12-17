from __future__ import annotations

import asyncio
from typing import Any, List, Tuple

import pytest

from tldw_Server_API.app.core.Billing.enforcement import BillingEnforcer


class _FakeConnPg:
    def __init__(self, result: int):
        self.result = result
        self.calls: List[Tuple[str, Tuple[Any, ...]]] = []

    async def fetchval(self, sql: str, *args: Any) -> int:
        # Record SQL for inspection in tests
        self.calls.append((sql, args))
        return int(self.result)


class _AcquireCtx:
    def __init__(self, conn: Any):
        self._conn = conn

    async def __aenter__(self) -> Any:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakePoolPg:
    def __init__(self, conn: _FakeConnPg):
        self._conn = conn

    def acquire(self) -> _AcquireCtx:
        return _AcquireCtx(self._conn)


@pytest.mark.asyncio
async def test_get_llm_tokens_month_aggregates_via_org_members_and_api_keys(monkeypatch):
    """_get_llm_tokens_month should query llm_usage_log joined with org_members and api_keys."""

    fake_conn = _FakeConnPg(result=1234)
    fake_pool = _FakePoolPg(fake_conn)

    async def _fake_get_db_pool():
        return fake_pool

    # Patch the AuthNZ DB pool getter so BillingEnforcer uses our fake pool.
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.database.get_db_pool",
        _fake_get_db_pool,
        raising=False,
    )

    enforcer = BillingEnforcer()
    tokens = await enforcer._get_llm_tokens_month(org_id=42)

    assert tokens == 1234
    assert fake_conn.calls, "Expected _get_llm_tokens_month to call fetchval"
    sql, args = fake_conn.calls[-1]
    flat_sql = " ".join(sql.split())
    # Ensure the query aggregates via org_members and api_keys joins
    assert "FROM llm_usage_log AS l JOIN org_members AS om ON l.user_id = om.user_id" in flat_sql
    assert "UNION ALL SELECT l2.total_tokens FROM llm_usage_log AS l2 JOIN api_keys AS ak ON l2.key_id = ak.id" in flat_sql
    # Org id and month_start should be passed as parameters
    assert args[0] == 42


class _FakeOrgRepo:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def list_org_members(self, org_id: int, limit: int = 1000, offset: int = 0, role=None, status=None):
        assert org_id == 7
        return [{"user_id": 1}, {"user_id": 2}, {"user_id": None}]


class _FakeEmbeddingsJobsDB:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def get_or_create_user_quota(self, user_id: str):
        # Map user_id to different active counts to verify summing
        if user_id == "1":
            return {"concurrent_jobs_active": 2}
        if user_id == "2":
            return {"concurrent_jobs_active": 3}
        return {"concurrent_jobs_active": 0}


@pytest.mark.asyncio
async def test_get_concurrent_jobs_sums_embedding_jobs_for_org(monkeypatch):
    """_get_concurrent_jobs should best-effort sum concurrent embedding jobs across org members."""

    async def _fake_get_db_pool():
        return object()

    # Patch lower-level dependencies used by _get_concurrent_jobs.
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.database.get_db_pool",
        _fake_get_db_pool,
        raising=False,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo.AuthnzOrgsTeamsRepo",
        _FakeOrgRepo,
        raising=False,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.DB_Management.Embeddings_Jobs_DB.EmbeddingsJobsDatabase",
        _FakeEmbeddingsJobsDB,
        raising=False,
    )

    enforcer = BillingEnforcer()
    total = await enforcer._get_concurrent_jobs(org_id=7)

    # 2 (user 1) + 3 (user 2) = 5 concurrent jobs
    assert total == 5

