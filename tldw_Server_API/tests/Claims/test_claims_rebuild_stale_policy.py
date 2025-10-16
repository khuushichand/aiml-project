import hashlib
import os
import tempfile

from fastapi.testclient import TestClient

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


def test_rebuild_all_stale_policy_enqueues_expected_media(monkeypatch):
    # Temp DB and seed: two media, both have claims; make one stale by bumping Media.last_modified
    tmpdir = tempfile.mkdtemp(prefix="claims_stale_")
    db_path = os.path.join(tmpdir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="test_client")
    db.initialize_db()

    # Media A (stale): claims older than media.last_modified
    content_a = "A1. A2."
    mid_a, _, _ = db.add_media_with_keywords(title="A", media_type="text", content=content_a, keywords=None)
    chash_a = hashlib.sha256(content_a.encode()).hexdigest()
    db.upsert_claims([
        {
            "media_id": mid_a,
            "chunk_index": 0,
            "span_start": None,
            "span_end": None,
            "claim_text": "A1.",
            "confidence": None,
            "extractor": "heuristic",
            "extractor_version": "v1",
            "chunk_hash": chash_a,
        }
    ])
    # Make claims older than media by setting Claims.last_modified far in the past
    db.execute_query("UPDATE Claims SET last_modified = ? WHERE media_id = ?", ("2000-01-01T00:00:00.000Z", mid_a))

    # Media B (not stale): claims up-to-date
    content_b = "B1. B2."
    mid_b, _, _ = db.add_media_with_keywords(title="B", media_type="text", content=content_b, keywords=None)
    chash_b = hashlib.sha256(content_b.encode()).hexdigest()
    db.upsert_claims([
        {
            "media_id": mid_b,
            "chunk_index": 0,
            "span_start": None,
            "span_end": None,
            "claim_text": "B1.",
            "confidence": None,
            "extractor": "heuristic",
            "extractor_version": "v1",
            "chunk_hash": chash_b,
        }
    ])

    # Build app and override dependencies
    from tldw_Server_API.app.main import app as fastapi_app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user

    class _User:
        def __init__(self):
            self.id = 1
            self.username = "admin"
            self.is_admin = True

    async def _override_db():
        return db

    async def _override_user():
        return _User()

    fastapi_app.dependency_overrides[get_media_db_for_user] = _override_db
    fastapi_app.dependency_overrides[get_request_user] = _override_user

    # Replace background service with a fake collector
    submissions = []

    class _FakeSvc:
        def submit(self, media_id: int, db_path: str):
            submissions.append((int(media_id), db_path))

    # Patch the endpoints module import
    import tldw_Server_API.app.api.v1.endpoints.claims as claims_ep
    monkeypatch.setattr(claims_ep, "get_claims_rebuild_service", lambda: _FakeSvc())

    with TestClient(fastapi_app) as client:
        r = client.post("/api/v1/claims/rebuild/all", params={"policy": "stale"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "accepted"
        assert body.get("policy") == "stale"
        assert body.get("enqueued") == 1

    # Ensure only stale media was enqueued
    mids = [m for m, _ in submissions]
    assert mids == [mid_a]

    try:
        db.close_connection()
    except Exception:
        pass
