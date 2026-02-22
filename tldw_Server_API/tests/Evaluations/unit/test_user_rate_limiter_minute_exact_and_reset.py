import asyncio
import warnings

import pytest

from tldw_Server_API.app.core.Evaluations.user_rate_limiter import (
    UserRateLimiter,
    UserTier,
    _EVALS_DEPRECATION_WARNED,
)
from tldw_Server_API.app.core.Evaluations import user_rate_limiter as evals_rl


@pytest.mark.unit
def test_custom_tier_enforces_cost_only(tmp_path, monkeypatch):
    """Phase 2: CUSTOM tier skips minute/daily checks; only cost caps enforced."""
    db_path = tmp_path / "evals_rate_limit.db"
    limiter = UserRateLimiter(db_path=str(db_path))
    monkeypatch.setattr(evals_rl, "_EVALS_DEPRECATION_WARNED", False)

    user_id = "u-eval"
    endpoint = "/api/evals/run"

    async def _upgrade():
        await limiter.upgrade_user_tier(
            user_id=user_id,
            new_tier=UserTier.CUSTOM,
            custom_limits={
                "evaluations_per_minute": 1,
                "batch_evaluations_per_minute": 1,
                "evaluations_per_day": 100,
                "total_tokens_per_day": 100000,
                "burst_size": 0,
                "max_cost_per_day": 10.0,
                "max_cost_per_month": 100.0,
            },
        )

    asyncio.run(_upgrade())

    async def _check():
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Multiple requests should all be allowed (no minute/daily checks)
            for _ in range(5):
                ok, meta = await limiter.check_rate_limit(
                    user_id=user_id,
                    endpoint=endpoint,
                    is_batch=False,
                    tokens_requested=0,
                    estimated_cost=0.0,
                )
                assert ok is True
                assert meta.get("rate_limit_source") == "legacy_cost_only"
                assert meta.get("tier") == "custom"

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "Phase 2" in str(deprecation_warnings[0].message)

    asyncio.run(_check())
