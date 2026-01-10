import pytest

pytestmark = pytest.mark.rate_limit

from tldw_Server_API.app.core.Resource_Governance import RedisResourceGovernor, RGRequest
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


@pytest.mark.asyncio
async def test_concurrency_gauge_updates_on_reserve_and_release():
    class _Loader:
        def get_policy(self, pid):
                     return {"streams": {"max_concurrent": 2, "ttl_sec": 60}, "scopes": ["global", "user"]}

    rg = RedisResourceGovernor(policy_loader=_Loader(), ns="rg_gauge")
    reg = get_metrics_registry()
    e = "user:g1"
    policy_id = "p"

    # Reserve one stream (should set gauge to 1 for both global and user scopes)
    d1, h1 = await rg.reserve(RGRequest(entity=e, categories={"streams": {"units": 1}}, tags={"policy_id": policy_id}))
    assert d1.allowed and h1

    st_user = reg.get_metric_stats("rg_concurrency_active", labels={"category": "streams", "scope": "user", "policy_id": policy_id})
    st_global = reg.get_metric_stats("rg_concurrency_active", labels={"category": "streams", "scope": "global", "policy_id": policy_id})
    assert st_user and st_user["latest"] >= 1
    assert st_global and st_global["latest"] >= 1

    # Release and gauge should drop to 0
    await rg.release(h1)
    st_user2 = reg.get_metric_stats("rg_concurrency_active", labels={"category": "streams", "scope": "user", "policy_id": policy_id})
    st_global2 = reg.get_metric_stats("rg_concurrency_active", labels={"category": "streams", "scope": "global", "policy_id": policy_id})
    assert st_user2 and st_user2["latest"] == 0
    assert st_global2 and st_global2["latest"] == 0
