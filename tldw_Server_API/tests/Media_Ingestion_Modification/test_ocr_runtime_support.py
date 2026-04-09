from __future__ import annotations

import socket

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.runtime_support import (
    CLIOCRProfile,
    ManagedOCRProfile,
    RemoteOCRProfile,
    clear_managed_process,
    effective_page_concurrency,
    get_managed_process,
    is_profile_available,
    load_ocr_runtime_profiles,
    register_managed_process,
    render_argv_template,
    reset_managed_process_registry,
)


@pytest.mark.unit
def test_remote_availability_depends_on_config_only(monkeypatch):
    profile = RemoteOCRProfile(
        mode="remote",
        host="127.0.0.1",
        port=9999,
        allow_managed_start=False,
        max_page_concurrency=4,
        argv=("{model_path}", "{image_path}"),
    )

    def _fail(*args, **kwargs):
        raise AssertionError("reachability probes are not allowed")

    monkeypatch.setattr(socket, "create_connection", _fail)
    monkeypatch.setattr("subprocess.run", _fail)

    assert is_profile_available(profile) is True  # nosec B101


@pytest.mark.unit
def test_is_profile_available_uses_managed_registry_when_backend_matches():
    reset_managed_process_registry()
    profile = ManagedOCRProfile(
        mode="managed",
        allow_managed_start=False,
        max_page_concurrency=2,
        argv=(),
    )
    process = object()
    register_managed_process("llamacpp", process)

    assert is_profile_available(profile) is False  # nosec B101
    assert is_profile_available(profile, backend_name="llamacpp") is True  # nosec B101
    assert is_profile_available(profile, backend_name="chatllm") is False  # nosec B101


@pytest.mark.unit
def test_effective_page_concurrency_uses_global_and_backend_caps():
    assert effective_page_concurrency(8, 3) == 3  # nosec B101
    assert effective_page_concurrency(3, 8) == 3  # nosec B101
    assert effective_page_concurrency(None, 5) == 5  # nosec B101
    assert effective_page_concurrency(5, None) == 5  # nosec B101
    assert effective_page_concurrency(None, None) == 1  # nosec B101


@pytest.mark.unit
def test_render_argv_template_replaces_placeholders_without_shell_execution():
    rendered = render_argv_template(
        [
            "ocr-bin",
            "--model",
            "{model_path}",
            "--image",
            "{image_path}",
            "--prompt",
            "{prompt}",
            "--host",
            "{host}",
            "--port",
            "{port}",
        ],
        model_path="/opt/models/ocr model.bin",
        image_path="/var/run/ocr/input 01.png;rm -rf /",
        prompt='read literally $(echo pwned) & "quoted"',
        host="127.0.0.1",
        port=8123,
    )

    expected = [
        "ocr-bin",
        "--model",
        "/opt/models/ocr model.bin",
        "--image",
        "/var/run/ocr/input 01.png;rm -rf /",
        "--prompt",
        'read literally $(echo pwned) & "quoted"',
        "--host",
        "127.0.0.1",
        "--port",
        "8123",
    ]
    assert rendered == expected  # nosec B101


@pytest.mark.unit
def test_render_argv_template_treats_replacement_values_literally():
    rendered = render_argv_template(
        ["ocr-bin", "--prompt", "{prompt}", "--host", "{host}", "--port", "{port}"],
        prompt="mention {host} and {port} literally",
        host="alpha",
        port=8123,
    )

    assert rendered == [
        "ocr-bin",
        "--prompt",
        "mention {host} and {port} literally",
        "--host",
        "alpha",
        "--port",
        "8123",
    ]  # nosec B101


@pytest.mark.unit
def test_load_ocr_runtime_profiles_defaults_to_os_environ(monkeypatch):
    monkeypatch.setenv("LLAMACPP_OCR_MODE", "managed")
    monkeypatch.setenv("LLAMACPP_OCR_ALLOW_MANAGED_START", "true")
    monkeypatch.setenv("LLAMACPP_OCR_MAX_PAGE_CONCURRENCY", "12")
    monkeypatch.setenv("LLAMACPP_OCR_ARGV", '["ocr-cli", "{image_path}", "{prompt}"]')

    profiles = load_ocr_runtime_profiles("LLAMACPP")

    assert isinstance(profiles.active, ManagedOCRProfile)  # nosec B101
    assert profiles.active.allow_managed_start is True  # nosec B101
    assert profiles.active.max_page_concurrency == 12  # nosec B101
    assert profiles.active.argv == ("ocr-cli", "{image_path}", "{prompt}")  # nosec B101


@pytest.mark.unit
def test_load_ocr_runtime_profiles_parses_env_inputs():
    env = {
        "LLAMACPP_OCR_MODE": "managed",
        "LLAMACPP_OCR_ALLOW_MANAGED_START": "true",
        "LLAMACPP_OCR_MAX_PAGE_CONCURRENCY": "12",
        "LLAMACPP_OCR_ARGV": '["ocr-cli", "{image_path}", "{prompt}"]',
    }

    profiles = load_ocr_runtime_profiles("LLAMACPP", env=env)

    assert isinstance(profiles.active, ManagedOCRProfile)  # nosec B101
    assert profiles.active.allow_managed_start is True  # nosec B101
    assert profiles.active.max_page_concurrency == 12  # nosec B101
    assert profiles.active.argv == ("ocr-cli", "{image_path}", "{prompt}")  # nosec B101


@pytest.mark.unit
def test_load_ocr_runtime_profiles_defaults_page_concurrency_to_one():
    profiles = load_ocr_runtime_profiles(
        "LLAMACPP",
        env={"LLAMACPP_OCR_MODE": "remote"},
    )

    assert profiles.active.max_page_concurrency == 1  # nosec B101


@pytest.mark.unit
def test_managed_process_registry_is_keyed_by_backend_name():
    reset_managed_process_registry()
    process_a = object()
    process_b = object()

    register_managed_process("llamacpp", process_a)
    register_managed_process("chatllm", process_b)

    assert get_managed_process("llamacpp") is process_a  # nosec B101
    assert get_managed_process("chatllm") is process_b  # nosec B101

    assert clear_managed_process("llamacpp") is process_a  # nosec B101
    assert get_managed_process("llamacpp") is None  # nosec B101
    assert get_managed_process("chatllm") is process_b  # nosec B101
