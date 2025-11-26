import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Resource_Governance import MemoryResourceGovernor
from tldw_Server_API.app.core.Resource_Governance.policy_loader import PolicyLoader, PolicyReloadConfig


pytestmark = pytest.mark.rate_limit


@pytest.mark.asyncio
async def test_diag_peek_with_policy_id(monkeypatch, tmp_path):
    # Run app in minimal mode and single_user to bypass heavy AuthNZ
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    # Use deterministic single-user API key for auth
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key-1234567890")

    # Minimal policy file (not strictly required for this test)
    yaml_path = tmp_path / "rg.yaml"
    yaml_path.write_text(
        (
            "version: 1\n"
            "policies:\n"
            "  chat.default:\n"
            "    requests: { rpm: 2 }\n"
            "    tokens: { per_min: 5 }\n"
            "    scopes: [user]\n"
        ),
        encoding="utf-8",
    )
    loader = PolicyLoader(str(yaml_path), PolicyReloadConfig(enabled=False))
    await loader.load_once()

    pols = {"chat.default": {"requests": {"rpm": 2}, "tokens": {"per_min": 5}, "scopes": ["user"]}}
    gov = MemoryResourceGovernor(policies=pols)

    from tldw_Server_API.app.main import app as main_app
    # Attach governor (loader not required for peek_with_policy here)
    main_app.state.rg_governor = gov

    with TestClient(main_app) as c:
        r = c.get(
            "/api/v1/resource-governor/diag/peek",
            params={"entity": "user:diag", "categories": "requests,tokens", "policy_id": "chat.default"},
            headers={"X-API-KEY": "test-api-key-1234567890"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        d = data.get("data") or {}
        assert "requests" in d and "tokens" in d
