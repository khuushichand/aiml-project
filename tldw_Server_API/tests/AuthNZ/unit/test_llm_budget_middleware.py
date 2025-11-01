import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


pytestmark = pytest.mark.unit


def _build_app_with_middleware():
    from tldw_Server_API.app.core.AuthNZ.llm_budget_middleware import LLMBudgetMiddleware

    app = FastAPI()

    @app.post("/api/v1/chat/completions")
    def chat_stub():
        return {"ok": True}

    app.add_middleware(LLMBudgetMiddleware)
    return app


@pytest.mark.asyncio
async def test_middleware_virtual_over_budget(monkeypatch):
    import tldw_Server_API.app.core.AuthNZ.llm_budget_middleware as mw

    class StubSettings:
        VIRTUAL_KEYS_ENABLED = True
        LLM_BUDGET_ENFORCE = True

    monkeypatch.setattr(mw, "get_settings", lambda: StubSettings())
    monkeypatch.setattr(mw, "derive_hmac_key_candidates", lambda _s: [b"k"])

    class FakePool:
        async def fetchone(self, *_args, **_kwargs):
            return {"id": 77, "user_id": 88}

    async def fake_get_db_pool():
        return FakePool()

    monkeypatch.setattr(mw, "get_db_pool", fake_get_db_pool)

    async def fake_get_key_limits(_key_id: int):
        return {"is_virtual": True}

    async def fake_is_key_over_budget(_key_id: int):
        return {
            "over": True,
            "reasons": ["day_tokens"],
            "day": {"tokens": 20000, "usd": 10.0},
            "month": {"tokens": 50000, "usd": 50.0},
            "limits": {
                "llm_budget_day_tokens": 10000,
                "llm_budget_day_usd": 5.0,
                "llm_budget_month_tokens": 300000,
                "llm_budget_month_usd": 150.0,
            },
        }

    monkeypatch.setattr(mw, "get_key_limits", fake_get_key_limits)
    monkeypatch.setattr(mw, "is_key_over_budget", fake_is_key_over_budget)

    app = _build_app_with_middleware()
    client = TestClient(app)

    r = client.post(
        "/api/v1/chat/completions",
        headers={"X-API-KEY": "dummy-key"},
        json={"model": "x", "messages": []},
    )

    assert r.status_code == 402
    data = r.json()
    assert data.get("error") == "budget_exceeded"
    assert "Virtual key budget exceeded" in data.get("message", "")
    assert isinstance(data.get("details"), dict)
    assert data["details"].get("over") is True


@pytest.mark.asyncio
async def test_middleware_virtual_under_budget_allows(monkeypatch):
    import tldw_Server_API.app.core.AuthNZ.llm_budget_middleware as mw

    class StubSettings:
        VIRTUAL_KEYS_ENABLED = True
        LLM_BUDGET_ENFORCE = True

    monkeypatch.setattr(mw, "get_settings", lambda: StubSettings())
    monkeypatch.setattr(mw, "derive_hmac_key_candidates", lambda _s: [b"k"])

    class FakePool:
        async def fetchone(self, *_args, **_kwargs):
            return {"id": 77, "user_id": 88}

    async def fake_get_db_pool():
        return FakePool()

    monkeypatch.setattr(mw, "get_db_pool", fake_get_db_pool)

    async def fake_get_key_limits(_key_id: int):
        return {"is_virtual": True}

    async def fake_is_key_over_budget(_key_id: int):
        return {
            "over": False,
            "reasons": [],
            "day": {"tokens": 100, "usd": 0.1},
            "month": {"tokens": 1000, "usd": 1.0},
            "limits": {
                "llm_budget_day_tokens": 10000,
                "llm_budget_day_usd": 5.0,
                "llm_budget_month_tokens": 300000,
                "llm_budget_month_usd": 150.0,
            },
        }

    monkeypatch.setattr(mw, "get_key_limits", fake_get_key_limits)
    monkeypatch.setattr(mw, "is_key_over_budget", fake_is_key_over_budget)

    app = _build_app_with_middleware()
    client = TestClient(app)

    r = client.post(
        "/api/v1/chat/completions",
        headers={"X-API-KEY": "dummy-key"},
        json={"model": "x", "messages": []},
    )

    assert r.status_code == 200
    assert r.json() == {"ok": True}

