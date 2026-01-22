import pytest

from tldw_Server_API.app.core.Embeddings.multi_tier_cache import MultiTierCache


@pytest.mark.asyncio
async def test_multi_tier_cache_sync_calls_inside_running_loop(tmp_path):
    cache = MultiTierCache(
        config={
            "l1_size_mb": 1,
            "l2_dir": str(tmp_path),
            "l2_size_gb": 1,
            "redis_port": 0,
        }
    )

    assert cache.set("alpha", {"v": 1}) is True
    assert cache.get("alpha") == {"v": 1}


def test_multi_tier_cache_ttl_zero_disables_storage(tmp_path):
    cache = MultiTierCache(
        config={
            "l1_size_mb": 1,
            "l2_dir": str(tmp_path),
            "l2_size_gb": 1,
            "redis_port": 0,
        }
    )

    assert cache.set("alpha", {"v": 1}, ttl=0) is False
    assert cache.get("alpha") is None
