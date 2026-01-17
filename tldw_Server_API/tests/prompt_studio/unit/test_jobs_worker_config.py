import os

import pytest

from tldw_Server_API.app.core.Prompt_Management.prompt_studio.services import jobs_worker


pytestmark = pytest.mark.unit


def test_build_worker_config_uses_env(monkeypatch):
    monkeypatch.setenv("PROMPT_STUDIO_JOBS_LEASE_SECONDS", "40")
    monkeypatch.setenv("PROMPT_STUDIO_JOBS_RENEW_JITTER_SECONDS", "3")
    monkeypatch.setenv("PROMPT_STUDIO_JOBS_RENEW_THRESHOLD_SECONDS", "11")

    cfg = jobs_worker._build_worker_config(worker_id="w1", queue="default")

    assert cfg.lease_seconds == 40
    assert cfg.renew_jitter_seconds == 3
    assert cfg.renew_threshold_seconds == 11
    assert cfg.worker_id == "w1"
    assert cfg.queue == "default"


def test_build_worker_config_heartbeat_override(monkeypatch):
    monkeypatch.setenv("PROMPT_STUDIO_JOBS_LEASE_SECONDS", "60")
    monkeypatch.setenv("PROMPT_STUDIO_JOBS_RENEW_THRESHOLD_SECONDS", "10")
    monkeypatch.setenv("TLDW_PS_HEARTBEAT_SECONDS", "15")

    cfg = jobs_worker._build_worker_config(worker_id="w2", queue="default")

    assert cfg.renew_threshold_seconds == 45


def test_build_worker_config_heartbeat_exceeds_lease(monkeypatch):
    monkeypatch.setenv("PROMPT_STUDIO_JOBS_LEASE_SECONDS", "10")
    monkeypatch.setenv("TLDW_PS_HEARTBEAT_SECONDS", "20")

    cfg = jobs_worker._build_worker_config(worker_id="w3", queue="default")

    assert cfg.renew_threshold_seconds == 1
