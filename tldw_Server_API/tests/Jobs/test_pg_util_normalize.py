import sys
import types

from tldw_Server_API.app.core.Jobs.pg_util import normalize_pg_dsn, negotiate_pg_dsn


def test_normalize_pg_dsn_encodes_options_spaces():
    dsn = "postgresql://tldw_user:TestPassword123!@127.0.0.1:5432/tldw_content"
    out = normalize_pg_dsn(dsn)
    assert out.startswith(dsn)
    assert "connect_timeout=" in out
    # options must be RFC3986 encoded (spaces as %20, not '+')
    assert "%20" in out and "+" not in out.split("?")[-1]
    # options are RFC3986-encoded; '=' becomes %3D in the query
    assert "statement_timeout%3D" in out
    assert "lock_timeout%3D" in out
    assert "idle_in_transaction_session_timeout%3D" in out


def test_negotiate_pg_dsn_downgrades_on_unrecognized_parameter(monkeypatch):
    # Inject a fake psycopg module that fails when idle_in_transaction_session_timeout is present
    fake_psycopg = types.SimpleNamespace()

    calls = {"dsns": []}

    class FakeError(Exception):
        pass

    def fake_connect(dsn):
        calls["dsns"].append(dsn)
        q = dsn.split("?", 1)[-1]
        if "options=" in q and "idle_in_transaction_session_timeout" in q:
            raise FakeError("unrecognized configuration parameter \"idle_in_transaction_session_timeout\"")
        # succeed otherwise
        class _Conn:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Conn()

    fake_psycopg.connect = fake_connect  # type: ignore
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    base = "postgresql://tldw_user:TestPassword123!@127.0.0.1:5432/tldw_content"
    out = negotiate_pg_dsn(base)
    # Negotiated DSN should not include idle_in_transaction_session_timeout
    assert "idle_in_transaction_session_timeout" not in out
    assert "statement_timeout" in out
    assert "lock_timeout" in out
    # Ensure we attempted at least two DSNs (full, then downgraded)
    assert len(calls["dsns"]) >= 2
