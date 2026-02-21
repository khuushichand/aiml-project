import pytest

from tldw_Server_API.app.core.Resource_Governance import MemoryResourceGovernor, RGRequest
from tldw_Server_API.app.core.Resource_Governance.policy_loader import (
    PolicyLoader,
    PolicyReloadConfig,
)
from tldw_Server_API.app.core.Usage.usage_tracker import log_llm_usage


pytestmark = pytest.mark.rate_limit


async def _init_authnz_sqlite(db_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    # Ensure usage logging is on; some suites toggle this off globally and
    # the tokens/day ledger tests require log_llm_usage to write entries.
    monkeypatch.setenv("LLM_USAGE_ENABLED", "1")
    try:
        from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
        from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
        await reset_db_pool()
        reset_settings()
    except Exception:
        _ = None
    try:
        from tldw_Server_API.app.core.AuthNZ.initialize import ensure_authnz_schema_ready_once
        await ensure_authnz_schema_ready_once()
    except Exception:
        _ = None
    # Reset cached daily-ledger singleton so daily-cap checks consult this DB.
    try:
        import tldw_Server_API.app.core.Resource_Governance.daily_caps as _dc

        _dc._daily_ledger = None  # type: ignore[attr-defined]
    except Exception:
        _ = None
    # Reset cached ledger inside usage_tracker between tests.
    try:
        import tldw_Server_API.app.core.Usage.usage_tracker as _ut
        _ut._tokens_daily_ledger = None  # type: ignore[attr-defined]
        _ut._tokens_legacy_backfill_done = set()  # type: ignore[attr-defined]
    except Exception:
        _ = None


@pytest.mark.asyncio
async def test_tokens_daily_cap_denies_when_exceeded(tmp_path, monkeypatch):
    db_path = tmp_path / "authnz_tokens.db"
    await _init_authnz_sqlite(db_path, monkeypatch)

    policy_yaml = tmp_path / "rg_tokens_daily.yaml"
    policy_yaml.write_text(
        """
schema_version: 1
policies:
  chat.test:
    requests: { rpm: 100000, burst: 1.0 }
    tokens:   { per_min: 1000000, burst: 1.0, daily_cap: 10 }
    scopes: [user]
route_map: {}
""".lstrip()
    )

    loader = PolicyLoader(str(policy_yaml), PolicyReloadConfig(enabled=False, interval_sec=0))
    await loader.load_once()
    gov = MemoryResourceGovernor(policy_loader=loader)

    # Record 9 tokens used so far for user 1.
    await log_llm_usage(
        user_id=1,
        key_id=None,
        endpoint="POST:/api/v1/chat/completions",
        operation="chat",
        provider="test",
        model="test-model",
        status=200,
        latency_ms=1,
        prompt_tokens=9,
        completion_tokens=0,
        total_tokens=9,
        request_id="rid-1",
        estimated=False,
    )

    # Requesting 2 more tokens should exceed daily cap 10.
    req = RGRequest(
        entity="user:1",
        categories={"tokens": {"units": 2}},
        tags={"policy_id": "chat.test"},
    )
    dec, _ = await gov.reserve(req, op_id="op1")
    assert dec.allowed is False
    assert dec.retry_after is not None

    # A smaller request within remaining headroom should be allowed.
    req_ok = RGRequest(
        entity="user:1",
        categories={"tokens": {"units": 1}},
        tags={"policy_id": "chat.test"},
    )
    dec2, _ = await gov.reserve(req_ok, op_id="op2")
    assert dec2.allowed is True


@pytest.mark.asyncio
async def test_log_llm_usage_writes_tokens_to_ledger_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "authnz_tokens_idem.db"
    await _init_authnz_sqlite(db_path, monkeypatch)

    from tldw_Server_API.app.core.DB_Management.Resource_Daily_Ledger import ResourceDailyLedger

    ledger = ResourceDailyLedger()
    await ledger.initialize()

    before = await ledger.total_for_day("user", "1", "tokens")

    await log_llm_usage(
        user_id=1,
        key_id=None,
        endpoint="POST:/api/v1/chat/completions",
        operation="chat",
        provider="test",
        model="test-model",
        status=200,
        latency_ms=1,
        prompt_tokens=5,
        completion_tokens=0,
        total_tokens=5,
        request_id="rid-dup",
        estimated=False,
    )
    # Repeat identical usage log should not double-count ledger.
    await log_llm_usage(
        user_id=1,
        key_id=None,
        endpoint="POST:/api/v1/chat/completions",
        operation="chat",
        provider="test",
        model="test-model",
        status=200,
        latency_ms=1,
        prompt_tokens=5,
        completion_tokens=0,
        total_tokens=5,
        request_id="rid-dup",
        estimated=False,
    )

    after = await ledger.total_for_day("user", "1", "tokens")
    assert after == before + 5


@pytest.mark.asyncio
async def test_backfill_legacy_tokens_to_ledger_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "authnz_tokens_backfill.db"
    await _init_authnz_sqlite(db_path, monkeypatch)

    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    from tldw_Server_API.app.core.AuthNZ.repos.usage_repo import AuthnzUsageRepo
    from tldw_Server_API.app.core.DB_Management.Resource_Daily_Ledger import ResourceDailyLedger
    from tldw_Server_API.app.core.Usage.usage_tracker import backfill_legacy_tokens_to_ledger

    pool = await get_db_pool()
    repo = AuthnzUsageRepo(pool)
    await repo.insert_llm_usage_log(
        user_id=1,
        key_id=None,
        endpoint="POST:/api/v1/chat/completions",
        operation="chat",
        provider="test",
        model="test-model",
        status=200,
        latency_ms=1,
        prompt_tokens=7,
        completion_tokens=0,
        total_tokens=7,
        prompt_cost_usd=0.0,
        completion_cost_usd=0.0,
        total_cost_usd=0.0,
        currency="USD",
        estimated=False,
        request_id="rid-legacy",
    )

    ledger = ResourceDailyLedger()
    await ledger.initialize()
    assert await ledger.total_for_day("user", "1", "tokens") == 0

    await backfill_legacy_tokens_to_ledger(entity_scope="user", entity_value="1")
    assert await ledger.total_for_day("user", "1", "tokens") == 7

    # Second backfill is a no-op (per process/entity/day).
    await backfill_legacy_tokens_to_ledger(entity_scope="user", entity_value="1")
    assert await ledger.total_for_day("user", "1", "tokens") == 7
