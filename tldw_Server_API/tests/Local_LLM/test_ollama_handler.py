import asyncio
import pytest

from tldw_Server_API.app.core.Local_LLM.Ollama_Handler import OllamaHandler
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Schemas import OllamaConfig
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions import InferenceError


@pytest.mark.asyncio
async def test_ollama_inference_404_pull_then_retry(monkeypatch):
    cfg = OllamaConfig()
    handler = OllamaHandler(cfg, global_app_config={})

    # Pretend ollama is installed
    monkeypatch.setattr(handler, "is_ollama_installed", lambda: asyncio.sleep(0, result=True))
    # Model not available initially
    monkeypatch.setattr(handler, "is_model_available", lambda model_name: asyncio.sleep(0, result=False))
    # pull_model succeeds
    monkeypatch.setattr(handler, "pull_model", lambda model_name: asyncio.sleep(0, result="ok"))

    # First request_json raises 404, second returns success
    import tldw_Server_API.app.core.Local_LLM.Ollama_Handler as ol_mod
    calls = {"n": 0}
    async def fake_request_json(client, method, url, json=None, headers=None, retries=2, backoff=0.0):
        if calls["n"] == 0:
            calls["n"] += 1
            import httpx
            req = httpx.Request(method, url)
            resp = httpx.Response(404, request=req, text="model not found")
            raise httpx.HTTPStatusError("not found", request=req, response=resp)
        return {"response": "ok"}
    monkeypatch.setattr(ol_mod, "request_json", fake_request_json)

    result = await handler.inference(model_name="m", prompt="hi")
    assert result["response"] == "ok"


@pytest.mark.asyncio
async def test_ollama_inference_start_then_retry(monkeypatch):
    cfg = OllamaConfig()
    handler = OllamaHandler(cfg, global_app_config={})

    # Model is available
    monkeypatch.setattr(handler, "is_model_available", lambda model_name: asyncio.sleep(0, result=True))

    # First request_json raises connection error; then serve + ready + retry succeed
    import tldw_Server_API.app.core.Local_LLM.Ollama_Handler as ol_mod
    calls = {"n": 0}
    async def fake_request_json(client, method, url, json=None, headers=None, retries=2, backoff=0.0):
        if calls["n"] == 0:
            calls["n"] += 1
            raise Exception("connection error")
        return {"response": "ok"}
    monkeypatch.setattr(ol_mod, "request_json", fake_request_json)

    # serve_model called, readiness ok
    monkeypatch.setattr(handler, "serve_model", lambda model_name, port=None, host="127.0.0.1": asyncio.sleep(0, result={"status": "started"}))
    monkeypatch.setattr(ol_mod, "wait_for_http_ready", lambda base_url, timeout_total=30.0, interval=0.5: asyncio.sleep(0, result=True))

    result = await handler.inference(model_name="m", prompt="hi")
    assert result["response"] == "ok"
