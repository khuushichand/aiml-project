from __future__ import annotations

import contextlib


def test_claims_rebuild_db_session_uses_managed_media_database(monkeypatch) -> None:
    from tldw_Server_API.app import main

    captured: dict[str, object] = {}

    @contextlib.contextmanager
    def _fake_managed_media_database(
        client_id: str,
        *,
        db_path: str | None = None,
        backend=None,
        config=None,
        initialize: bool = True,
        suppress_init_exceptions=(),
        suppress_close_exceptions=(),
    ):
        captured["client_id"] = client_id
        captured["db_path"] = db_path
        captured["backend"] = backend
        captured["config"] = config
        captured["initialize"] = initialize
        captured["suppress_init_exceptions"] = suppress_init_exceptions
        captured["suppress_close_exceptions"] = suppress_close_exceptions
        yield "db-sentinel"

    monkeypatch.setattr(main, "get_user_media_db_path", lambda user_id: f"/tmp/media-{user_id}.db")
    monkeypatch.setattr(main, "managed_media_database", _fake_managed_media_database)

    settings = {
        "SINGLE_USER_FIXED_ID": "17",
        "SERVER_CLIENT_ID": "startup-client",
    }

    with main._claims_rebuild_db_session(settings) as (user_id, db_path, db):
        assert user_id == 17
        assert db_path == "/tmp/media-17.db"
        assert db == "db-sentinel"

    assert captured == {
        "client_id": "startup-client",
        "db_path": "/tmp/media-17.db",
        "backend": None,
        "config": None,
        "initialize": False,
        "suppress_init_exceptions": (),
        "suppress_close_exceptions": main._STARTUP_GUARD_EXCEPTIONS,
    }
