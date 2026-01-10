from __future__ import annotations

import os
import time as _time

import pytest


def _has_psycopg() -> bool:


    try:
        import psycopg  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.integration
def test_postgres_idempotency_filters_with_iso_and_z(monkeypatch):
    dsn = os.getenv("SANDBOX_TEST_PG_DSN")
    if not dsn or not _has_psycopg():
        pytest.skip("Postgres DSN not provided or psycopg not installed")

    from tldw_Server_API.app.core.Sandbox.store import PostgresStore

    st = PostgresStore(dsn=dsn)
    # Ensure clean idempotency table for this test keyspace
    import psycopg
    with psycopg.connect(dsn, autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("DELETE FROM sandbox_idempotency WHERE endpoint LIKE 'pgtest%' OR key LIKE 'pgtest%'")

    # Insert two records with controlled timestamps using monkeypatch on store.time.time
    base = _time.time()
    monkeypatch.setattr("tldw_Server_API.app.core.Sandbox.store.time.time", lambda: base - 60)
    st.store_idempotency(endpoint="pgtest/sessions", user_id="u1", key="pgtest-k1", body={"a": 1}, object_id="obj-1", response={"ok": True})
    monkeypatch.setattr("tldw_Server_API.app.core.Sandbox.store.time.time", lambda: base + 60)
    st.store_idempotency(endpoint="pgtest/sessions", user_id="u1", key="pgtest-k2", body={"b": 2}, object_id="obj-2", response={"ok": True})

    from datetime import datetime, timezone, timedelta
    def _z(dt):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    from_iso = _z(datetime.fromtimestamp(base, tz=timezone.utc) - timedelta(seconds=10))
    to_iso = _z(datetime.fromtimestamp(base, tz=timezone.utc) + timedelta(seconds=10))

    # Window should include only the first (k1)
    items = st.list_idempotency(endpoint="pgtest/sessions", created_at_from=from_iso, created_at_to=to_iso, limit=10, offset=0)
    keys = [it.get("key") for it in items]
    assert "pgtest-k1" in keys and "pgtest-k2" not in keys

    # Count with window matching second
    from_iso2 = _z(datetime.fromtimestamp(base, tz=timezone.utc) + timedelta(seconds=10))
    to_iso2 = _z(datetime.fromtimestamp(base, tz=timezone.utc) + timedelta(seconds=120))
    cnt = st.count_idempotency(endpoint="pgtest/sessions", created_at_from=from_iso2, created_at_to=to_iso2)
    assert isinstance(cnt, int) and cnt >= 1
