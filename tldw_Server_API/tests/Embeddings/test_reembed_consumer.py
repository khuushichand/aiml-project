import asyncio
import pytest

from tldw_Server_API.app.core.Embeddings.services.reembed_consumer import process_once, REQUEST_STREAM, SCHEDULED_STREAM


class _FakeRedis:
    def __init__(self):
        self.streams = {REQUEST_STREAM: [], SCHEDULED_STREAM: []}

    async def xrange(self, name, min, max, count=None):
        items = self.streams.get(name, [])
        out = items[: (count or len(items))]
        return out

    async def xadd(self, name, fields):
        eid = f"{len(self.streams.setdefault(name, []))+1}-0"
        self.streams[name].append((eid, dict(fields)))
        return eid

    async def xdel(self, name, *ids):
        items = self.streams.get(name, [])
        keep = [(i, f) for (i, f) in items if i not in ids]
        self.streams[name] = keep
        return len(items) - len(keep)


@pytest.mark.unit
def test_reembed_consumer_schedules_and_deletes():
    fake = _FakeRedis()
    # Seed two request entries
    fake.streams[REQUEST_STREAM] = [
        ("1-0", {"user_id": "u", "collection": "c1", "current_embedder_name":"hf","current_embedder_version":"m1","new_embedder_name":"hf","new_embedder_version":"m2"}),
        ("2-0", {"user_id": "u", "collection": "c2", "current_embedder_name":"hf","current_embedder_version":"m1","new_embedder_name":"hf","new_embedder_version":"m3"}),
    ]

    processed = asyncio.run(process_once(fake, max_items=10))
    assert processed == 2
    # Requests removed
    assert len(fake.streams[REQUEST_STREAM]) == 0
    # Scheduled added with scheduled_at
    sched = fake.streams[SCHEDULED_STREAM]
    assert len(sched) == 2
    assert "scheduled_at" in sched[0][1]
