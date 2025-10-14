import hashlib
import os
import tempfile
from typing import Any

from fastapi.testclient import TestClient

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


def _setup_db_with_claims() -> tuple[MediaDatabase, int]:
    tmpdir = tempfile.mkdtemp(prefix="claims_env_")
    db_path = os.path.join(tmpdir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="test_client")
    db.initialize_db()
    content = "S1. S2. S3."
    media_id, _, _ = db.add_media_with_keywords(title="Doc", media_type="text", content=content, keywords=None)
    chunk_hash = hashlib.sha256(content.encode()).hexdigest()
    rows = []
    for i, txt in enumerate(["C1", "C2", "C3"]):
        rows.append({
            "media_id": media_id,
            "chunk_index": i,
            "span_start": None,
            "span_end": None,
            "claim_text": txt,
            "confidence": 0.9,
            "extractor": "heuristic",
            "extractor_version": "v1",
            "chunk_hash": chunk_hash,
        })
    db.upsert_claims(rows)
    return db, media_id


def test_claims_status_admin_ok():
    from tldw_Server_API.app.main import app as fastapi_app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user

    class _Admin:
        def __init__(self) -> None:
            self.id = 1
            self.username = "admin"
            self.is_admin = True

    async def _override_user():
        return _Admin()

    # DB not required for status, but keep consistent override
    async def _override_db():
        db, _ = _setup_db_with_claims()
        return db

    fastapi_app.dependency_overrides[get_request_user] = _override_user
    fastapi_app.dependency_overrides[get_media_db_for_user] = _override_db

    with TestClient(fastapi_app) as client:
        r = client.get("/api/v1/claims/status")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "ok"
        assert isinstance(data.get("stats", {}), dict)
        assert isinstance(data.get("queue_length"), int)
        # workers may be None or int depending on initialized state
        assert data.get("workers") is None or isinstance(data.get("workers"), int)


def test_claims_envelope_pagination_absolute_link():
    from tldw_Server_API.app.main import app as fastapi_app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user

    class _Admin:
        def __init__(self) -> None:
            self.id = 1
            self.username = "admin"
            self.is_admin = True

    db, media_id = _setup_db_with_claims()

    async def _override_user():
        return _Admin()

    async def _override_db():
        return db

    fastapi_app.dependency_overrides[get_request_user] = _override_user
    fastapi_app.dependency_overrides[get_media_db_for_user] = _override_db

    with TestClient(fastapi_app) as client:
        r1 = client.get(f"/api/v1/claims/{media_id}", params={"limit": 1, "offset": 0, "envelope": True, "absolute_links": True})
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert isinstance(body1.get("total"), int)
        assert isinstance(body1.get("total_pages"), int)
        next_link = body1.get("next_link")
        if body1.get("next_offset") is not None:
            assert isinstance(next_link, str) and next_link.startswith("http")
            r2 = client.get(next_link)
            assert r2.status_code == 200, r2.text
            body2 = r2.json()
            assert body2.get("items"), "Second page items missing"


def test_claims_status_forbidden_non_admin():
    from tldw_Server_API.app.main import app as fastapi_app
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user

    class _User:
        def __init__(self) -> None:
            self.id = 1
            self.username = "u"
            self.is_admin = False

    async def _override_user():
        return _User()

    fastapi_app.dependency_overrides[get_request_user] = _override_user

    with TestClient(fastapi_app) as client:
        r = client.get("/api/v1/claims/status")
        assert r.status_code == 403
