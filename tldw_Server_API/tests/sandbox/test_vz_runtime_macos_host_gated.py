from __future__ import annotations

import sys

import pytest

from tldw_Server_API.app.core.Sandbox.runners.vz_linux_runner import VZLinuxRunner
from tldw_Server_API.app.core.Sandbox.runners.vz_macos_runner import VZMacOSRunner


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS host only")
def test_vz_linux_preflight_smoke_on_real_host() -> None:
    result = VZLinuxRunner().preflight(network_policy="deny_all")

    assert isinstance(result.available, bool)
    assert isinstance(result.host, dict)
    assert "os" in result.host


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS host only")
def test_vz_macos_preflight_smoke_on_real_host() -> None:
    result = VZMacOSRunner().preflight(network_policy="deny_all")

    assert isinstance(result.available, bool)
    assert isinstance(result.host, dict)
    assert "os" in result.host
