import hashlib
import os
import tempfile
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


@pytest.mark.integration
def test_claims_endpoints_list_and_rebuild():
    # Create temp DB and seed one media + claim
    tmpdir = tempfile.mkdtemp(prefix="claims_api_")
    db_path = os.path.join(tmpdir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="test_client")
    db.initialize_db()

    content = "Hello world. This is a test document. It contains a few sentences."
    media_id, _, _ = db.add_media_with_keywords(
        title="Doc", media_type="text", content=content, keywords=None
    )
    chunk_hash = hashlib.sha256(content.encode()).hexdigest()
    db.upsert_claims([
        {
            "media_id": media_id,
            "chunk_index": 0,
            "span_start": None,
            "span_end": None,
            "claim_text": "This is a test document.",
            "confidence": 0.9,
            "extractor": "heuristic",
            "extractor_version": "v1",
            "chunk_hash": chunk_hash,
        }
    ])

    # Build app and override dependencies for auth + DB
    from tldw_Server_API.app.main import app as fastapi_app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user

    class _User:
        def __init__(self):
            self.id = 1
            self.username = "tester"
            self.is_admin = True

    # Always return our seeded DB (single-user simulation)
    async def _override_db() -> MediaDatabase:
        return db

    async def _override_user():
        return _User()

    fastapi_app.dependency_overrides[get_media_db_for_user] = _override_db
    fastapi_app.dependency_overrides[get_request_user] = _override_user

    with TestClient(fastapi_app) as client:
        # List claims
        r = client.get(f"/api/v1/claims/{media_id}?limit=10")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and data
        assert any("test document" in c.get("claim_text", "") for c in data)

        # Rebuild single media (accept only)
        r2 = client.post(f"/api/v1/claims/{media_id}/rebuild")
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2.get("status") == "accepted"
        assert int(body2.get("media_id")) == int(media_id)

        # Rebuild FTS
        r3 = client.post("/api/v1/claims/rebuild_fts")
        assert r3.status_code == 200
        body3 = r3.json()
        assert body3.get("status") == "ok"
        assert isinstance(body3.get("indexed"), int)

        # Rebuild all (missing policy)
        r4 = client.post("/api/v1/claims/rebuild/all", params={"policy": "missing"})
        assert r4.status_code == 200
        body4 = r4.json()
        assert body4.get("status") == "accepted"
        assert body4.get("policy") in {"missing", "all", "stale"}

    try:
        db.close_connection()
    except Exception:
        pass
