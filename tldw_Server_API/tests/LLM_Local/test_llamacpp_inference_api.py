import os
from typing import Tuple

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def llamacpp_client() -> Tuple[TestClient, dict]:
    os.environ.setdefault("AUTH_MODE", "single_user")
    os.environ.setdefault("TESTING", "true")
    # Enable llamacpp router
    cur = os.getenv("ROUTES_ENABLE", "")
    parts = [p.strip().lower() for p in cur.replace(" ", ",").split(",") if p.strip()]
    if "llamacpp" not in parts:
        parts.append("llamacpp")
    os.environ["ROUTES_ENABLE"] = ",".join(parts)

    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    from tldw_Server_API.app.main import app
    api_key = get_settings().SINGLE_USER_API_KEY
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    client = TestClient(app)
    return client, headers


@pytest.mark.integration
def test_llamacpp_inference_happy_path(llamacpp_client, monkeypatch):
    client, headers = llamacpp_client

    # Patch llm_manager on the endpoint module
    class _Mgr:
        llamacpp = True
        class _Logger:
            def error(self, *a, **kw):
                pass
        logger = _Logger()
        async def get_server_status(self, backend: str):
            return {"backend": backend, "model": "mock.gguf"}
        async def run_inference(self, backend: str, model_name_or_path: str, prompt=None, **kwargs):
            # Echo a minimal OpenAI-style response
            return {
                "model": model_name_or_path,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}}],
                "kwargs": kwargs,
            }

    import tldw_Server_API.app.api.v1.endpoints.llamacpp as lp
    monkeypatch.setattr(lp, "llm_manager", _Mgr(), raising=False)

    payload = {
        "model": "ignored-by-server",
        "messages": [
            {"role": "user", "content": "Hello!"}
        ],
        "temperature": 0.7,
    }
    r = client.post("/api/v1/llamacpp/inference", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model"] == "mock.gguf"
    assert body["choices"][0]["message"]["content"] == "hi"
