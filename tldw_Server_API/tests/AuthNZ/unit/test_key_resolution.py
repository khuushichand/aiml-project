import pytest


pytestmark = pytest.mark.unit


class _FakePostgresPool:
    def __init__(self, expected_candidates):
        self.pool = object()  # signal Postgres backend
        self.expected = tuple(expected_candidates)
        self.calls = []

    async def fetchone(self, query: str, candidates, status: str):
        # Verify candidate list and status
        self.calls.append((query, tuple(candidates), status))
        assert tuple(candidates) == self.expected
        assert status == "active"
        return {"id": 42, "user_id": 7}


class _FakeSQLitePool:
    def __init__(self, expected_candidates):
        self.pool = None  # signal SQLite backend
        self.expected = tuple(expected_candidates)
        self.calls = []

    async def fetchone(self, query: str, params):
        *candidates, status = tuple(params)
        self.calls.append((query, tuple(candidates), status))
        assert tuple(candidates) == self.expected
        assert status == "active"
        return {"id": 99, "user_id": 13}


@pytest.mark.asyncio
async def test_resolve_api_key_by_hash_postgres(monkeypatch):
    # Use APIKeyManager derivation to compute expected HMAC digests
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    from tldw_Server_API.app.core.AuthNZ.settings import Settings
    from tldw_Server_API.app.core.AuthNZ.key_resolution import resolve_api_key_by_hash
    import tldw_Server_API.app.core.AuthNZ.key_resolution as keyres

    api_key = "rotate-me-postgres"
    old_secret = "old-secret-resolve-xyz-abcdefghijklmnopqrstuvwxyz0123"
    new_secret = "new-secret-resolve-xyz-abcdefghijklmnopqrstuvwxyz0123"

    mgr = APIKeyManager()
    mgr.settings = Settings(AUTH_MODE="multi_user", JWT_SECRET_KEY=new_secret, JWT_SECONDARY_SECRET=old_secret)
    candidates = mgr.hash_candidates(api_key)

    # Patch settings and DB pool
    monkeypatch.setattr(keyres, "get_settings", lambda: mgr.settings, raising=True)
    fake_pool = _FakePostgresPool(candidates)
    async def _fake_get_db_pool():
        return fake_pool
    monkeypatch.setattr(keyres, "get_db_pool", _fake_get_db_pool, raising=True)

    result = await resolve_api_key_by_hash(api_key)
    assert result == {"id": 42, "user_id": 7}
    assert fake_pool.calls, "expected fetchone to be called with candidates"


@pytest.mark.asyncio
async def test_resolve_api_key_by_hash_sqlite(monkeypatch):
    # Use APIKeyManager derivation to compute expected HMAC digests
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    from tldw_Server_API.app.core.AuthNZ.settings import Settings
    from tldw_Server_API.app.core.AuthNZ.key_resolution import resolve_api_key_by_hash
    import tldw_Server_API.app.core.AuthNZ.key_resolution as keyres

    api_key = "rotate-me-sqlite"
    old_secret = "old-secret-resolve-abc-abcdefghijklmnopqrstuvwxyz0123"
    new_secret = "new-secret-resolve-abc-abcdefghijklmnopqrstuvwxyz0123"

    mgr = APIKeyManager()
    mgr.settings = Settings(AUTH_MODE="multi_user", JWT_SECRET_KEY=new_secret, JWT_SECONDARY_SECRET=old_secret)
    candidates = mgr.hash_candidates(api_key)

    # Patch settings and DB pool
    monkeypatch.setattr(keyres, "get_settings", lambda: mgr.settings, raising=True)
    fake_pool = _FakeSQLitePool(candidates)
    async def _fake_get_db_pool():
        return fake_pool
    monkeypatch.setattr(keyres, "get_db_pool", _fake_get_db_pool, raising=True)

    result = await resolve_api_key_by_hash(api_key)
    assert result == {"id": 99, "user_id": 13}
    assert fake_pool.calls, "expected fetchone to be called with candidates"
