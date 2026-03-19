from pathlib import Path
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.api.v1.API_Deps import DB_Deps as deps
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.DB_Management.media_db.api import MediaDbFactory
from tldw_Server_API.app.core.DB_Management.media_db.errors import ConflictError
from tldw_Server_API.app.core.DB_Management.media_db.runtime import session as media_db_session
from tldw_Server_API.app.core.DB_Management.media_db.runtime import validation as media_db_validation


def test_factory_returns_distinct_sessions_for_distinct_scopes() -> None:
    factory = MediaDbFactory.for_sqlite_path(":memory:", client_id="scope-test")

    first = factory.for_request(org_id=10, team_id=20)
    second = factory.for_request(org_id=11, team_id=21)

    assert first is not second
    assert (first.org_id, first.team_id) == (10, 20)
    assert (second.org_id, second.team_id) == (11, 21)


def test_media_db_session_runtime_module_no_longer_mentions_media_db_v2_in_source() -> None:
    source = Path(media_db_session.__file__).read_text()
    assert "Media_DB_v2" not in source


def test_cached_factory_does_not_mutate_existing_session_scope() -> None:
    factory = MediaDbFactory.for_sqlite_path(":memory:", client_id="scope-test")

    first = factory.for_request(org_id=1, team_id=2)
    _ = factory.for_request(org_id=3, team_id=4)

    assert (first.org_id, first.team_id) == (1, 2)


def test_for_sqlite_path_provisions_shared_backend_for_request_scopes(monkeypatch) -> None:
    sentinel_backend = object()
    backend_calls: list[tuple[str, str]] = []
    database_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        media_db_session,
        "_create_sqlite_backend",
        lambda db_path, client_id: backend_calls.append((db_path, client_id)) or sentinel_backend,
    )

    def _fake_database_factory(**kwargs):
        database_calls.append(kwargs)
        return SimpleNamespace(
            default_org_id=None,
            default_team_id=None,
            release_context_connection=lambda: None,
        )

    factory = media_db_session.MediaDbFactory.for_sqlite_path(
        "/tmp/scope-test.db",
        client_id="scope-test",
    )
    factory.database_factory = _fake_database_factory

    first = factory.for_request(org_id=10, team_id=20)
    second = factory.for_request(org_id=11, team_id=21)

    assert backend_calls == [("/tmp/scope-test.db", "scope-test")]
    assert factory.backend is sentinel_backend
    assert database_calls == [
        {
            "db_path": "/tmp/scope-test.db",
            "client_id": "scope-test",
            "backend": sentinel_backend,
        },
        {
            "db_path": "/tmp/scope-test.db",
            "client_id": "scope-test",
            "backend": sentinel_backend,
        },
    ]
    assert (first.org_id, first.team_id) == (10, 20)
    assert (second.org_id, second.team_id) == (11, 21)


def _make_user(user_id: int = 1) -> User:
    return User(
        id=user_id,
        username=f"user-{user_id}",
        roles=["user"],
        permissions=[],
        is_admin=False,
    )


def test_get_or_create_media_db_factory_caches_factory_per_user(monkeypatch) -> None:
    created: list[object] = []

    class FakeFactory:
        def __init__(self, *, db_path: str, client_id: str):
            self.db_path = db_path
            self.client_id = client_id
            created.append(self)

    monkeypatch.setattr(deps, "_media_db_factories", {}, raising=False)
    monkeypatch.setattr(deps, "_get_db_path_for_user", lambda user_id: Path(f"/tmp/{user_id}.db"), raising=True)
    monkeypatch.setattr(deps, "get_content_backend_instance", lambda: None, raising=True)
    monkeypatch.setattr(
        deps.MediaDbFactory,
        "for_sqlite_path",
        classmethod(lambda cls, db_path, client_id: FakeFactory(db_path=db_path, client_id=client_id)),
        raising=True,
    )

    first = deps._get_or_create_media_db_factory(_make_user())
    second = deps._get_or_create_media_db_factory(_make_user())

    assert first is second
    assert len(created) == 1


