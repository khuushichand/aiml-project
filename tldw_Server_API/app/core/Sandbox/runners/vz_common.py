from __future__ import annotations

import contextlib
import os
import platform
import sys
from datetime import datetime

from tldw_Server_API.app.core.testing import is_truthy

from ..models import RunPhase, RunSpec, RunStatus, RuntimeType
from ..runtime_capabilities import RuntimePreflightResult
from ..streams import get_hub

_VZ_NONCRITICAL_EXCEPTIONS = (
    AttributeError,
    OSError,
    PermissionError,
    RuntimeError,
    TypeError,
    ValueError,
)

_APPLE_SILICON_ARCHES = {"arm64", "aarch64"}


def _truthy(value: str | None) -> bool:
    return is_truthy(value)


def vz_host_facts() -> dict[str, str | bool]:
    arch = str(platform.machine() or "").strip().lower()
    return {
        "os": sys.platform,
        "arch": arch,
        "apple_silicon": bool(sys.platform == "darwin" and arch in _APPLE_SILICON_ARCHES),
    }


class VZBaseRunner:
    runtime_type: RuntimeType
    fake_exec_env_key: str
    available_env_key: str
    version_env_key: str
    template_ready_env_key: str
    template_missing_reason: str

    def _execution_ready(self) -> bool:
        return _truthy(os.getenv(self.fake_exec_env_key))

    def _helper_ready(self) -> bool:
        return _truthy(os.getenv("TLDW_SANDBOX_MACOS_HELPER_READY"))

    def _template_ready(self) -> bool:
        return _truthy(os.getenv(self.template_ready_env_key))

    def _version(self) -> str | None:
        raw = str(os.getenv(self.version_env_key) or "").strip()
        return raw or None

    def preflight(self, network_policy: str | None = None) -> RuntimePreflightResult:
        host = vz_host_facts()
        reasons: list[str] = []

        if sys.platform != "darwin":
            reasons.append("macos_required")
        if not bool(host.get("apple_silicon")):
            reasons.append("apple_silicon_required")

        availability_override = os.getenv(self.available_env_key)
        if availability_override is not None and not _truthy(availability_override):
            reasons.append(f"{self.runtime_type.value}_unavailable")

        if not self._helper_ready():
            reasons.append("macos_helper_missing")
        if not self._template_ready():
            reasons.append(self.template_missing_reason)
        if not self._execution_ready():
            reasons.append("real_execution_not_implemented")

        if str(network_policy or "deny_all").strip().lower() == "allowlist":
            reasons.append("strict_allowlist_not_supported")

        available = not reasons
        return RuntimePreflightResult(
            runtime=self.runtime_type,
            available=available,
            reasons=reasons,
            host={str(k): v for k, v in host.items()},
            enforcement_ready={"deny_all": available, "allowlist": False},
        )

    def _run_fake(self, run_id: str, message: str) -> RunStatus:
        now = datetime.utcnow()
        with contextlib.suppress(_VZ_NONCRITICAL_EXCEPTIONS):
            get_hub().publish_event(run_id, "start", {"ts": now.isoformat(), "runtime": self.runtime_type.value})
            get_hub().publish_event(run_id, "end", {"exit_code": 0})
        return RunStatus(
            id="",
            phase=RunPhase.completed,
            started_at=now,
            finished_at=now,
            exit_code=0,
            message=message,
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
        if _truthy(os.getenv(self.fake_exec_env_key)):
            return self._run_fake(run_id, message=f"{self.runtime_type.value} fake execution")
        raise RuntimeError(f"{self.runtime_type.value}_real_execution_not_implemented")
