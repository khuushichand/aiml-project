import asyncio
import pytest
from loguru import logger

# Mark as unit to integrate with suite filters
pytestmark = pytest.mark.unit


class RaisingState:
    def __setattr__(self, name, value):  # pragma: no cover - simple trigger
        raise RuntimeError("intentional state failure")


class DummyRequest:
    def __init__(self):
        # Headers mimic API key header presence
        self.headers = {"X-API-KEY": "dummy-key"}
        # Simulate request path for logging context
        self.scope = {"path": "/unit/llm-guard"}
        # A state object that raises on any attribute assignment
        self.state = RaisingState()


@pytest.mark.asyncio
async def test_enforce_llm_budget_logs_and_raises_on_state_failure(monkeypatch):
    # Import inside test to ensure monkeypatch targets the loaded module
    from tldw_Server_API.app.core.AuthNZ import llm_budget_guard as guard

    # Stub settings to enable the guard and budget enforcement
    class StubSettings:
        VIRTUAL_KEYS_ENABLED = True
        LLM_BUDGET_ENFORCE = True

    monkeypatch.setattr(guard, "get_settings", lambda: StubSettings())

    # Make HMAC key candidates deterministic
    monkeypatch.setattr(guard, "derive_hmac_key_candidates", lambda _s: [b"k"])

    # Fake DB pool that always finds a matching key row
    class FakePool:
        async def fetchone(self, *_args, **_kwargs):
            return {"id": 123, "user_id": 456}

    async def fake_get_db_pool():
        return FakePool()

    monkeypatch.setattr(guard, "get_db_pool", fake_get_db_pool)

    # Capture loguru error/exception output
    logs = []

    def sink(message):
        logs.append(message)

    sink_id = logger.add(sink, level="ERROR")
    try:
        req = DummyRequest()
        with pytest.raises(guard.HTTPException) as ei:
            await guard.enforce_llm_budget(req)

        assert ei.value.status_code == 500
        # Ensure an error/exception message was emitted with our marker text
        assert any(
            "failed to set request.state attributes" in (m.record.get("message") or "") for m in logs
        ), "expected error log not captured"
    finally:
        logger.remove(sink_id)


@pytest.mark.asyncio
async def test_enforce_llm_budget_error_payload_shape(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import llm_budget_guard as guard

    class StubSettings:
        VIRTUAL_KEYS_ENABLED = True
        LLM_BUDGET_ENFORCE = True

    monkeypatch.setattr(guard, "get_settings", lambda: StubSettings())
    monkeypatch.setattr(guard, "derive_hmac_key_candidates", lambda _s: [b"k"])

    class FakePool:
        async def fetchone(self, *_args, **_kwargs):
            return {"id": 42, "user_id": 7}

    async def fake_get_db_pool():
        return FakePool()

    monkeypatch.setattr(guard, "get_db_pool", fake_get_db_pool)

    # Use the RaisingState again to trigger the error path
    req = DummyRequest()
    with pytest.raises(guard.HTTPException) as ei:
        await guard.enforce_llm_budget(req)

    assert ei.value.status_code == 500
    detail = ei.value.detail
    assert isinstance(detail, dict)
    assert detail.get("error") == "internal_state_error"
    assert "Failed to attach authorization context" in detail.get("message", "")
    assert isinstance(detail.get("details"), dict)
    assert detail["details"].get("path") == "/unit/llm-guard"
    assert detail["details"].get("attributes") == ["api_key_id", "user_id"]


@pytest.mark.asyncio
async def test_enforce_llm_budget_happy_path(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import llm_budget_guard as guard

    class StubSettings:
        VIRTUAL_KEYS_ENABLED = True
        LLM_BUDGET_ENFORCE = True

    monkeypatch.setattr(guard, "get_settings", lambda: StubSettings())
    monkeypatch.setattr(guard, "derive_hmac_key_candidates", lambda _s: [b"k"])

    class FakePool:
        async def fetchone(self, *_args, **_kwargs):
            return {"id": 555, "user_id": 999}

    async def fake_get_db_pool():
        return FakePool()

    monkeypatch.setattr(guard, "get_db_pool", fake_get_db_pool)

    # Make the key non-virtual to early-return without budget checks
    async def fake_get_key_limits(_key_id: int):
        return {"is_virtual": False}

    monkeypatch.setattr(guard, "get_key_limits", fake_get_key_limits)

    class NormalState:
        pass

    class OkRequest:
        def __init__(self):
            self.headers = {"X-API-KEY": "dummy-key"}
            self.scope = {"path": "/unit/ok"}
            self.state = NormalState()

    req = OkRequest()
    # Should not raise
    await guard.enforce_llm_budget(req)
    # State attributes should be set
    assert getattr(req.state, "api_key_id", None) == 555
    assert getattr(req.state, "user_id", None) == 999


@pytest.mark.asyncio
async def test_enforce_llm_budget_virtual_under_budget_ok(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import llm_budget_guard as guard

    class StubSettings:
        VIRTUAL_KEYS_ENABLED = True
        LLM_BUDGET_ENFORCE = True

    monkeypatch.setattr(guard, "get_settings", lambda: StubSettings())
    monkeypatch.setattr(guard, "derive_hmac_key_candidates", lambda _s: [b"k"])

    class FakePool:
        async def fetchone(self, *_args, **_kwargs):
            return {"id": 111, "user_id": 222}

    async def fake_get_db_pool():
        return FakePool()

    monkeypatch.setattr(guard, "get_db_pool", fake_get_db_pool)

    # Virtual key with limits, but not over budget
    async def fake_get_key_limits(_key_id: int):
        return {"is_virtual": True, "llm_budget_day_tokens": 10000}

    called = {"over_budget": False}

    async def fake_is_key_over_budget(_key_id: int):
        called["over_budget"] = True
        return {
            "over": False,
            "reasons": [],
            "day": {"tokens": 100, "usd": 0.10},
            "month": {"tokens": 500, "usd": 0.50},
            "limits": {
                "llm_budget_day_tokens": 10000,
                "llm_budget_day_usd": 5.0,
                "llm_budget_month_tokens": 300000,
                "llm_budget_month_usd": 150.0,
            },
        }

    monkeypatch.setattr(guard, "get_key_limits", fake_get_key_limits)
    monkeypatch.setattr(guard, "is_key_over_budget", fake_is_key_over_budget)

    class NormalState:
        pass

    class OkRequest:
        def __init__(self):
            self.headers = {"X-API-KEY": "dummy-key"}
            self.scope = {"path": "/unit/ok-virtual"}
            self.state = NormalState()

    req = OkRequest()
    # Should not raise; budget is under limits
    await guard.enforce_llm_budget(req)
    assert getattr(req.state, "api_key_id", None) == 111
    assert getattr(req.state, "user_id", None) == 222
    # Ensure the budget checker was invoked
    assert called["over_budget"] is True
