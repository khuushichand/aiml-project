import math
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from fastapi import Request
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User


@pytest.mark.unit
def test_embeddings_endpoint_adapter_multi_with_l2(monkeypatch):
    monkeypatch.setenv("LLM_EMBEDDINGS_ADAPTERS_ENABLED", "1")
    monkeypatch.setenv("LLM_EMBEDDINGS_L2_NORMALIZE", "1")
    monkeypatch.setenv("TEST_MODE", "1")

    # Provide a dummy user via dependency override
    test_user = User(id=1, username="tester", email="t@example.com", is_active=True)

    async def _mock_user(_request: Request):  # noqa: D401, ARG001
        return test_user

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_request_user] = _mock_user

    class _StubAdapter:
        def capabilities(self):  # noqa: D401
            return {"dimensions_default": None, "max_batch_size": 2048}

        def embed(self, request, *, timeout=None):  # noqa: ANN001
            # Return two embeddings with obvious norms
            return {
                "data": [
                    {"index": 0, "embedding": [3.0, 4.0]},
                    {"index": 1, "embedding": [0.0, 5.0]},
                ],
                "model": request.get("model"),
            }

    class _StubRegistry:
        def get_adapter(self, name):  # noqa: ANN001
            return _StubAdapter()

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.embeddings_adapter_registry.get_embeddings_registry",
        return_value=_StubRegistry(),
    ):
        with TestClient(app) as client:
            payload = {"model": "openai:text-embedding-3-small", "input": ["a", "b"]}
            r = client.post("/api/v1/embeddings", json=payload)
            assert r.status_code == 200, r.text
            body = r.json()
            embs = [d["embedding"] for d in body.get("data", [])]
            assert len(embs) == 2
            # Check unit length after L2 normalization
            for v in embs:
                n = math.sqrt(sum(x * x for x in v))
                assert abs(n - 1.0) < 1e-5

    app.dependency_overrides = original_overrides