def test_get_or_create_media_db_factory_accepts_string_user_ids_via_id_int(monkeypatch) -> None:
    created: list[object] = []

    class FakeFactory:
        def __init__(self, *, db_path: str, client_id: str):
            self.db_path = db_path
            self.client_id = client_id
            created.append(self)

    monkeypatch.setattr(deps, "_media_db_factories", {}, raising=False)
    monkeypatch.setattr(deps, "_get_db_path_for_user", lambda user_id: Path(f"/tmp/{user_id}.db"), raising=True)
    monkeypatch.setattr(deps, "get_content_backend_instance", lambda: None, raising=True)
    monkeypatch.setattr(
        deps.MediaDbFactory,
        "for_sqlite_path",
        classmethod(lambda cls, db_path, client_id: FakeFactory(db_path=db_path, client_id=client_id)),
        raising=True,
    )

    string_user = _make_user()
    string_user.id = "7"

    factory = deps._get_or_create_media_db_factory(string_user)

    assert factory is created[0]
    assert factory.db_path == "/tmp/7.db"


def test_resolve_media_db_for_user_returns_fresh_scoped_session_from_cached_factory(monkeypatch) -> None:
    sessions: list[object] = []

    class FakeFactory:
        def for_request(self, *, org_id=None, team_id=None):
            session = SimpleNamespace(
                org_id=org_id,
                team_id=team_id,
                release_context_connection=lambda: None,
            )
            sessions.append(session)
            return session

    scopes = [
        SimpleNamespace(effective_org_id=10, effective_team_id=20),
        SimpleNamespace(effective_org_id=11, effective_team_id=21),
    ]

    monkeypatch.setattr(deps, "_get_or_create_media_db_factory", lambda current_user: FakeFactory(), raising=False)
    monkeypatch.setattr(deps, "get_scope", lambda: scopes.pop(0), raising=True)
    monkeypatch.setattr(deps, "get_content_backend_instance", lambda: None, raising=True)
    monkeypatch.setattr(deps, "_get_db_path_for_user", lambda user_id: Path(f"/tmp/{user_id}.db"), raising=True)

    class FakeLegacyDb:
        def __init__(self, db_path: str, client_id: str, backend=None):
            self.db_path = db_path
            self.client_id = client_id
            self.default_org_id = None
            self.default_team_id = None

        def release_context_connection(self) -> None:
            return None

    monkeypatch.setattr(deps, "MediaDatabase", FakeLegacyDb, raising=True)
    monkeypatch.setattr(deps, "_user_db_instances", {}, raising=True)

    first = deps._resolve_media_db_for_user(_make_user())
    second = deps._resolve_media_db_for_user(_make_user())

    assert first is not second
    assert (first.org_id, first.team_id) == (10, 20)
    assert (second.org_id, second.team_id) == (11, 21)
    assert len(sessions) == 2


def test_reset_media_db_cache_closes_cached_factories(monkeypatch) -> None:
    closed: list[str] = []

    class _FakeFactory:
        def close(self) -> None:
            closed.append("closed")

    monkeypatch.setattr(deps, "_media_db_factories", {1: _FakeFactory()}, raising=True)
    monkeypatch.setattr(deps, "_user_db_instances", {}, raising=True)

    deps.reset_media_db_cache()

    assert closed == ["closed"]
    assert deps._media_db_factories == {}


def test_conflict_error_str_includes_zero_identifier() -> None:
    exc = ConflictError(entity="Media", identifier=0)

    assert "ID: 0" in str(exc)


def test_media_db_validation_requires_full_legacy_helper_contract() -> None:
    incomplete = SimpleNamespace(
        execute_query=lambda *args, **kwargs: None,
        transaction=lambda: None,
        client_id="scope-test",
        db_path_str=":memory:",
    )

    with pytest.raises(TypeError):
        media_db_validation.require_media_database_like(
            incomplete,
            error_message="expected media db",
        )
