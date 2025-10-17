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
        # Simple in-memory streams storage: name -> list[(id, fields)]
        self._streams = {}
        # Hash maps for DLQ state etc.
        self._hashes = {}

    # Queue depth
    async def xlen(self, name):
        # Prefer in-memory stream length if present
        if name in self._streams:
            return len(self._streams.get(name, []))
        if name in self._queues:
            return self._queues[name]
        if name in self._dlq:
            return self._dlq[name]
        return 0

    # Oldest entry for age calculation (SSE uses XRANGE with '-', '+', count=1)
    async def xrange(self, name, min, max, count=None):
        # Prefer actual stored stream entries
        if name in self._streams:
            data = self._streams.get(name, [])
            if not data:
                return []
            # Return earliest entries by insertion order
            if count is None or count <= 0:
                return data[:]
            return data[:count]
        # Optionally simulate empty streams for age==0.0
        if name in self._xrange_empty:
            return []
        # Return a fabricated oldest id with a fixed timestamp for determinism
        # 1700000000000 ms (~Nov 2023)
        return [("1700000000000-0", {})]

    async def xrevrange(self, name, max="+", min="-", count=None):  # noqa: A002
        # Return most-recent-first entries from in-memory stream
        data = list(self._streams.get(name, []))
        data.reverse()
        if count is not None and count > 0:
            data = data[:count]
        return data

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

    async def hgetall(self, key):
        return dict(self._hashes.get(key, {}))

    async def hset(self, key, mapping=None, **kwargs):
        m = dict(mapping or {})
        m.update(kwargs)
        cur = self._hashes.setdefault(key, {})
        cur.update(m)
        return 1

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

    async def ttl(self, key):
        # Return a fixed TTL for testing purposes when key exists
        if key in self._kv:
            return 3600
        return -2  # key does not exist

    # Stream write (minimal XADD)
    async def xadd(self, name, fields):
        lst = self._streams.setdefault(name, [])
        # Deterministic id: use len-based counter (not ms) to avoid time deps
        eid = f"{len(lst)+1}-0"
        # Ensure dict[str, str]
        f = {}
        for k, v in (fields or {}).items():
            try:
                f[str(k)] = v if isinstance(v, str) else json.dumps(v)
            except Exception:
                f[str(k)] = str(v)
        lst.append((eid, f))
        # Update default queue depth accounting
        self._queues[name] = len(lst)
        return eid
