from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from threading import RLock
from typing import Awaitable, Callable

from loguru import logger

from tldw_Server_API.app.services.shutdown_models import (
    ShutdownComponent,
    ShutdownPhase,
    ShutdownPolicy,
)


_TRANSPORT_CLOSE_GRACE_SECONDS = 1.0


@dataclass(frozen=True)
class TransportFamilySnapshot:
    name: str
    active_count: int
    has_drain_hook: bool


class RegisteredTransportFamily:
    def __init__(
        self,
        *,
        name: str,
        active_count: Callable[[], int],
        drain: Callable[[float | None], Awaitable[None] | None] | None,
    ) -> None:
        self.name = name
        self._active_count = active_count
        self._drain = drain

    def current_active_count(self) -> int:
        try:
            return max(0, int(self._active_count()))
        except Exception:
            return 0

    async def drain(self, timeout_s: float | None = None) -> None:
        if self._drain is None:
            return
        result = self._drain(timeout_s)
        if inspect.isawaitable(result):
            if timeout_s is None:
                await result
            else:
                await asyncio.wait_for(result, timeout=timeout_s)

    def snapshot(self) -> TransportFamilySnapshot:
        return TransportFamilySnapshot(
            name=self.name,
            active_count=self.current_active_count(),
            has_drain_hook=self._drain is not None,
        )


class ShutdownTransportRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._families: dict[str, RegisteredTransportFamily] = {}

    def register_family(
        self,
        name: str,
        *,
        active_count: Callable[[], int],
        drain: Callable[[float | None], Awaitable[None] | None] | None,
    ) -> RegisteredTransportFamily:
        family = RegisteredTransportFamily(name=name, active_count=active_count, drain=drain)
        with self._lock:
            if name in self._families:
                logger.warning(f"Shutdown transport family re-registered; replacing existing entry: {name}")
            self._families[name] = family
        return family

    def unregister_family(self, name: str) -> None:
        with self._lock:
            self._families.pop(name, None)

    def get_family(self, name: str) -> RegisteredTransportFamily | None:
        with self._lock:
            return self._families.get(name)

    def iter_families(self) -> tuple[RegisteredTransportFamily, ...]:
        with self._lock:
            return tuple(self._families.values())

    def snapshot(self) -> tuple[TransportFamilySnapshot, ...]:
        return tuple(family.snapshot() for family in self.iter_families())

    def total_active_sessions(self) -> int:
        return sum(snapshot.active_count for snapshot in self.snapshot())


_shutdown_transport_registry = ShutdownTransportRegistry()


def get_shutdown_transport_registry() -> ShutdownTransportRegistry:
    return _shutdown_transport_registry


def register_shutdown_transport_family(
    name: str,
    *,
    active_count: Callable[[], int],
    drain: Callable[[float | None], Awaitable[None] | None] | None,
) -> RegisteredTransportFamily:
    return _shutdown_transport_registry.register_family(
        name,
        active_count=active_count,
        drain=drain,
    )


def unregister_shutdown_transport_family(name: str) -> None:
    _shutdown_transport_registry.unregister_family(name)


def build_shutdown_components(
    registry: ShutdownTransportRegistry | None = None,
    *,
    phase: ShutdownPhase = ShutdownPhase.ACCEPTORS,
    policy: ShutdownPolicy = ShutdownPolicy.PROD_DRAIN,
    default_timeout_ms: int = int(_TRANSPORT_CLOSE_GRACE_SECONDS * 1000),
) -> list[ShutdownComponent]:
    selected_registry = registry or _shutdown_transport_registry
    components: list[ShutdownComponent] = []
    for family in selected_registry.iter_families():
        components.append(
            ShutdownComponent(
                name=f"transport:{family.name}",
                phase=phase,
                policy=policy,
                default_timeout_ms=default_timeout_ms,
                stop=lambda family=family, timeout_ms=default_timeout_ms: family.drain(
                    timeout_s=max(0.0, timeout_ms / 1000.0),
                ),
            )
        )
    return components
