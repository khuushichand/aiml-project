from __future__ import annotations

import tldw_Server_API.app.core.Sandbox.macos_diagnostics as diagnostics_module


def test_collect_macos_diagnostics_reports_missing_helper_and_templates(monkeypatch) -> None:
    monkeypatch.setattr(diagnostics_module.sys, "platform", "darwin")
    monkeypatch.setattr(diagnostics_module.platform, "machine", lambda: "arm64")
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.delenv("TLDW_SANDBOX_MACOS_HELPER_PATH", raising=False)
    monkeypatch.delenv("TLDW_SANDBOX_MACOS_HELPER_READY", raising=False)
    monkeypatch.delenv("TLDW_SANDBOX_VZ_LINUX_TEMPLATE_SOURCE", raising=False)
    monkeypatch.delenv("TLDW_SANDBOX_VZ_LINUX_TEMPLATE_READY", raising=False)
    monkeypatch.delenv("TLDW_SANDBOX_VZ_MACOS_TEMPLATE_READY", raising=False)
    monkeypatch.delenv("TLDW_SANDBOX_VZ_LINUX_FAKE_EXEC", raising=False)
    monkeypatch.delenv("TLDW_SANDBOX_VZ_MACOS_FAKE_EXEC", raising=False)

    data = diagnostics_module.collect_macos_diagnostics()

    assert data["host"]["supported"] is True
    assert data["helper"]["configured"] is False
    assert data["helper"]["path"] is None
    assert data["helper"]["ready"] is False
    assert data["templates"]["vz_linux"]["configured"] is False
    assert data["templates"]["vz_linux"]["source"] is None
    assert data["templates"]["vz_linux"]["ready"] is False
    assert "macos_helper_missing" in data["runtimes"]["vz_linux"]["reasons"]
    assert data["runtimes"]["vz_linux"]["execution_mode"] == "none"


def test_collect_macos_diagnostics_separates_policy_from_host_readiness(monkeypatch) -> None:
    monkeypatch.setattr(diagnostics_module.sys, "platform", "darwin")
    monkeypatch.setattr(diagnostics_module.platform, "machine", lambda: "arm64")
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_SEATBELT_AVAILABLE", "1")
    monkeypatch.delenv("TLDW_SANDBOX_SEATBELT_STANDARD_ENABLED", raising=False)

    data = diagnostics_module.collect_macos_diagnostics()

    assert data["runtimes"]["seatbelt"]["supported_trust_levels"] == ["trusted"]
    assert data["runtimes"]["seatbelt"]["available"] in (True, False)


def test_collect_macos_diagnostics_uses_optional_operator_metadata_env(monkeypatch) -> None:
    monkeypatch.setattr(diagnostics_module.sys, "platform", "darwin")
    monkeypatch.setattr(diagnostics_module.platform, "machine", lambda: "arm64")
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_MACOS_HELPER_PATH", "/tmp/macos-helper")
    monkeypatch.setenv("TLDW_SANDBOX_VZ_LINUX_TEMPLATE_SOURCE", "/tmp/vz-linux.img")

    data = diagnostics_module.collect_macos_diagnostics()

    assert data["helper"]["path"] == "/tmp/macos-helper"
    assert data["templates"]["vz_linux"]["source"] == "/tmp/vz-linux.img"
