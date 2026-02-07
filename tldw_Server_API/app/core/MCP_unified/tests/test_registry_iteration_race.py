import asyncio
from typing import Any

import pytest

from tldw_Server_API.app.core.MCP_unified.modules.base import BaseModule, ModuleConfig
from tldw_Server_API.app.core.MCP_unified.modules.registry import ModuleRegistry


class _GateLookupModule(BaseModule):
    gate_enter: asyncio.Event | None = None
    gate_release: asyncio.Event | None = None
    gate_kind: str | None = None

    async def on_initialize(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def check_health(self) -> dict[str, bool]:
        return {"ok": True}

    async def get_tools(self) -> list[dict[str, Any]]:
        return []

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any], context: Any | None = None) -> Any:
        return None

    async def _maybe_gate(self, kind: str) -> None:
        enter = self.__class__.gate_enter
        release = self.__class__.gate_release
        gate_kind = self.__class__.gate_kind
        if gate_kind == kind and enter is not None and release is not None and not enter.is_set():
            enter.set()
            await release.wait()

    async def has_tool(self, tool_name: str) -> bool:
        await self._maybe_gate("tool")
        return False

    async def has_resource(self, uri: str) -> bool:
        await self._maybe_gate("resource")
        return False

    async def has_prompt(self, name: str) -> bool:
        await self._maybe_gate("prompt")
        return False


async def _run_lookup_race(method_name: str, lookup_arg: str) -> None:
    registry = ModuleRegistry()
    await registry.register_module("race_mod_a", _GateLookupModule, ModuleConfig(name="race_mod_a"))
    await registry.register_module("race_mod_b", _GateLookupModule, ModuleConfig(name="race_mod_b"))

    enter = asyncio.Event()
    release = asyncio.Event()
    _GateLookupModule.gate_enter = enter
    _GateLookupModule.gate_release = release
    _GateLookupModule.gate_kind = method_name

    lookup_fn = getattr(registry, f"find_module_for_{method_name}")
    lookup_task = asyncio.create_task(lookup_fn(lookup_arg))

    await asyncio.wait_for(enter.wait(), timeout=2.0)
    await registry.register_module("race_mod_new", _GateLookupModule, ModuleConfig(name="race_mod_new"))
    release.set()

    result = await asyncio.wait_for(lookup_task, timeout=2.0)
    assert result is None

    _GateLookupModule.gate_enter = None
    _GateLookupModule.gate_release = None
    _GateLookupModule.gate_kind = None


@pytest.mark.asyncio
async def test_find_module_for_tool_handles_registry_mutation_during_iteration():
    await _run_lookup_race("tool", "missing_tool")


@pytest.mark.asyncio
async def test_find_module_for_resource_handles_registry_mutation_during_iteration():
    await _run_lookup_race("resource", "missing://resource")


@pytest.mark.asyncio
async def test_find_module_for_prompt_handles_registry_mutation_during_iteration():
    await _run_lookup_race("prompt", "missing_prompt")

