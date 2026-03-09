"""YAML-based global agent registry for ACP.

Loads agent definitions from Config_Files/agents.yaml and provides
runtime availability detection (binary on PATH, API keys set).
"""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


@dataclass
class AgentRegistryEntry:
    """A single agent entry from the registry."""
    type: str
    name: str
    description: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    requires_api_key: str | None = None
    default: bool = False

    def check_availability(self) -> dict[str, Any]:
        """Check runtime availability of this agent."""
        result: dict[str, Any] = {
            "type": self.type,
            "name": self.name,
            "description": self.description,
        }

        # Check binary
        if self.command:
            which_result = shutil.which(self.command)
            result["binary_found"] = which_result is not None
            if which_result:
                result["binary_path"] = which_result
        else:
            result["binary_found"] = True  # No binary required (e.g., "custom")

        # Check API key
        if self.requires_api_key:
            result["api_key_set"] = bool(os.getenv(self.requires_api_key))
            if not result["api_key_set"]:
                result["missing_api_key"] = self.requires_api_key
        else:
            result["api_key_set"] = True

        # Overall status
        if not result.get("binary_found"):
            result["status"] = "unavailable"
        elif not result.get("api_key_set"):
            result["status"] = "requires_setup"
        else:
            result["status"] = "available"

        result["is_configured"] = result["status"] == "available"
        return result


class AgentRegistry:
    """Loads and caches agent entries from agents.yaml."""

    def __init__(self, yaml_path: str | None = None) -> None:
        if yaml_path is None:
            yaml_path = os.path.join(
                os.path.dirname(__file__),
                "..", "..", "..", "Config_Files", "agents.yaml",
            )
        self._yaml_path = os.path.abspath(yaml_path)
        self._entries: list[AgentRegistryEntry] = []
        self._default_type: str = "custom"
        self._last_load_time: float = 0
        self._last_mtime: float = 0
        self._reload_interval: float = 30.0  # seconds

    def load(self) -> None:
        """Load or reload the registry from YAML."""
        if yaml is None:
            logger.warning("PyYAML not installed — agent registry unavailable")
            self._entries = []
            return

        if not os.path.isfile(self._yaml_path):
            logger.warning("Agent registry file not found: {}", self._yaml_path)
            self._entries = []
            return

        try:
            with open(self._yaml_path, "r") as f:
                data = yaml.safe_load(f)
        except Exception as exc:
            logger.error("Failed to load agent registry: {}", exc)
            return

        if not isinstance(data, dict):
            logger.error("Agent registry is not a valid YAML mapping")
            return

        entries: list[AgentRegistryEntry] = []
        default_type = "custom"

        for item in data.get("agents", []):
            if not isinstance(item, dict):
                continue
            agent_type = item.get("type")
            name = item.get("name")
            if not agent_type or not name:
                continue
            entry = AgentRegistryEntry(
                type=str(agent_type),
                name=str(name),
                description=str(item.get("description", "")),
                command=str(item.get("command", "")),
                args=list(item.get("args", [])),
                env=dict(item.get("env", {})),
                requires_api_key=item.get("requires_api_key"),
                default=bool(item.get("default", False)),
            )
            entries.append(entry)
            if entry.default:
                default_type = entry.type

        self._entries = entries
        self._default_type = default_type
        self._last_load_time = time.time()
        try:
            self._last_mtime = os.path.getmtime(self._yaml_path)
        except OSError:
            pass
        logger.debug("Loaded {} agents from registry", len(entries))

    def _maybe_reload(self) -> None:
        """Reload if the file has changed."""
        now = time.time()
        if now - self._last_load_time < self._reload_interval:
            return
        try:
            current_mtime = os.path.getmtime(self._yaml_path)
        except OSError:
            return
        if current_mtime != self._last_mtime:
            logger.info("Agent registry file changed, reloading")
            self.load()

    @property
    def entries(self) -> list[AgentRegistryEntry]:
        """Get all registry entries, reloading if needed."""
        if not self._entries:
            self.load()
        else:
            self._maybe_reload()
        return list(self._entries)

    @property
    def default_type(self) -> str:
        if not self._entries:
            self.load()
        return self._default_type

    def get_entry(self, agent_type: str) -> AgentRegistryEntry | None:
        """Look up an entry by type."""
        for entry in self.entries:
            if entry.type == agent_type:
                return entry
        return None

    def get_available_agents(self) -> list[dict[str, Any]]:
        """Get all agents with runtime availability info."""
        return [entry.check_availability() for entry in self.entries]


# Module-level singleton
_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
