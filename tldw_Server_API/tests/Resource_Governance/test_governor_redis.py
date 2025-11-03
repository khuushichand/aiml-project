import pytest
pytestmark = pytest.mark.rate_limit

from tldw_Server_API.app.core.Resource_Governance import RedisResourceGovernor, RGRequest


class FakeTime:
    def __init__(self, t0: float = 0.0):
        self.t = t0

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


@pytest.mark.asyncio
async def test_requests_sliding_window_with_stub_redis():
    # Policies loader stub with simple get_policy
    class _Loader:
        def get_policy(self, pid):
            return {"requests": {"rpm": 2}, "scopes": ["global", "user"]}

    ft = FakeTime(0.0)
    ns = "rg_t_reqsliding"
    rg = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft, ns=ns)
    # Ensure clean keys for this policy/category
    client = await rg._client_get()
    # Aggressive cleanup for this policy id across categories
    try:
        for pat in (f"{ns}:win:p:requests*", f"{ns}:win:p:*", f"{ns}:lease:p:*"):
            _cur, keys = await client.scan(match=pat)
            for k in keys:
                await client.delete(k)
    except Exception:
        pass
    e = "user:1"
    req = RGRequest(entity=e, categories={"requests": {"units": 1}}, tags={"policy_id": "p"})

    d1, h1 = await rg.reserve(req, op_id="r1")
    assert d1.allowed and h1
    d2, h2 = await rg.reserve(req, op_id="r2")
    assert d2.allowed and h2

    d3, h3 = await rg.reserve(req, op_id="r3")
    assert not d3.allowed and h3 is None

    # Advance window → should allow again
    ft.advance(60.0)
    d4, h4 = await rg.reserve(req, op_id="r4")
    assert d4.allowed and h4


@pytest.mark.asyncio
async def test_tokens_lua_script_retry_after():
    class _Loader:
        def get_policy(self, pid):
            return {"tokens": {"per_min": 2, "burst": 1.0}, "scopes": ["global", "user"]}

    ft = FakeTime(0.0)
    ns = "rg_t_tokens"
    rg = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft, ns=ns)
    # Clean token keys for this test's policy id
    client = await rg._client_get()
    try:
        for pat in (f"{ns}:win:ptok:tokens*", f"{ns}:win:ptok:*"):
            _cur, keys = await client.scan(match=pat)
            for k in keys:
                await client.delete(k)
    except Exception:
        pass
    e = "user:tok"
    req = RGRequest(entity=e, categories={"tokens": {"units": 1}}, tags={"policy_id": "ptok"})

    d1, _ = await rg.reserve(req)
    assert d1.allowed
    d2, _ = await rg.reserve(req)
    assert d2.allowed

    d3, _ = await rg.reserve(req)
    assert not d3.allowed
    assert d3.retry_after is not None and int(d3.retry_after) >= 60

    ft.advance(30.0)
    d4, _ = await rg.reserve(req)
    assert not d4.allowed
    assert d4.retry_after is not None and 25 <= int(d4.retry_after) <= 60

    ft.advance(31.0)
    d5, _ = await rg.reserve(req)
    assert d5.allowed


@pytest.mark.asyncio
async def test_concurrency_leases_with_zrem_capability():
    class _Loader:
        def get_policy(self, pid):
            return {"streams": {"max_concurrent": 1, "ttl_sec": 60}, "scopes": ["global", "user"]}

    ft = FakeTime(0.0)
    ns = "rg_t_conc"
    rg = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft, ns=ns)
    client = await rg._client_get()
    # Clean any prior leases
    try:
        for pat in (f"{ns}:lease:pcon:streams*", f"{ns}:lease:pcon:*"):
            _cur, keys = await client.scan(match=pat)
            for k in keys:
                await client.delete(k)
    except Exception:
        pass
    if not hasattr(client, "zrem"):
        pytest.skip("Redis client lacks zrem; skipping precise lease deletion test")

    e = "user:lease"
    req = RGRequest(entity=e, categories={"streams": {"units": 1}}, tags={"policy_id": "pcon"})

    d1, h1 = await rg.reserve(req)
    assert d1.allowed and h1

    d2, h2 = await rg.reserve(req)
    assert not d2.allowed and h2 is None

    # Commit should release just this handle's leases via ZREM
    await rg.commit(h1)

    d3, h3 = await rg.reserve(req)
    assert d3.allowed and h3


