from __future__ import annotations

import socket

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.runtime_support import (
    CLIOCRProfile,
    RemoteOCRProfile,
    load_ocr_runtime_profiles_from_keys,
)


@pytest.mark.unit
def test_load_ocr_runtime_profiles_from_keys_uses_remote_mode_specific_fields():
    env = {
        "HUNYUAN_LLAMACPP_MODE": "remote",
        "HUNYUAN_LLAMACPP_HOST": "127.0.0.1",
        "HUNYUAN_LLAMACPP_PORT": "8088",
        "HUNYUAN_LLAMACPP_MODEL": "ggml-org/HunyuanOCR-GGUF:Q8_0",
        "HUNYUAN_LLAMACPP_MODEL_PATH": "/models/ignored-by-remote.gguf",
        "HUNYUAN_LLAMACPP_SERVER_ARGV": '["llama-server", "-hf", "{model_path}"]',
        "HUNYUAN_LLAMACPP_CLI_ARGV": '["llama-ocr", "--model", "{model_path}"]',
    }

    profiles = load_ocr_runtime_profiles_from_keys(
        env=env,
        mode_key="HUNYUAN_LLAMACPP_MODE",
        host_key="HUNYUAN_LLAMACPP_HOST",
        port_key="HUNYUAN_LLAMACPP_PORT",
        remote_model_key="HUNYUAN_LLAMACPP_MODEL",
        model_path_key="HUNYUAN_LLAMACPP_MODEL_PATH",
        managed_argv_key="HUNYUAN_LLAMACPP_SERVER_ARGV",
        cli_argv_key="HUNYUAN_LLAMACPP_CLI_ARGV",
    )

    assert isinstance(profiles.active, RemoteOCRProfile)  # nosec B101
    assert isinstance(profiles.cli, CLIOCRProfile)  # nosec B101
    assert profiles.remote.model == "ggml-org/HunyuanOCR-GGUF:Q8_0"  # nosec B101
    assert profiles.remote.model_path is None  # nosec B101
    assert profiles.remote.argv == ()  # nosec B101
    assert profiles.cli.model_path == "/models/ignored-by-remote.gguf"  # nosec B101
    assert profiles.cli.argv == ("llama-ocr", "--model", "{model_path}")  # nosec B101


@pytest.mark.unit
def test_hunyuan_llamacpp_runtime_available_is_local_only_for_remote_mode(monkeypatch):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.hunyuan_llamacpp_runtime import (
        HunyuanLlamaCppRuntime,
    )

    monkeypatch.setenv("HUNYUAN_LLAMACPP_MODE", "remote")
    monkeypatch.setenv("HUNYUAN_LLAMACPP_HOST", "127.0.0.1")
    monkeypatch.setenv("HUNYUAN_LLAMACPP_PORT", "8088")
    monkeypatch.setenv("HUNYUAN_LLAMACPP_MODEL", "ggml-org/HunyuanOCR-GGUF:Q8_0")

    def _fail(*args, **kwargs):
        raise AssertionError("availability must stay local-only")

    monkeypatch.setattr(socket, "create_connection", _fail)
    monkeypatch.setattr("subprocess.run", _fail)

    assert HunyuanLlamaCppRuntime.available() is True  # nosec B101


@pytest.mark.unit
def test_hunyuan_llamacpp_runtime_auto_mode_prefers_remote_before_managed_and_cli(monkeypatch):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.hunyuan_llamacpp_runtime import (
        HunyuanLlamaCppRuntime,
    )

    monkeypatch.setenv("HUNYUAN_LLAMACPP_MODE", "auto")
    monkeypatch.setenv("HUNYUAN_LLAMACPP_HOST", "127.0.0.1")
    monkeypatch.setenv("HUNYUAN_LLAMACPP_PORT", "8088")
    monkeypatch.setenv("HUNYUAN_LLAMACPP_MODEL", "ggml-org/HunyuanOCR-GGUF:Q8_0")
    monkeypatch.setenv("HUNYUAN_LLAMACPP_ALLOW_MANAGED_START", "true")
    monkeypatch.setenv("HUNYUAN_LLAMACPP_MODEL_PATH", "/models/HunyuanOCR-GGUF-Q8_0.gguf")
    monkeypatch.setenv("HUNYUAN_LLAMACPP_SERVER_ARGV", '["llama-server", "-hf", "{model_path}"]')
    monkeypatch.setenv("HUNYUAN_LLAMACPP_CLI_ARGV", '["llama-ocr", "--model", "{model_path}"]')

    description = HunyuanLlamaCppRuntime.describe()

    assert HunyuanLlamaCppRuntime.available() is True  # nosec B101
    assert description["mode"] == "remote"  # nosec B101
    assert description["configured_mode"] == "auto"  # nosec B101
