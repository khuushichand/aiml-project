import os
import time
from fastapi.testclient import TestClient
from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.config import settings


def _client():
    c = TestClient(app)
    c.cookies.set("csrf_token", "test-csrf")
    return c


def test_embeddings_token_limit_rejected():
    # Ensure test mode rate limiting bypass
    os.environ["TESTING"] = "true"
    try:
        # Configure strict token limit
        settings["EMBEDDING_MODEL_MAX_TOKENS"] = {"openai:text-embedding-3-small": 1}
        # Allow provider/model
        settings["ALLOWED_EMBEDDING_PROVIDERS"] = ["openai"]
        settings["ALLOWED_EMBEDDING_MODELS"] = ["text-embedding-3-small"]

        client = _client()
        payload = {
            "model": "text-embedding-3-small",
            "input": "This sentence surely exceeds a single token."
        }
        r = client.post("/api/v1/embeddings", json=payload)
        assert r.status_code == 400
        data = r.json()
        assert data.get("error") == "input_too_long"
        assert "details" in data
        assert isinstance(data["details"], list) and len(data["details"]) >= 1
    finally:
        os.environ.pop("TESTING", None)


def test_embeddings_allowlist_rejected():
    os.environ["TESTING"] = "true"
    try:
        # Disallow provider/model
        settings["ALLOWED_EMBEDDING_PROVIDERS"] = ["huggingface"]
        settings["ALLOWED_EMBEDDING_MODELS"] = ["sentence-transformers/all-MiniLM-L6-v2"]

        client = _client()
        payload = {
            "model": "text-embedding-3-small",
            "input": "short"
        }
        r = client.post("/api/v1/embeddings", json=payload)
        assert r.status_code == 403
        assert "not allowed" in r.json().get("detail", "").lower()
    finally:
        os.environ.pop("TESTING", None)

