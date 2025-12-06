import os

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.rate_limit


def _reset_rg_state(app):
    """
    Ensure each test starts with a fresh ResourceGovernor / policy loader.

    Tests in this module mutate RG_POLICY_PATH and related envs; reusing the
    same FastAPI app instance without resetting RG state can cause cross-test
    rate-limit bleed (unexpected 429s). This helper clears governor-related
    attributes so middleware will lazily reinitialize from the current env.
    """
    for attr in ("rg_governor", "rg_policy_loader", "rg_policy_store", "rg_policy_version", "rg_policy_count"):
        try:
            if hasattr(app.state, attr):
                setattr(app.state, attr, None)
        except Exception:
            continue


@pytest.mark.asyncio
async def test_e2e_evaluations_deny_headers_retry_after(monkeypatch, tmp_path):
    # Minimal app with RG middleware; enforce requests-only deny semantics for a
    # representative Evaluations endpoint via route_map.
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("RG_ENABLE_SIMPLE_MIDDLEWARE", "1")
    monkeypatch.setenv("RG_MIDDLEWARE_ENFORCE_TOKENS", "0")
    monkeypatch.setenv("RG_BACKEND", "memory")
    monkeypatch.setenv("RG_POLICY_STORE", "file")

    policy = (
        "version: 1\n"
        "policies:\n"
        "  evals.small:\n"
        "    requests: { rpm: 1 }\n"
        "route_map:\n"
        "  by_path:\n"
        "    /api/v1/evaluations/rate-limits: evals.small\n"
    )
    p = tmp_path / "rg_evals.yaml"
    p.write_text(policy, encoding="utf-8")

    monkeypatch.setenv("RG_POLICY_PATH", str(p))
    monkeypatch.setenv("RG_POLICY_RELOAD_ENABLED", "false")

    # Single-user auth for minimal app
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key")

    from tldw_Server_API.app.main import app

    _reset_rg_state(app)

    with TestClient(app) as client:
        # First request should not be rate-limited by RG; allow non-429 errors
        # from downstream Evaluations plumbing as long as RG does not deny.
        r1 = client.get(
            "/api/v1/evaluations/rate-limits",
            headers={"X-API-KEY": "test-api-key"},
        )
        assert r1.status_code != 429

        # Second request should be governed by RG via route_map.
        r2 = client.get(
            "/api/v1/evaluations/rate-limits",
            headers={"X-API-KEY": "test-api-key"},
        )

    assert r2.status_code in (429, 503)
    if r2.status_code == 429:
        retry_after = r2.headers.get("Retry-After")
        assert retry_after is not None
        assert r2.headers.get("X-RateLimit-Limit") == "1"
        assert r2.headers.get("X-RateLimit-Remaining") == "0"
        reset = r2.headers.get("X-RateLimit-Reset")
        assert reset is not None and int(reset) >= 1


