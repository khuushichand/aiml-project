import json
from collections import defaultdict
from datetime import datetime, timedelta
import types

import pytest

from tldw_Server_API.app.core.AuthNZ.session_manager import SessionManager
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings


class FakeRedis:
    def __init__(self):
        self.kv: dict[str, str] = {}
        self.sets: defaultdict[str, set[int]] = defaultdict(set)

    async def setex(self, key, ttl, value):
        self.kv[key] = value

    async def sadd(self, key, value):
        self.sets[key].add(value)

    async def expire(self, key, ttl):
        # TTL tracking not required for test assertions
        return True

    async def get(self, key):
        return self.kv.get(key)

    async def delete(self, key):
        self.kv.pop(key, None)

    async def scan_iter(self, pattern):
        if pattern != "session:*":
            return
        # Iterate over a snapshot to allow mutation during iteration
        for key in list(self.kv.keys()):
            if key.startswith("session:"):
                yield key


class StubTransaction:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class StubPool:
    def __init__(self, conn):
        self.conn = conn

    def transaction(self):
        return StubTransaction(self.conn)


class StubConn:
    def __init__(self, expected_hash, session_id, user_id):
        self.expected_hash = expected_hash
        self.session_id = session_id
        self.user_id = user_id
        self.updated = False

    async def fetchrow(self, query, refresh_hash):
        assert refresh_hash == self.expected_hash
        return {"id": self.session_id, "user_id": self.user_id}

    async def execute(self, *args, **kwargs):
        self.updated = True
        return None


@pytest.mark.asyncio
async def test_refresh_session_replaces_cached_access_token(monkeypatch):
    reset_settings()
    manager = SessionManager()
    manager._initialized = True

    # Simplify hashing/encryption for deterministic testing
    manager.hash_token = types.MethodType(lambda self, token: f"h:{token}", manager)
    manager.encrypt_token = types.MethodType(
        lambda self, token: f"enc:{token}" if token else None, manager
    )

    def _extract_stub(self, token):
        if not token:
            return (None, None)
        return (f"jti:{token}", datetime.utcnow() + timedelta(minutes=30))

    manager._extract_token_metadata = types.MethodType(_extract_stub, manager)

    fake_redis = FakeRedis()
    manager.redis_client = fake_redis

    old_refresh = "old-refresh-token"
    old_refresh_hash = manager.hash_token(old_refresh)
    session_id = 555
    user_id = 42

    # Seed redis cache with previous access token entry
    old_access_hash = manager.hash_token("old-access-token")
    fake_redis.kv[f"session:{old_access_hash}"] = json.dumps(
        {
            "session_id": session_id,
            "user_id": user_id,
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "user_active": True,
            "revoked": False,
        }
    )

    stub_conn = StubConn(old_refresh_hash, session_id, user_id)
    stub_pool = StubPool(stub_conn)

    async def _ensure_db_pool_stub(self):
        return stub_pool

    manager.db_pool = stub_pool
    manager._ensure_db_pool = types.MethodType(_ensure_db_pool_stub, manager)

    new_access = "new-access-token"
    new_refresh = "new-refresh-token"

    result = await manager.refresh_session(
        refresh_token=old_refresh,
        new_access_token=new_access,
        new_refresh_token=new_refresh,
    )

    assert result["session_id"] == session_id
    new_access_hash = manager.hash_token(new_access)

    # Old cache entry should be removed and replaced with new token hash
    assert f"session:{old_access_hash}" not in fake_redis.kv
    assert f"session:{new_access_hash}" in fake_redis.kv

    cached_payload = json.loads(fake_redis.kv[f"session:{new_access_hash}"])
    assert cached_payload["session_id"] == session_id
    assert cached_payload["user_id"] == user_id
