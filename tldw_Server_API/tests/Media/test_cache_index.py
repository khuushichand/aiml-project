import pytest


class _FakeRedis:
    def __init__(self):
        self.calls = []
        self.kv = {}
        self.sets = {}

    # Basic KV
    def setex(self, key, ttl, value):
        self.calls.append(("setex", key, ttl, value))
        self.kv[key] = value

    def get(self, key):
        self.calls.append(("get", key))
        return self.kv.get(key)

    def delete(self, *keys):
        self.calls.append(("delete", keys))
        deleted = 0
        for k in keys:
            k = k.decode() if isinstance(k, (bytes, bytearray)) else k
            if k in self.kv:
                del self.kv[k]
                deleted += 1
        return deleted

    # Set ops
    def sadd(self, key, member):
        self.calls.append(("sadd", key, member))
        self.sets.setdefault(key, set()).add(member)

    def smembers(self, key):
        self.calls.append(("smembers", key))
        # Redis returns set of bytes in many clients; emulate strings for simplicity
        return set(self.sets.get(key, set()))

    def expire(self, key, ttl):
        self.calls.append(("expire", key, ttl))
        return True

    # Scan fallback
    def scan(self, cursor=0, match=None, count=None):
        self.calls.append(("scan", cursor, match, count))
        # Return no matches by default
        return 0, []


@pytest.mark.unit
def test_cache_index_added_and_invalidated(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import media as media_mod

    fake = _FakeRedis()
    monkeypatch.setattr(media_mod, "cache", fake)

    # Simulate caching a media details response
    key = "cache:/api/v1/media/123:abc123"
    media_mod.cache_response(key, {"ok": True})

    # Expect KV set and index set updates
    assert any(call[0] == "setex" and call[1] == key for call in fake.calls)
    idx_key = "cacheidx:/api/v1/media/123"
    assert idx_key in fake.sets
    assert key in fake.sets[idx_key]

    # Seed index with multiple items and ensure invalidate deletes them
    other_key = "cache:/api/v1/media/123:def456"
    fake.kv[other_key] = "v"
    fake.sets[idx_key].add(other_key)

    media_mod.invalidate_cache(123)

    # Both keys should be deleted
    assert key not in fake.kv
    assert other_key not in fake.kv
    # Index set should be removed (we don't strictly enforce, but delete is attempted)
    # We accept either emptied set or key removal; check delete call presence
    assert any(call[0] == "delete" and idx_key in [k.decode() if isinstance(k, (bytes, bytearray)) else k for k in call[1]] for call in fake.calls)


@pytest.mark.unit
def test_invalidate_uses_scan_when_index_missing(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import media as media_mod

    class _ScanOnlyRedis(_FakeRedis):
        def smembers(self, key):
            # Simulate missing index set
            return set()

        def scan(self, cursor=0, match=None, count=None):
            # Return one matching key via SCAN on first call, then finish
            if cursor == 0:
                # Create the key to be deleted in KV
                self.kv["cache:/api/v1/media/456:ghi789"] = "v"
                return 0, ["cache:/api/v1/media/456:ghi789"]
            return 0, []

    fake = _ScanOnlyRedis()
    monkeypatch.setattr(media_mod, "cache", fake)

    media_mod.invalidate_cache(456)

    # Expect fallback removal of scanned/deletable key even when index missing
    assert "cache:/api/v1/media/456:ghi789" not in fake.kv