@pytest.mark.asyncio
async def test_e2e_authnz_debug_deny_headers_retry_after(monkeypatch, tmp_path):
    # Minimal app with RG middleware; enforce requests-only deny semantics for a
    # lightweight AuthNZ debug endpoint that does not require full login flow.
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("RG_ENABLE_SIMPLE_MIDDLEWARE", "1")
    monkeypatch.setenv("RG_MIDDLEWARE_ENFORCE_TOKENS", "0")
    monkeypatch.setenv("RG_BACKEND", "memory")
    monkeypatch.setenv("RG_POLICY_STORE", "file")

    policy = (
        "version: 1\n"
        "policies:\n"
        "  authnz.small:\n"
        "    requests: { rpm: 1 }\n"
        "route_map:\n"
        "  by_path:\n"
        "    /api/v1/authnz/debug/api-key-id: authnz.small\n"
    )
    p = tmp_path / "rg_authnz.yaml"
    p.write_text(policy, encoding="utf-8")

    monkeypatch.setenv("RG_POLICY_PATH", str(p))
    monkeypatch.setenv("RG_POLICY_RELOAD_ENABLED", "false")

    # Auth mode does not matter for this debug route, but keep a predictable
    # configuration for consistency with other RG tests.
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key")

    # Stub out heavy AuthNZ budget helpers so the debug endpoint does not hit DBs.
    import tldw_Server_API.app.api.v1.endpoints.authnz_debug as authnz_debug_ep

    async def _fake_resolve_api_key(api_key: str):
        _ = api_key
        return None

    async def _fake_get_key_limits(key_id: int):
        _ = key_id
        return {}

    async def _fake_summarize_usage_for_key_day(key_id: int):
        _ = key_id
        return {}

    async def _fake_summarize_usage_for_key_month(key_id: int):
        _ = key_id
        return {}

    async def _fake_is_key_over_budget(key_id: int):
        _ = key_id
        return {"over": False, "reasons": []}

    monkeypatch.setattr(authnz_debug_ep, "resolve_api_key_by_hash", _fake_resolve_api_key)
    monkeypatch.setattr(authnz_debug_ep, "get_key_limits", _fake_get_key_limits)
    monkeypatch.setattr(authnz_debug_ep, "summarize_usage_for_key_day", _fake_summarize_usage_for_key_day)
    monkeypatch.setattr(authnz_debug_ep, "summarize_usage_for_key_month", _fake_summarize_usage_for_key_month)
    monkeypatch.setattr(authnz_debug_ep, "is_key_over_budget", _fake_is_key_over_budget)

    from tldw_Server_API.app.main import app

    _reset_rg_state(app)

    with TestClient(app) as client:
        r1 = client.get("/api/v1/authnz/debug/api-key-id")
        assert r1.status_code != 429

        r2 = client.get("/api/v1/authnz/debug/api-key-id")

    assert r2.status_code in (429, 503)
    if r2.status_code == 429:
        retry_after = r2.headers.get("Retry-After")
        assert retry_after is not None
        assert r2.headers.get("X-RateLimit-Limit") == "1"
        assert r2.headers.get("X-RateLimit-Remaining") == "0"
        reset = r2.headers.get("X-RateLimit-Reset")
        assert reset is not None and int(reset) >= 1


@pytest.mark.asyncio
async def test_e2e_character_chat_deny_headers_retry_after(monkeypatch, tmp_path):
    # Minimal app with RG middleware; enforce requests-only deny semantics for
    # the legacy character chat completion endpoint used in tests.
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("RG_ENABLE_SIMPLE_MIDDLEWARE", "1")
    monkeypatch.setenv("RG_MIDDLEWARE_ENFORCE_TOKENS", "0")
    monkeypatch.setenv("RG_BACKEND", "memory")
    monkeypatch.setenv("RG_POLICY_STORE", "file")

    policy = (
        "version: 1\n"
        "policies:\n"
        "  character.small:\n"
        "    requests: { rpm: 1 }\n"
        "route_map:\n"
        "  by_path:\n"
        "    /api/v1/chats/*: character.small\n"
    )
    p = tmp_path / "rg_character.yaml"
    p.write_text(policy, encoding="utf-8")

    monkeypatch.setenv("RG_POLICY_PATH", str(p))
    monkeypatch.setenv("RG_POLICY_RELOAD_ENABLED", "false")

    # Single-user auth for minimal app; character chat sessions depend on
    # get_request_user which uses this configuration.
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key")

    from tldw_Server_API.app.main import app

    _reset_rg_state(app)

    # Override ChaCha DB dependency with a lightweight stub so the endpoint does
    # not touch the real database layer.
    from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user

    class _StubChaChaDB:
        def get_conversation_by_id(self, chat_id: str):
            # Provide a minimal conversation owned by user id 1 so the endpoint
            # proceeds past ownership checks.
            return {"id": chat_id, "client_id": "1"}

    async def _stub_get_db(current_user=None):  # noqa: ARG001
        return _StubChaChaDB()

    app.dependency_overrides[get_chacha_db_for_user] = _stub_get_db

    try:
        with TestClient(app) as client:
            chat_id = "rg-e2e-chat"
            url = f"/api/v1/chats/{chat_id}/complete"

            # First request should not be rate-limited by RG; allow downstream
            # errors as long as RG does not immediately return 429.
            r1 = client.post(url, headers={"X-API-KEY": "test-api-key"})
            assert r1.status_code != 429

            # Second request should be governed by RG policy via middleware.
            r2 = client.post(url, headers={"X-API-KEY": "test-api-key"})
    finally:
        app.dependency_overrides.pop(get_chacha_db_for_user, None)

    assert r2.status_code in (429, 503)
    if r2.status_code == 429:
        retry_after = r2.headers.get("Retry-After")
        assert retry_after is not None
        assert r2.headers.get("X-RateLimit-Limit") == "1"
        assert r2.headers.get("X-RateLimit-Remaining") == "0"
        reset = r2.headers.get("X-RateLimit-Reset")
        assert reset is not None and int(reset) >= 1

