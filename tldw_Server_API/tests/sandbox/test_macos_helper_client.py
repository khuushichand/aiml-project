from __future__ import annotations

from tldw_Server_API.app.core.Sandbox.macos_virtualization.helper_client import (
    MacOSVirtualizationHelperClient,
)


def test_helper_client_uses_fake_transport_in_test_mode(monkeypatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")

    client = MacOSVirtualizationHelperClient()
    reply = client.create_vm({"runtime": "vz_linux", "vm_name": "run-123"})

    assert reply.vm_id == "run-123"
    assert reply.state == "created"
