from typing import AsyncGenerator

from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal
from tldw_Server_API.app.core.DB_Management.media_db.runtime.validation import MediaDbLike
from tldw_Server_API.tests.test_utils import create_test_media


def _principal_override():


    async def _override(request=None) -> AuthPrincipal:
        principal = AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="test-user",
            token_type="single_user",
            jti=None,
            roles=["admin"],
            permissions=["media.update"],
            is_admin=True,
            org_ids=[],
            team_ids=[],
        )
        if request is not None:
            request.state.auth = AuthContext(
                principal=principal,
                ip=None,
                user_agent=None,
                request_id=None,
            )
        return principal

    return _override


def test_reprocess_rebuilds_chunks(tmp_path, monkeypatch, managed_test_media_db):


    from tldw_Server_API.app.main import app as fastapi_app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user

    monkeypatch.setenv("TEST_MODE", "1")

    db_path = tmp_path / "media.db"
    with managed_test_media_db(
        "test_client",
        db_path=str(db_path),
        initialize=False,
    ) as seed_db:
        media_id = create_test_media(seed_db, title="Test Doc", content="One two three four five.")

    async def _override_user() -> User:
        return User(id=1, username="tester", email=None, is_active=True)

    async def _override_db() -> AsyncGenerator[MediaDbLike, None]:
        with managed_test_media_db(
            "test_client",
            db_path=str(db_path),
            initialize=False,
        ) as override_db:
            yield override_db

    fastapi_app.dependency_overrides[get_request_user] = _override_user
    fastapi_app.dependency_overrides[get_auth_principal] = _principal_override()
    fastapi_app.dependency_overrides[get_media_db_for_user] = _override_db

    try:
        with TestClient(fastapi_app) as client:
            resp = client.post(
                f"/api/v1/media/{media_id}/reprocess",
                json={
                    "perform_chunking": True,
                    "chunk_method": "sentences",
                    "chunk_size": 50,
                    "chunk_overlap": 10,
                    "generate_embeddings": False,
                },
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["media_id"] == media_id
            assert data["status"] == "completed"
            assert isinstance(data["chunks_created"], int)
            assert data["chunks_created"] >= 1
    finally:
        fastapi_app.dependency_overrides.pop(get_request_user, None)
        fastapi_app.dependency_overrides.pop(get_auth_principal, None)
        fastapi_app.dependency_overrides.pop(get_media_db_for_user, None)

    with managed_test_media_db(
        "test_client",
        db_path=str(db_path),
        initialize=False,
    ) as check_db:
        row = check_db.execute_query(
            "SELECT count(*) AS c FROM UnvectorizedMediaChunks WHERE media_id = ?",
            (media_id,),
        ).fetchone()
    count_val = row["c"] if isinstance(row, dict) else row[0]
    assert count_val >= 1


def test_reprocess_missing_media_returns_404(tmp_path, managed_test_media_db):


    from tldw_Server_API.app.main import app as fastapi_app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user

    db_path = tmp_path / "media.db"
    with managed_test_media_db(
        "test_client",
        db_path=str(db_path),
        initialize=False,
    ):
        pass

    async def _override_user() -> User:
        return User(id=1, username="tester", email=None, is_active=True)

    async def _override_db() -> AsyncGenerator[MediaDbLike, None]:
        with managed_test_media_db(
            "test_client",
            db_path=str(db_path),
            initialize=False,
        ) as override_db:
            yield override_db

    fastapi_app.dependency_overrides[get_request_user] = _override_user
    fastapi_app.dependency_overrides[get_auth_principal] = _principal_override()
    fastapi_app.dependency_overrides[get_media_db_for_user] = _override_db

    try:
        with TestClient(fastapi_app) as client:
            resp = client.post(
                "/api/v1/media/9999/reprocess",
                json={"perform_chunking": True},
            )
            assert resp.status_code == 404, resp.text
    finally:
        fastapi_app.dependency_overrides.pop(get_request_user, None)
        fastapi_app.dependency_overrides.pop(get_auth_principal, None)
        fastapi_app.dependency_overrides.pop(get_media_db_for_user, None)