@pytest.mark.asyncio
async def test_per_category_fail_mode_override_on_error(monkeypatch):
    class _Loader:
        def get_policy(self, pid):
            return {"tokens": {"per_min": 1, "fail_mode": "fail_open"}, "scopes": ["global", "user"]}

    ft = FakeTime(0.0)
    ns = "rg_t_burst"
    rg = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft, ns=ns)
    # Clean request keys for this test's policy id
    client = await rg._client_get()
    try:
        for pat in (f"{ns}:win:p:requests*", f"{ns}:win:p:*"):
            _cur, keys = await client.scan(match=pat)
            for k in keys:
                await client.delete(k)
    except Exception:
        pass

    # Force client methods to raise to trigger fail_mode path
    class _Broken:
        async def evalsha(self, *a, **k):
            raise RuntimeError("boom")
        async def script_load(self, *a, **k):
            raise RuntimeError("boom")

    async def _broken_client():
        return _Broken()

    monkeypatch.setattr(rg, "_client_get", _broken_client)

    req = RGRequest(entity="user:x", categories={"tokens": {"units": 1}}, tags={"policy_id": "p"})
    d, _ = await rg.reserve(req)
    assert d.allowed  # allowed due to per-category fail_open


@pytest.mark.asyncio
async def test_requests_burst_and_retry_after_behavior():
    class _Loader:
        def get_policy(self, pid):
            return {"requests": {"rpm": 5}, "scopes": ["global", "user"]}

    ft = FakeTime(0.0)
    ns = "rg_t_burst2"
    rg = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft, ns=ns)
    # Clean keys for this policy id
    client = await rg._client_get()
    try:
        for pat in (f"{ns}:win:pburst:requests*", f"{ns}:win:pburst:*"):
            _cur, keys = await client.scan(match=pat)
            for k in keys:
                await client.delete(k)
    except Exception:
        pass
    e = "user:burst"
    req = RGRequest(entity=e, categories={"requests": {"units": 1}}, tags={"policy_id": "pburst"})

    # 5 quick requests allowed
    for i in range(5):
        d, h = await rg.reserve(req, op_id=f"b{i}")
        assert d.allowed and h

    # 6th denied with a retry_after
    d6, h6 = await rg.reserve(req, op_id="b6")
    assert not d6.allowed and h6 is None
    assert d6.retry_after is not None and int(d6.retry_after) > 0

    # Advance just shy of full window: still denied
    ft.advance(max(1, int(d6.retry_after or 60) - 1))
    d7, _ = await rg.reserve(req)
    assert not d7.allowed

    # Advance past the window: allowed again
    ft.advance(2.0)
    d8, h8 = await rg.reserve(req)
    assert d8.allowed and h8


@pytest.mark.asyncio
async def test_requests_steady_rate_no_denials():
    class _Loader:
        def get_policy(self, pid):
            # 6 rpm → one every 10s should always pass
            return {"requests": {"rpm": 6}, "scopes": ["global", "user"]}

    ft = FakeTime(0.0)
    ns = "rg_t_steady2"
    rg = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft, ns=ns)
    # Clean request keys for this test's policy id
    client = await rg._client_get()
    try:
        for pat in (f"{ns}:win:psteady:requests*", f"{ns}:win:psteady:*"):
            _cur, keys = await client.scan(match=pat)
            for k in keys:
                await client.delete(k)
    except Exception:
        pass
    e = "user:steady"
    req = RGRequest(entity=e, categories={"requests": {"units": 1}}, tags={"policy_id": "psteady"})

    allowed = 0
    for i in range(12):
        d, h = await rg.reserve(req, op_id=f"s{i}")
        assert d.allowed and h
        allowed += 1
        # Advance 10 seconds between calls
        ft.advance(10.0)

    assert allowed == 12
