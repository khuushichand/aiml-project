import os
import time
from fastapi.testclient import TestClient
from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user


class _FakeMediaDB:
    def __init__(self):
        self._items = {
            123: {"id": 123, "title": "Doc", "author": "A", "content": {"content": "short text"}},
        }

    def get_media_by_id(self, media_id: int):
        return self._items.get(media_id)


from contextlib import contextmanager


@contextmanager
def _client():
    with TestClient(app) as c:
        c.cookies.set("csrf_token", "test-csrf")
        yield c


def test_media_embedding_job_lifecycle():
    os.environ["TESTING"] = "true"
    try:
        original_allowed_providers = settings.get("ALLOWED_EMBEDDING_PROVIDERS")
        original_allowed_models = settings.get("ALLOWED_EMBEDDING_MODELS")
        original_model_limits = settings.get("EMBEDDING_MODEL_MAX_TOKENS")
        # Keep token limits permissive
        settings["ALLOWED_EMBEDDING_PROVIDERS"] = ["openai", "huggingface"]
        settings["ALLOWED_EMBEDDING_MODELS"] = ["text-embedding-3-small", "sentence-transformers/all-MiniLM-L6-v2"]
        settings["EMBEDDING_MODEL_MAX_TOKENS"] = {"openai:text-embedding-3-small": 8192}

        # Override media DB dependency
        app.dependency_overrides[get_media_db_for_user] = lambda: _FakeMediaDB()

        with _client() as client:
            # Start job
            api_key = get_settings().SINGLE_USER_API_KEY
            r = client.post("/api/v1/media/123/embeddings", json={}, headers={"X-API-KEY": api_key})
            assert r.status_code == 200
            body = r.json()
            assert body.get("status") == "accepted"
            job_id = body.get("job_id")
            assert job_id

            # Get job status (may be processing/completed/failed depending on environment)
            r2 = client.get(f"/api/v1/media/embeddings/jobs/{job_id}", headers={"X-API-KEY": api_key})
            assert r2.status_code == 200
            data = r2.json()
            assert data.get("id") == job_id
            assert data.get("media_id") == 123
            assert data.get("status") in ("processing", "completed", "failed")

            # List jobs
            r3 = client.get("/api/v1/media/embeddings/jobs", headers={"X-API-KEY": api_key})
            assert r3.status_code == 200
            j = r3.json()
            assert isinstance(j.get("data"), list)
            assert any(row.get("id") == job_id for row in j["data"])
    finally:
        os.environ.pop("TESTING", None)
        app.dependency_overrides.pop(get_media_db_for_user, None)
        if original_allowed_providers is None:
            settings.pop("ALLOWED_EMBEDDING_PROVIDERS", None)
        else:
            settings["ALLOWED_EMBEDDING_PROVIDERS"] = original_allowed_providers
        if original_allowed_models is None:
            settings.pop("ALLOWED_EMBEDDING_MODELS", None)
        else:
            settings["ALLOWED_EMBEDDING_MODELS"] = original_allowed_models
        if original_model_limits is None:
            settings.pop("EMBEDDING_MODEL_MAX_TOKENS", None)
        else:
            settings["EMBEDDING_MODEL_MAX_TOKENS"] = original_model_limits
