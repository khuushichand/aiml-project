import os

import pytest


AUTO_MOCK_PROVIDERS = {"openai", "groq", "mistral"}


def _api_key() -> str:
    return os.environ.get("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")


def _auth_headers() -> dict:
    return {"X-API-KEY": _api_key()}


def _require_ok(resp, label: str) -> None:
    if not resp.ok:
        raise AssertionError(f"{label} failed: status={resp.status} body={resp.text()}")


def _metric_sum(payload: dict, metric_name: str) -> float:
    stats = payload.get("metrics", {}).get(metric_name)
    if not stats:
        return 0.0
    try:
        return float(stats.get("sum", 0.0))
    except Exception:
        return 0.0


def _select_provider(providers: list, provider_type: str, disallowed: set[str]) -> tuple[dict | None, str | None]:
    for provider in providers:
        if provider.get("type") != provider_type:
            continue
        if not provider.get("is_configured"):
            continue
        if provider.get("name") in disallowed:
            continue
        models = provider.get("models") or []
        if not models:
            continue
        health = provider.get("health") or {}
        if health and str(health.get("status", "")).lower() not in {"healthy", "ok"}:
            continue
        return provider, models[0]
    return None, None


def _chat_payload(provider_name: str, model: str, message: str, stream: bool) -> dict:
    return {
        "api_provider": provider_name,
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "temperature": 0.2,
        "max_tokens": 128,
        "stream": stream,
    }


@pytest.mark.e2e
@pytest.mark.local_llm_service
def test_llm_provider_local_workflow(page, server_url):
    if os.getenv("RUN_LOCAL_LLM_E2E", "").lower() not in {"1", "true", "yes", "y", "on"}:
        pytest.skip("Local LLM E2E disabled; set RUN_LOCAL_LLM_E2E=1 to enable.")

    headers = _auth_headers()
    providers_resp = page.request.get("/api/v1/llm/providers", headers=headers)
    _require_ok(providers_resp, "list providers")
    providers = providers_resp.json().get("providers", [])

    provider, model = _select_provider(providers, "local", set())
    if not provider:
        pytest.skip("No configured local LLM provider found.")
    provider_name = provider["name"]

    provider_resp = page.request.get(f"/api/v1/llm/providers/{provider_name}", headers=headers)
    _require_ok(provider_resp, "provider details")
    assert provider_resp.json().get("name") == provider_name

    metrics_before = page.request.get("/api/v1/metrics/chat", headers=headers)
    _require_ok(metrics_before, "chat metrics before")
    before_sum = _metric_sum(metrics_before.json(), "chat_requests_total")

    completion_resp = page.request.post(
        "/api/v1/chat/completions",
        headers=headers,
        json=_chat_payload(provider_name, model, "Say hello from local provider.", False),
    )
    _require_ok(completion_resp, "chat completion")
    completion_payload = completion_resp.json()
    assert completion_payload.get("choices")

    stream_resp = page.request.post(
        "/api/v1/chat/completions",
        headers=headers,
        json=_chat_payload(provider_name, model, "Stream a short reply.", True),
    )
    _require_ok(stream_resp, "chat completion stream")
    stream_body = stream_resp.text()
    assert "data:" in stream_body or "choices" in stream_body

    metrics_after = page.request.get("/api/v1/metrics/chat", headers=headers)
    _require_ok(metrics_after, "chat metrics after")
    after_sum = _metric_sum(metrics_after.json(), "chat_requests_total")
    assert after_sum >= before_sum + 1


@pytest.mark.e2e
@pytest.mark.external_api
def test_llm_provider_external_workflow(page, server_url):
    if os.getenv("RUN_COMMERCIAL_CHAT_TESTS", "").lower() not in {"1", "true", "yes", "y", "on"}:
        pytest.skip("Commercial chat tests disabled; set RUN_COMMERCIAL_CHAT_TESTS=1 to enable.")

    headers = _auth_headers()
    providers_resp = page.request.get("/api/v1/llm/providers", headers=headers)
    _require_ok(providers_resp, "list providers")
    providers = providers_resp.json().get("providers", [])

    provider, model = _select_provider(providers, "commercial", AUTO_MOCK_PROVIDERS)
    if not provider:
        pytest.skip("No configured commercial LLM provider available.")
    provider_name = provider["name"]

    provider_resp = page.request.get(f"/api/v1/llm/providers/{provider_name}", headers=headers)
    _require_ok(provider_resp, "provider details")
    assert provider_resp.json().get("name") == provider_name

    metrics_before = page.request.get("/api/v1/metrics/chat", headers=headers)
    _require_ok(metrics_before, "chat metrics before")
    before_sum = _metric_sum(metrics_before.json(), "chat_requests_total")

    completion_resp = page.request.post(
        "/api/v1/chat/completions",
        headers=headers,
        json=_chat_payload(provider_name, model, "Say hello from external provider.", False),
    )
    _require_ok(completion_resp, "chat completion")
    completion_payload = completion_resp.json()
    assert completion_payload.get("choices")

    stream_resp = page.request.post(
        "/api/v1/chat/completions",
        headers=headers,
        json=_chat_payload(provider_name, model, "Stream a short reply.", True),
    )
    _require_ok(stream_resp, "chat completion stream")
    stream_body = stream_resp.text()
    assert "data:" in stream_body or "choices" in stream_body

    metrics_after = page.request.get("/api/v1/metrics/chat", headers=headers)
    _require_ok(metrics_after, "chat metrics after")
    after_sum = _metric_sum(metrics_after.json(), "chat_requests_total")
    assert after_sum >= before_sum + 1
