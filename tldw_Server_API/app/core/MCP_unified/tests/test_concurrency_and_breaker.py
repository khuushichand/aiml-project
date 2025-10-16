import asyncio
import pytest
from typing import Dict, Any

from tldw_Server_API.app.core.MCP_unified.modules.base import BaseModule, ModuleConfig


class SlowModule(BaseModule):
    def __init__(self, config: ModuleConfig):
        super().__init__(config)
        self.current = 0
        self.max_seen = 0

    async def on_initialize(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def check_health(self) -> Dict[str, bool]:
        return {"ok": True}

    async def get_tools(self) -> list[dict]:
        return []

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context=None):
        return None

    async def _work(self, delay: float):
        self.current += 1
        self.max_seen = max(self.max_seen, self.current)
        try:
            await asyncio.sleep(delay)
        finally:
            self.current -= 1
        return "done"


@pytest.mark.asyncio
async def test_per_module_concurrency_guard_limits_parallelism():
    # Allow only 2 concurrent ops
    mod = SlowModule(ModuleConfig(name="slow", max_concurrent=2))

    async def call_once():
        return await mod.execute_with_circuit_breaker(mod._work, 0.05)

    # Schedule 5 parallel calls
    tasks = [asyncio.create_task(call_once()) for _ in range(5)]
    await asyncio.gather(*tasks)

    # Ensure observed concurrency was limited to 2
    assert mod.max_seen <= 2


class FlappyModule(BaseModule):
    def __init__(self, config: ModuleConfig):
        super().__init__(config)
        self.calls = 0

    async def on_initialize(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def check_health(self) -> Dict[str, bool]:
        return {"ok": True}

    async def get_tools(self) -> list[dict]:
        return []

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context=None):
        return None

    async def _always_fail(self):
        self.calls += 1
        raise RuntimeError("fail")


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_with_backoff_behaves():
    # Threshold=1, initial timeout=0s: immediate half-open on next call; backoff should extend
    mod = FlappyModule(ModuleConfig(
        name="flappy",
        circuit_breaker_threshold=1,
        circuit_breaker_timeout=0,
        circuit_breaker_backoff_factor=2.0,
        circuit_breaker_max_timeout=2,
    ))

    # First failure -> open (for 0s effective), next call becomes half-open
    with pytest.raises(Exception):
        await mod.execute_with_circuit_breaker(mod._always_fail)
    # Next attempt should enter half-open (is_circuit_breaker_open returns False)
    assert mod.is_circuit_breaker_open() is False

    # Fail again in half-open -> re-open with backoff (>0s)
    with pytest.raises(Exception):
        await mod.execute_with_circuit_breaker(mod._always_fail)

    assert mod._circuit_breaker_half_open is False
    # Now breaker should be open for some time
    assert mod.is_circuit_breaker_open() is True
