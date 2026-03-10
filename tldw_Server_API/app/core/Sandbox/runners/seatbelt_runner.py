from __future__ import annotations

import os
import sys
from datetime import datetime

from loguru import logger

from tldw_Server_API.app.core.testing import is_truthy

from ..models import RunPhase, RunSpec, RunStatus, RuntimeType
from ..runtime_capabilities import RuntimePreflightResult
from ..streams import get_hub
from .vz_common import vz_host_facts


def _truthy(value: str | None) -> bool:
    return is_truthy(value)


class SeatbeltRunner:
    """Host-local macOS runner for seatbelt-scoped trusted workloads.

    This runner only supports discovery and a fake execution path today.
    `untrusted` is never allowed, `standard` requires explicit opt-in, and real
    seatbelt execution is still pending.
    """

    runtime_type = RuntimeType.seatbelt

    def _version(self) -> str | None:
        raw = str(os.getenv("TLDW_SANDBOX_SEATBELT_VERSION") or "").strip()
        return raw or None

    def _supported_trust_levels(self) -> list[str]:
        levels = ["trusted"]
        if _truthy(os.getenv("TLDW_SANDBOX_SEATBELT_STANDARD_ENABLED")):
            levels.append("standard")
        return levels

    def preflight(self, network_policy: str | None = None) -> RuntimePreflightResult:
        host = vz_host_facts()
        reasons: list[str] = []

        if sys.platform != "darwin":
            reasons.append("macos_required")
        if not bool(host.get("apple_silicon")):
            reasons.append("apple_silicon_required")

        availability_override = os.getenv("TLDW_SANDBOX_SEATBELT_AVAILABLE")
        if availability_override is not None and not _truthy(availability_override):
            reasons.append("seatbelt_unavailable")

        if str(network_policy or "deny_all").strip().lower() == "allowlist":
            reasons.append("strict_allowlist_not_supported")

        available = not reasons
        return RuntimePreflightResult(
            runtime=self.runtime_type,
            available=available,
            reasons=reasons,
            supported_trust_levels=self._supported_trust_levels(),
            host={str(k): v for k, v in host.items()},
            enforcement_ready={"deny_all": False, "allowlist": False},
        )

    def _run_fake(self, run_id: str) -> RunStatus:
        now = datetime.utcnow()
        hub = get_hub()
        for event, payload in (
            ("start", {"ts": now.isoformat(), "runtime": self.runtime_type.value}),
            ("end", {"exit_code": 0}),
        ):
            try:
                hub.publish_event(run_id, event, payload)
            except (AttributeError, OSError, PermissionError, RuntimeError, TypeError, ValueError) as exc:
                logger.warning(
                    "seatbelt fake execution failed to publish {} event for run {}: {}",
                    event,
                    run_id,
                    exc,
                )
        return RunStatus(
            id="",
            phase=RunPhase.completed,
            started_at=now,
            finished_at=now,
            exit_code=0,
            message="seatbelt fake execution",
            runtime_version=self._version(),
        )

    @classmethod
    def cancel_run(cls, _run_id: str) -> bool:
        return False

    def start_run(
        self,
        run_id: str,
        spec: RunSpec,
        session_workspace: str | None = None,
    ) -> RunStatus:
        del spec
        del session_workspace
        if _truthy(os.getenv("TLDW_SANDBOX_SEATBELT_FAKE_EXEC")):
            return self._run_fake(run_id)
        raise RuntimeError("seatbelt_real_execution_not_implemented")
