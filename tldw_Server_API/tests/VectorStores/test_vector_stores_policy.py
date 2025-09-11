import os
from fastapi.testclient import TestClient
from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.config import settings


def _client():
    c = TestClient(app)
    c.cookies.set("csrf_token", "test-csrf")
    return c


def test_upsert_content_token_limit_and_allowlist():
    os.environ["TESTING"] = "true"
    try:
        # Configure allowlist and token limits
        settings["ALLOWED_EMBEDDING_PROVIDERS"] = ["openai"]
        settings["ALLOWED_EMBEDDING_MODELS"] = ["text-embedding-3-small"]
        settings["EMBEDDING_MODEL_MAX_TOKENS"] = {"openai:text-embedding-3-small": 2}

        client = _client()
        # Create a vector store
        vs = client.post("/api/v1/vector_stores", json={"name": "PolStore", "dimensions": 8}).json()
        store_id = vs["id"]

        # Upsert with content that exceeds 2 tokens
        records = {"records": [{"content": "This clearly exceeds two tokens.", "metadata": {}}]}
        r = client.post(f"/api/v1/vector_stores/{store_id}/vectors", json=records)
        assert r.status_code == 400
        j = r.json()
        assert j.get("error") == "input_too_long"

        # Upsert with short content passes token limit but still requires embedding provider/model allowed
        records2 = {"records": [{"content": "hi", "metadata": {}}]}
        # We can't assert success here without embedding backend; just ensure it reaches embedding path.
        # It may still fail later if embeddings unavailable, but should not fail with policy error now.
        r2 = client.post(f"/api/v1/vector_stores/{store_id}/vectors", json=records2)
        assert r2.status_code in (200, 500)
        if r2.status_code == 500:
            # Should not be a policy error
            assert "not allowed" not in r2.text.lower()
    finally:
        os.environ.pop("TESTING", None)


def test_query_token_limit_and_allowlist():
    os.environ["TESTING"] = "true"
    try:
        settings["ALLOWED_EMBEDDING_PROVIDERS"] = ["openai"]
        settings["ALLOWED_EMBEDDING_MODELS"] = ["text-embedding-3-small"]
        settings["EMBEDDING_MODEL_MAX_TOKENS"] = {"openai:text-embedding-3-small": 1}

        client = _client()
        vs = client.post("/api/v1/vector_stores", json={"name": "PolStore2", "dimensions": 8}).json()
        store_id = vs["id"]

        # Query with long text should be rejected by token limit
        r = client.post(f"/api/v1/vector_stores/{store_id}/query", json={"query": "Too long here", "top_k": 3})
        assert r.status_code == 400
        assert "input_too_long" in r.text

        # Disallow provider to trigger allowlist failure
        settings["ALLOWED_EMBEDDING_PROVIDERS"] = ["huggingface"]
        r2 = client.post(f"/api/v1/vector_stores/{store_id}/query", json={"query": "hi", "top_k": 3})
        assert r2.status_code == 403
        assert "not allowed" in r2.text.lower()
    finally:
        os.environ.pop("TESTING", None)

