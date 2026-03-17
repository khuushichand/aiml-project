"""AdapterFactory -- registry and instantiation of protocol adapters."""
from __future__ import annotations

from typing import Type

from .base import ProtocolAdapter


class AdapterFactory:
    """Simple registry that maps protocol names to adapter classes."""

    def __init__(self) -> None:
        self._registry: dict[str, Type[ProtocolAdapter]] = {}

    def register(self, protocol: str, cls: Type[ProtocolAdapter]) -> None:
        """Register an adapter class under the given protocol name."""
        self._registry[protocol] = cls

    def create(self, protocol: str) -> ProtocolAdapter:
        """Instantiate and return an adapter for *protocol*.

        Raises ``ValueError`` if the protocol is not registered.
        """
        cls = self._registry.get(protocol)
        if cls is None:
            raise ValueError(
                f"Unknown protocol '{protocol}'. "
                f"Available: {sorted(self._registry)}"
            )
        return cls()

    def available_protocols(self) -> list[str]:
        """Return a sorted list of registered protocol names."""
        return sorted(self._registry)
