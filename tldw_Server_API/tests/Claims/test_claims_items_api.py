import hashlib
import os
import tempfile
from typing import AsyncGenerator

from fastapi.testclient import TestClient

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext


def _seed_claim_db() -> tuple[str, int, int]:


     tmpdir = tempfile.mkdtemp(prefix="claims_item_")
    db_path = os.path.join(tmpdir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="1")
    db.initialize_db()
    content = "A. B. C."
    media_id, _, _ = db.add_media_with_keywords(title="Doc", media_type="text", content=content, keywords=None)
    chunk_hash = hashlib.sha256(content.encode()).hexdigest()
    db.upsert_claims([
        {
            "media_id": media_id,
            "chunk_index": 0,
            "span_start": None,
            "span_end": None,
            "claim_text": "A.",
            "confidence": 0.8,
            "extractor": "heuristic",
            "extractor_version": "v1",
            "chunk_hash": chunk_hash,
        }
    ])
    row = db.execute_query("SELECT id FROM Claims WHERE media_id = ? AND deleted = 0", (media_id,)).fetchone()
    claim_id = int(row["id"]) if isinstance(row, dict) else int(row[0])
    db.close_connection()
    return db_path, media_id, claim_id


def _principal_override(is_admin: bool):
    async def _override(request=None):
        principal = AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="tester",
            token_type="access",
            jti=None,
            roles=["admin"] if is_admin else ["user"],
            permissions=["claims.edit"],
            is_admin=is_admin,
            org_ids=[],
            team_ids=[],
        )
        if request is not None:
            try:
                request.state.auth = AuthContext(
                    principal=principal,
                    ip=None,
                    user_agent=None,
                    request_id=None,
                )
            except Exception:
                pass
        return principal

    return _override


def test_claims_item_get_and_update():


     from tldw_Server_API.app.main import app as fastapi_app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user

    class _User:
        def __init__(self) -> None:
                     self.id = 1
            self.username = "tester"
            self.is_admin = False

    async def _override_user():
        return _User()

    db_path, _, claim_id = _seed_claim_db()

    async def _override_db() -> AsyncGenerator[MediaDatabase, None]:
        override_db = MediaDatabase(db_path=db_path, client_id="1")
        try:
            yield override_db
        finally:
            try:
                override_db.close_connection()
            except Exception:
                pass

    fastapi_app.dependency_overrides[get_auth_principal] = _principal_override(False)
    fastapi_app.dependency_overrides[get_request_user] = _override_user
    fastapi_app.dependency_overrides[get_media_db_for_user] = _override_db

    try:
        with TestClient(fastapi_app) as client:
            r = client.get(f"/api/v1/claims/items/{claim_id}")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data.get("id") == claim_id

            patch = {"claim_text": "Updated claim text.", "confidence": 0.5}
            r2 = client.patch(f"/api/v1/claims/items/{claim_id}", json=patch)
            assert r2.status_code == 200, r2.text
            data2 = r2.json()
            assert data2.get("claim_text") == "Updated claim text."
            assert abs(float(data2.get("confidence") or 0) - 0.5) < 1e-6
    finally:
        fastapi_app.dependency_overrides.pop(get_auth_principal, None)
        fastapi_app.dependency_overrides.pop(get_request_user, None)
        fastapi_app.dependency_overrides.pop(get_media_db_for_user, None)


def test_claims_list_all():


     from tldw_Server_API.app.main import app as fastapi_app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user

    class _User:
        def __init__(self) -> None:
                     self.id = 1
            self.username = "tester"
            self.is_admin = False

    async def _override_user():
        return _User()

    db_path, _, _ = _seed_claim_db()

    async def _override_db() -> AsyncGenerator[MediaDatabase, None]:
        override_db = MediaDatabase(db_path=db_path, client_id="1")
        try:
            yield override_db
        finally:
            try:
                override_db.close_connection()
            except Exception:
                pass

    fastapi_app.dependency_overrides[get_auth_principal] = _principal_override(False)
    fastapi_app.dependency_overrides[get_request_user] = _override_user
    fastapi_app.dependency_overrides[get_media_db_for_user] = _override_db

    try:
        with TestClient(fastapi_app) as client:
            r = client.get("/api/v1/claims?limit=10")
            assert r.status_code == 200, r.text
            data = r.json()
            assert isinstance(data, list)
            assert len(data) >= 1
    finally:
        fastapi_app.dependency_overrides.pop(get_auth_principal, None)
        fastapi_app.dependency_overrides.pop(get_request_user, None)
        fastapi_app.dependency_overrides.pop(get_media_db_for_user, None)
