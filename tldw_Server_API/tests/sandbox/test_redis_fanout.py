import asyncio
import os
import types
import uuid
from queue import Queue

import pytest


class _Bus:
    channels: dict[str, list["FakePubSub"]] = {}

    @classmethod
    def publish(cls, channel: str, data: bytes) -> None:
        subs = list(cls.channels.get(channel, []))
        for sub in subs:
            try:
                sub._q.put({"type": "message", "data": data})
            except Exception:
                continue


class FakePubSub:
    def __init__(self):
             self._subs = set()
        self._q: Queue = Queue()

    def subscribe(self, channel: str) -> None:
        _Bus.channels.setdefault(channel, []).append(self)
        self._subs.add(channel)

    def listen(self):  # generator
        while True:
            msg = self._q.get()
            if msg is None:
                break
            yield msg


class FakeRedis:
    @classmethod
    def from_url(cls, url: str):
        return cls()

    def ping(self):

             return True

    def publish(self, channel: str, data: bytes):
        _Bus.publish(channel, data)

    def pubsub(self, ignore_subscribe_messages: bool = True):
        return FakePubSub()


@pytest.mark.asyncio
async def test_redis_fanout_cross_worker(monkeypatch):
    # Enable fanout and use a unique channel
    chan = f"test:sandbox:{uuid.uuid4().hex}"
    monkeypatch.setenv("SANDBOX_WS_REDIS_FANOUT", "true")
    monkeypatch.setenv("SANDBOX_REDIS_URL", "redis://fake")
    monkeypatch.setenv("SANDBOX_WS_REDIS_CHANNEL", chan)

    # Inject fake redis module
    fake_mod = types.SimpleNamespace(Redis=FakeRedis)
    monkeypatch.setitem(__import__("sys").modules, "redis", fake_mod)

    # Import hub class after monkeypatch
    from tldw_Server_API.app.core.Sandbox.streams import RunStreamHub

    h1 = RunStreamHub()
    h2 = RunStreamHub()
    # Ensure hub2 is tied to this test loop for delivery
    loop = asyncio.get_running_loop()
    h2.set_loop(loop)
    run_id = "rid-redis-fanout"
    q = h2.subscribe_with_buffer(run_id)

    # Publish from hub1 and expect to receive on hub2 via Redis fanout
    h1.publish_stdout(run_id, b"hello", max_log_bytes=1024)

    frame = await asyncio.wait_for(q.get(), timeout=1.5)
    assert frame["type"] == "stdout"
    assert frame["encoding"] in {"utf8", "base64"}
    if frame["encoding"] == "utf8":
        assert frame["data"] == "hello"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_redis_fanout_cross_worker_real(monkeypatch):
    # Use a real Redis instance if available (SANDBOX_TEST_REDIS_URL or REDIS_URL or localhost)
    try:
        import redis  # type: ignore
    except Exception:
        pytest.skip("redis library not installed")
    url = os.getenv("SANDBOX_TEST_REDIS_URL") or os.getenv("REDIS_URL") or "redis://127.0.0.1:6379/0"
    try:
        client = redis.Redis.from_url(url)
        client.ping()
    except Exception:
        pytest.skip("Real Redis not available")

    chan = f"test:sandbox:{uuid.uuid4().hex}"
    monkeypatch.setenv("SANDBOX_WS_REDIS_FANOUT", "true")
    monkeypatch.setenv("SANDBOX_REDIS_URL", url)
    monkeypatch.setenv("SANDBOX_WS_REDIS_CHANNEL", chan)

    from tldw_Server_API.app.core.Sandbox.streams import RunStreamHub

    h1 = RunStreamHub()
    h2 = RunStreamHub()
    loop = asyncio.get_running_loop()
    h2.set_loop(loop)
    run_id = f"rid-real-{uuid.uuid4().hex}"
    q = h2.subscribe_with_buffer(run_id)

    # Allow time for the background subscriber to subscribe to the channel
    await asyncio.sleep(0.05)
    h1.publish_stdout(run_id, b"ping", max_log_bytes=1024)

    frame = await asyncio.wait_for(q.get(), timeout=3.0)
    assert frame["type"] == "stdout"
    assert frame["encoding"] in {"utf8", "base64"}
    if frame["encoding"] == "utf8":
        assert frame["data"] == "ping"

def test_health_includes_redis_ping(monkeypatch):

     # Setup app with sandbox routes and fake redis
    monkeypatch.setenv("TEST_MODE", "1")
    chan = f"test:sandbox:health:{uuid.uuid4().hex}"
    monkeypatch.setenv("SANDBOX_WS_REDIS_FANOUT", "true")
    monkeypatch.setenv("SANDBOX_REDIS_URL", "redis://fake")
    monkeypatch.setenv("SANDBOX_WS_REDIS_CHANNEL", chan)
    fake_mod = types.SimpleNamespace(Redis=FakeRedis)
    monkeypatch.setitem(__import__("sys").modules, "redis", fake_mod)

    import importlib
    if "tldw_Server_API.app.main" in importlib.sys.modules:
        importlib.reload(importlib.sys.modules["tldw_Server_API.app.main"])  # type: ignore[arg-type]
    main = importlib.import_module("tldw_Server_API.app.main")
    app = getattr(main, "app")
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        r = client.get("/api/v1/sandbox/health")
        assert r.status_code == 200
        data = r.json()
        assert "redis" in data
        assert data["redis"].get("enabled") is True
        assert data["redis"].get("connected") is True
        # Should include ping_ms when connected
        assert "ping_ms" in data["redis"]
