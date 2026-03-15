from pathlib import Path
from types import SimpleNamespace

from tldw_Server_API.app.api.v1.API_Deps import DB_Deps as deps
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.DB_Management.media_db.api import MediaDbFactory


def test_factory_returns_distinct_sessions_for_distinct_scopes() -> None:
    factory = MediaDbFactory.for_sqlite_path(":memory:", client_id="scope-test")

    first = factory.for_request(org_id=10, team_id=20)
    second = factory.for_request(org_id=11, team_id=21)

    assert first is not second
    assert (first.org_id, first.team_id) == (10, 20)
    assert (second.org_id, second.team_id) == (11, 21)


def test_cached_factory_does_not_mutate_existing_session_scope() -> None:
    factory = MediaDbFactory.for_sqlite_path(":memory:", client_id="scope-test")

    first = factory.for_request(org_id=1, team_id=2)
    _ = factory.for_request(org_id=3, team_id=4)

    assert (first.org_id, first.team_id) == (1, 2)


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
