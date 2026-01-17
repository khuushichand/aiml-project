from __future__ import annotations

import time

import pytest

from tldw_Server_API.app.core.Infrastructure import redis_factory as rf


def test_sync_stub_core_commands():
    client = rf.InMemorySyncRedis()

    client.set("k1", "v1")
    assert client.get("k1") == "v1"

    client.setex("k2", 5, "v2")
    ttl = client.ttl("k2")
    assert ttl >= 0

    assert client.sadd("set:1", "a") == 1
    assert client.sadd("set:1", "a") == 0
    assert client.smembers("set:1") == {"a"}
    assert client.srem("set:1", "a") == 1

    client.zadd("z:1", {"alpha": 1.0, "beta": 2.0})
    assert client.zrange("z:1", 0, -1) == ["alpha", "beta"]
    assert client.zscore("z:1", "alpha") == 1.0
    assert client.zincrby("z:1", 2.5, "alpha") == 3.5

    assert client.hset("h:1", {"field": "1"}) == 1
    assert client.hget("h:1", "field") == "1"
    assert client.hincrby("h:1", "field", 2) == 3
    assert client.hgetall("h:1")["field"] == "3"

    cursor, keys = client.scan(0, match="k*", count=10)
    assert cursor == 0
    assert "k1" in keys
    assert set(client.keys("k*")) >= {"k1", "k2"}

    info = client.info("memory")
    assert "used_memory" in info
    assert client.dbsize() >= 4

    assert client.delete("k1", "k2") == 2


@pytest.mark.asyncio
async def test_async_stub_streams_and_scripts():
    client = rf.InMemoryAsyncRedis()

    await client.xadd("stream:1", {"field": "a"})
    await client.xadd("stream:1", {"field": "b"})
    assert await client.xlen("stream:1") == 2

    await client.xgroup_create("stream:1", "group:1")
    first_batch = await client.xreadgroup(
        "group:1",
        "consumer:1",
        {"stream:1": ">"},
        count=1,
    )
    assert first_batch
    assert first_batch[0][0] == "stream:1"
    assert len(first_batch[0][1]) == 1

    second_batch = await client.xreadgroup(
        "group:1",
        "consumer:1",
        {"stream:1": ">"},
        count=1,
    )
    assert second_batch
    assert len(second_batch[0][1]) == 1

    script = "redis.call('ZRANGE', KEYS[1], 0, -1); redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, 0)"
    sha = await client.script_load(script)
    result = await client.evalsha(sha, 1, "rate:key", 1, 60, 1000.0)
    assert result == [1, 0]

    eval_result = await client.eval(script, 1, "rate:key", 1, 60, time.time())
    assert isinstance(eval_result, list)
