from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pytest

from tldw_Server_API.app.core.AuthNZ.session_manager import SessionManager
from tldw_Server_API.app.core.AuthNZ.settings import Settings


class _FakeTransaction:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self, conn):
        self.pool = object()  # Marker so SessionManager treats as Postgres path
        self._conn = conn

    def transaction(self):
        return _FakeTransaction(self._conn)


class _FakeConn:
    def __init__(self, session_record: Dict[str, Any]):
        self._session_record = session_record
        self.fetchrow_calls = 0

    async def fetchrow(self, query: str, *args):
        if "SELECT id, user_id" in query:
            self.fetchrow_calls += 1
            return dict(self._session_record)
        return None

    async def execute(self, *args, **kwargs):
        return None


class _StubBlacklist:
    def __init__(self):
        self.calls = []

    def hint_blacklisted(self, jti: str, expires_at: datetime):
        self.calls.append(("hint", jti, expires_at))

    async def revoke_token(
        self,
        *,
        jti: str,
        expires_at: datetime,
        user_id: Optional[int],
        token_type: str,
        reason: Optional[str],
        revoked_by: Optional[int],
        ip_address: Optional[str],
    ) -> bool:
        self.calls.append(
            ("revoke", jti, expires_at, user_id, token_type, reason, revoked_by, ip_address)
        )
        return True


@pytest.mark.asyncio
async def test_revoke_session_blacklists_tokens(monkeypatch):
    now = datetime.utcnow()
    session_record = {
        "id": 123,
        "user_id": 456,
        "access_jti": "access-jti-xyz",
        "refresh_jti": "refresh-jti-xyz",
        "expires_at": now + timedelta(minutes=15),
        "refresh_expires_at": now + timedelta(days=2),
    }

    settings = Settings(AUTH_MODE="multi_user", JWT_SECRET_KEY="rotation-new-secret-1234567890abcd")
    manager = SessionManager(settings=settings)
    manager._initialized = True
    manager._external_db_pool = True

    fake_conn = _FakeConn(session_record)
    fake_pool = _FakePool(fake_conn)

    async def _fake_ensure_db_pool():
        return fake_pool

    monkeypatch.setattr(manager, "_ensure_db_pool", _fake_ensure_db_pool)

    stub_blacklist = _StubBlacklist()
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.session_manager.get_token_blacklist",
        lambda: stub_blacklist,
    )

    await manager.revoke_session(session_id=123, revoked_by=42, reason="unit-test")

    revoke_events = [
        call for call in stub_blacklist.calls if call and call[0] == "revoke"
    ]
    assert len(revoke_events) == 2
    access_event = next(evt for evt in revoke_events if evt[4] == "access")
    refresh_event = next(evt for evt in revoke_events if evt[4] == "refresh")
    assert access_event[1] == session_record["access_jti"]
    assert refresh_event[1] == session_record["refresh_jti"]
