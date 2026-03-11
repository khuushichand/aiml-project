from __future__ import annotations

from ..models import RuntimeType
from .vz_common import VZBaseRunner


class VZMacOSRunner(VZBaseRunner):
    runtime_type = RuntimeType.vz_macos
    fake_exec_env_key = "TLDW_SANDBOX_VZ_MACOS_FAKE_EXEC"
    available_env_key = "TLDW_SANDBOX_VZ_MACOS_AVAILABLE"
    version_env_key = "TLDW_SANDBOX_VZ_MACOS_VERSION"
    template_ready_env_key = "TLDW_SANDBOX_VZ_MACOS_TEMPLATE_READY"
    template_missing_reason = "macos_template_missing"
