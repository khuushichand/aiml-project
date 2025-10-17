import asyncio
import json
import time

import pytest

from tldw_Server_API.app.core.Embeddings.worker_orchestrator import WorkerOrchestrator
from tldw_Server_API.app.core.Embeddings.worker_config import OrchestrationConfig


class _FakeRedisDrainer:
    def __init__(self):
        self._zsets = {}  # key -> list[(score, raw)]
        self._streams = {}  # key -> list[(id, fields)]

    async def zrangebyscore(self, key, min='-inf', max='+inf', start=0, num=None):
        items = sorted(self._zsets.get(key, []), key=lambda x: x[0])
        lo = float('-inf') if min == '-inf' else float(min)
        hi = float('inf') if max == '+inf' else float(max)
        due = [raw for (score, raw) in items if lo <= float(score) <= hi]
        slice_ = due[start:(start + num) if num is not None else None]
        return slice_

    async def zrem(self, key, raw):
        items = self._zsets.get(key, [])
        new_items = [(s, r) for (s, r) in items if r != raw]
        self._zsets[key] = new_items
        return 1 if len(new_items) != len(items) else 0

    async def xadd(self, name, fields):
        lst = self._streams.setdefault(name, [])
        eid = f"{len(lst)+1}-0"
        f = {}
        for k, v in (fields or {}).items():
            f[str(k)] = v if isinstance(v, str) else json.dumps(v)
        lst.append((eid, f))
        return eid

    # Helpers for test setup
    def seed_delayed(self, key, payloads):
        now_ms = int(time.time() * 1000)
        items = []
        for i, pl in enumerate(payloads):
            raw = json.dumps(pl)
            items.append((now_ms - 1000 - i * 10, raw))  # due in the past
        self._zsets[key] = items


class _JMStub:
    def __init__(self, client):
        self.redis_client = client


class _PoolCfgStub:
    def __init__(self, queue_name):
        self.queue_name = queue_name


@pytest.mark.unit
def test_drainer_moves_due_items_to_live_queue(monkeypatch):
    orch = WorkerOrchestrator(OrchestrationConfig.default_config())
    fake = _FakeRedisDrainer()
    # Provide a job manager stub with our fake redis
    orch.job_manager = _JMStub(fake)
    # Provide minimal pool configs so drainer discovers queues
    class _PoolStub:
        def __init__(self, q):
            self.config = _PoolCfgStub(q)
    orch.pools = {
        'embedding': _PoolStub('embeddings:embedding')
    }
    # Seed two due items
    delayed_key = 'embeddings:embedding:delayed'
    fake.seed_delayed(delayed_key, [
        {"job_id": "j1", "payload": {"x": 1}},
        {"job_id": "j2", "payload": {"x": 2}},
    ])
    # Speed up token bucket
    orch._requeue_rate = 1000.0
    orch._requeue_burst = 1000.0

    async def _run_once():
        orch.running = True
        # Start drainer and let it run briefly
        task = asyncio.create_task(orch._drain_delayed_queues())
        await asyncio.sleep(0.05)
        orch.running = False
        await asyncio.sleep(0.05)
        try:
            task.cancel()
        except Exception:
            pass

    asyncio.run(_run_once())

    # Verify items were moved to live stream and removed from zset
    live_items = fake._streams.get('embeddings:embedding', [])
    assert len(live_items) >= 2
    assert delayed_key not in fake._zsets or len(fake._zsets.get(delayed_key, [])) == 0
