from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import RuntimeType


@dataclass
class RuntimeCapabilities:
    """Capability flags advertised by a sandbox runtime provider."""

    supports_strict_deny_all: bool = False
    supports_strict_allowlist: bool = False
    supports_interactive: bool = False
    supports_port_mappings: bool = False
    supports_acp_session_mode: bool = False


@dataclass
class RuntimePreflightResult:
    """Host/runtime preflight status used by policy admission."""

    runtime: RuntimeType
    available: bool
    reasons: list[str] = field(default_factory=list)
    host: dict[str, Any] = field(default_factory=dict)
    enforcement_ready: dict[str, bool] = field(
        default_factory=lambda: {"deny_all": False, "allowlist": False}
    )

