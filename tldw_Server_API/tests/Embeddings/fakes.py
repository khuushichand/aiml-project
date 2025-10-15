import json


class FakeAsyncRedisSummary:
    """Reusable async Redis fake for orchestrator summary/polling tests.

    Exposes:
    - xlen for queue and dlq depths
    - xrange to provide an oldest stream id (for queue age calculation)
    - scan/get to iterate worker metrics snapshots
    - close no-op
    """

    def __init__(self):
        # Live queue depths
        self._queues = {
            'embeddings:chunking': 1,
            'embeddings:embedding': 2,
            'embeddings:storage': 3,
        }
        # DLQ depths
        self._dlq = {
            'embeddings:chunking:dlq': 0,
            'embeddings:embedding:dlq': 1,
            'embeddings:storage:dlq': 0,
        }
        # Worker metrics snapshots (scanned via worker:metrics:*)
        self._metrics = [
            {"worker_type": "chunking", "jobs_processed": 10, "jobs_failed": 1},
            {"worker_type": "embedding", "jobs_processed": 20, "jobs_failed": 2},
            {"worker_type": "storage",  "jobs_processed": 30, "jobs_failed": 3},
        ]
        # Generic KV store for stage flags and other simple keys
        self._kv = {}
        # Queues for which XRANGE should return empty (to force age==0.0)
        self._xrange_empty = set()

    # Queue depth
    async def xlen(self, name):
        if name in self._queues:
            return self._queues[name]
        if name in self._dlq:
            return self._dlq[name]
        return 0

    # Oldest entry for age calculation (SSE uses XRANGE with '-', '+', count=1)
    async def xrange(self, name, min, max, count=None):
        # Optionally simulate empty streams for age==0.0
        if name in self._xrange_empty:
            return []
        # Return a fabricated oldest id with a fixed timestamp for determinism
        # 1700000000000 ms (~Nov 2023)
        return [("1700000000000-0", {})]

    # Scan worker metrics keys
    async def scan(self, cursor, match=None, count=None):
        keys = [f"worker:metrics:{i}" for i in range(len(self._metrics))]
        # Single page
        return (0, keys)

    # Return worker metrics JSON by index key
    async def get(self, key):
        try:
            # stage flags / arbitrary keys first
            if key in self._kv:
                return self._kv[key]
            idx = int(str(key).split(':')[-1])
            return json.dumps(self._metrics[idx])
        except Exception:
            # Unknown keys (e.g., stage flags) -> None
            return None

    async def close(self):
        return True

    # Extended helpers for stage flags
    async def set(self, key, value):
        self._kv[key] = value
        return True

    async def delete(self, key):
        if key in self._kv:
            del self._kv[key]
            return 1
        return 0

    # Configure XRANGE empty behavior per queue name
    async def configure_xrange_empty(self, name: str, empty: bool = True):
        if empty:
            self._xrange_empty.add(name)
        else:
            self._xrange_empty.discard(name)
