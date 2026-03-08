"""Connector-id based registry for approved SQL backends."""

from __future__ import annotations

from typing import Any


class ConnectorRegistry:
    """Resolve connector IDs to approved connector configuration."""

    def __init__(self, mappings: dict[str, dict[str, Any]]) -> None:
        self._mappings = {key: dict(value) for key, value in mappings.items()}

    def get(self, connector_id: str) -> dict[str, Any]:
        cfg = self._mappings.get(connector_id)
        if cfg is None:
            raise KeyError(f"Unknown connector id: {connector_id}")
        return dict(cfg)
