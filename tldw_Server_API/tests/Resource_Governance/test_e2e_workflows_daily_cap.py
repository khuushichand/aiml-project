import json

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.rate_limit


def _reset_rg_state(app):
    for attr in ("rg_governor", "rg_policy_loader", "rg_policy_store", "rg_policy_version", "rg_policy_count"):
        try:
            if hasattr(app.state, attr):
                setattr(app.state, attr, None)
        except Exception:
            continue


async def _init_authnz_sqlite(db_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    try:
        from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
        from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

        await reset_db_pool()
        reset_settings()
    except Exception:
        pass
    try:
        from tldw_Server_API.app.core.AuthNZ.initialize import ensure_authnz_schema_ready_once

        await ensure_authnz_schema_ready_once()
    except Exception:
        pass


@pytest.mark.asyncio
async def test_e2e_workflows_daily_cap_denies_with_headers(monkeypatch, tmp_path):
    # Ensure ledger is available for enforcement.
    db_path = tmp_path / "authnz_wf_e2e.db"
    await _init_authnz_sqlite(db_path, monkeypatch)

    # Create a fresh user + API key so legacy workflow runs do not affect the cap.
    from uuid import uuid4
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager

    pool = await get_db_pool()
    users_db = UsersDB(pool)
    await users_db.initialize()
    created_user = await users_db.create_user(
        username="wf-cap-user",
        email="wf-cap-user@example.com",
        password_hash="x",
        role="user",
        is_active=True,
        is_superuser=False,
        storage_quota_mb=5120,
        uuid_value=uuid4(),
    )
    user_id = int(created_user["id"])
    mgr = APIKeyManager(pool)
    await mgr.initialize()
    key_rec = await mgr.create_api_key(user_id=user_id, name="wf-cap-key")
    api_key = key_rec["key"]

    # Isolate workflows content DB under a temporary user DB base dir so legacy
    # counts/backfill do not pick up runs from other tests.
    user_db_base = tmp_path / "user_dbs"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(user_db_base))

    # Minimal app + RG middleware.
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("RG_ENABLE_SIMPLE_MIDDLEWARE", "1")
    monkeypatch.setenv("RG_BACKEND", "memory")
    monkeypatch.setenv("RG_POLICY_STORE", "file")
    monkeypatch.setenv("RG_POLICY_RELOAD_ENABLED", "false")

    # Auth is multi-user (API key) and test-mode stability.
    monkeypatch.setenv("TEST_MODE", "true")

    from tldw_Server_API.app.main import app

    _reset_rg_state(app)
    try:
        import configparser
        from tldw_Server_API.app.core.DB_Management.DB_Manager import reset_content_backend

        cfg = configparser.ConfigParser()
        cfg["Database"] = {
            "type": "sqlite",
            "workflows_path": str(tmp_path / "workflows.db"),
        }
        reset_content_backend(config=cfg, reload=False)
    except Exception:
        pass

    policy = (
        "schema_version: 1\n"
        "policies:\n"
        "  workflows.small:\n"
        "    requests: { rpm: 100000, burst: 1.0 }\n"
        "    workflows_runs: { daily_cap: 1 }\n"
        "    scopes: [user]\n"
        "route_map:\n"
        "  by_path:\n"
        "    \"/api/v1/workflows/*\": workflows.small\n"
    )
    p = tmp_path / "rg_workflows.yaml"
    p.write_text(policy, encoding="utf-8")
    monkeypatch.setenv("RG_POLICY_PATH", str(p))

    body = {
        "definition": {
            "name": "wf-small",
            "version": 1,
            "steps": [{"id": "log", "type": "log", "config": {"message": "hi"}}],
        },
        "inputs": {},
    }

    with TestClient(app) as c:
        r1 = c.post(
            "/api/v1/workflows/run",
            headers={"X-API-KEY": api_key},
            data=json.dumps(body),
        )
        assert r1.status_code == 200

        r2 = c.post(
            "/api/v1/workflows/run",
            headers={"X-API-KEY": api_key},
            data=json.dumps(body),
        )
        assert r2.status_code == 429
        assert r2.headers.get("X-RateLimit-Limit") == "1"
        assert r2.headers.get("X-RateLimit-Remaining") == "0"
        assert r2.headers.get("Retry-After") is not None
