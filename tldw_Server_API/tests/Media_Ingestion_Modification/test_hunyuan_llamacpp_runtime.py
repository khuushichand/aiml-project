from __future__ import annotations

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
