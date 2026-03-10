from __future__ import annotations

from ..models import RuntimeType
from .vz_common import VZBaseRunner


class VZLinuxRunner(VZBaseRunner):
    runtime_type = RuntimeType.vz_linux
    fake_exec_env_key = "TLDW_SANDBOX_VZ_LINUX_FAKE_EXEC"
    available_env_key = "TLDW_SANDBOX_VZ_LINUX_AVAILABLE"
    version_env_key = "TLDW_SANDBOX_VZ_LINUX_VERSION"
    template_ready_env_key = "TLDW_SANDBOX_VZ_LINUX_TEMPLATE_READY"
    template_missing_reason = "vz_linux_template_missing"
