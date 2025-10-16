import asyncio
import json
import os
import types

import pytest

from tldw_Server_API.app.core.Embeddings.worker_orchestrator import WorkerOrchestrator
from tldw_Server_API.app.core.Embeddings.worker_config import OrchestrationConfig


class _FakeRedisDrainer:
    def __init__(self):
        self.z = {}
        self.streams = {}

    async def zrangebyscore(self, key, min, max, start=0, num=None):
        arr = self.z.get(key, [])
        # All are due; emulate Redis ordering by score then insertion
        out = arr[start: start + (num if num is not None else len(arr))]
        # Return the member strings
        return [m for (_score, m) in out]

    async def zrem(self, key, member):
        arr = self.z.get(key, [])
        keep = [(s, m) for (s, m) in arr if m != member]
        self.z[key] = keep
        return 1 if len(keep) != len(arr) else 0

    async def xadd(self, name, fields):
        arr = self.streams.setdefault(name, [])
        eid = f"{len(arr)+1}-0"
        arr.append((eid, dict(fields)))
        return eid


def _make_pool_stub(queue_name: str):
    return types.SimpleNamespace(config=types.SimpleNamespace(queue_name=queue_name))


@pytest.mark.unit
def test_token_bucket_throttles_requeue(monkeypatch):
    # Configure low rate and small burst so only a small number is drained per tick
    monkeypatch.setenv('EMBEDDINGS_REQUEUE_RATE', '0')
    monkeypatch.setenv('EMBEDDINGS_REQUEUE_BURST', '10')

    fake = _FakeRedisDrainer()
    q = 'embeddings:embedding'
    delayed = f'{q}:delayed'
    # Preload 50 due items
    now_ms = 1700000000000
    fake.z[delayed] = [(now_ms, json.dumps({"job_id": f"j-{i}"})) for i in range(50)]

    # Build orchestrator with stubbed pools and fake redis client
    cfg = OrchestrationConfig.default_config()
    orch = WorkerOrchestrator(cfg)
    orch.pools = {"embedding": _make_pool_stub(q)}
    orch.running = True
    orch.job_manager = types.SimpleNamespace(redis_client=fake)

    async def run_once():
        # Run drainer for a bit then stop
        t = asyncio.create_task(orch._drain_delayed_queues())
        # Allow one loop to run
        await asyncio.sleep(0.2)
        orch.running = False
        t.cancel()
        try:
            await t
        except BaseException:
            pass

    asyncio.run(run_once())

    # At most burst (10) items should have been moved
    moved = len(fake.streams.get(q, []))
    remaining = len(fake.z.get(delayed, []))
    assert moved <= 10
    assert remaining >= 40
