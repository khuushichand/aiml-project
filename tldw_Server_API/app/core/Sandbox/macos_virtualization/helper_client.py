from __future__ import annotations

import os
from typing import Any

from tldw_Server_API.app.core.testing import is_truthy

from .models import HelperVMReply


class MacOSVirtualizationHelperClient:
    """Client stub for the future native macOS virtualization helper."""

    def create_vm(self, request: dict[str, Any]) -> HelperVMReply:
        if is_truthy(os.getenv("TEST_MODE")):
            vm_name = str(request.get("vm_name") or "").strip() or "vm-test"
            runtime = str(request.get("runtime") or "").strip()
            return HelperVMReply(
                vm_id=vm_name,
                state="created",
                details={"runtime": runtime or None, "transport": "fake"},
            )
        raise RuntimeError("macos_virtualization_helper_unavailable")
