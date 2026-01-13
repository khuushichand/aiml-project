import os

import pytest

from tldw_Server_API.app.core.Prompt_Management.prompt_studio.quota_config import (
    apply_prompt_studio_quota_defaults,
    apply_prompt_studio_quota_policy,
)


def test_apply_prompt_studio_quota_defaults_sets_jobs_env(monkeypatch):
    monkeypatch.delenv("JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO", raising=False)
    monkeypatch.delenv("JOBS_QUOTA_MAX_QUEUED_PROMPT_STUDIO", raising=False)
    monkeypatch.delenv("JOBS_QUOTA_SUBMITS_PER_MIN_PROMPT_STUDIO", raising=False)
    monkeypatch.setenv("PROMPT_STUDIO_MAX_CONCURRENT_JOBS", "12")
    monkeypatch.setenv("PROMPT_STUDIO_JOBS_MAX_QUEUED", "50")
    monkeypatch.setenv("PROMPT_STUDIO_JOBS_SUBMITS_PER_MIN", "8")

    applied = apply_prompt_studio_quota_defaults()

    assert os.getenv("JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO") == "12"
    assert os.getenv("JOBS_QUOTA_MAX_QUEUED_PROMPT_STUDIO") == "50"
    assert os.getenv("JOBS_QUOTA_SUBMITS_PER_MIN_PROMPT_STUDIO") == "8"
    assert applied["JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO"] == 12
    assert applied["JOBS_QUOTA_MAX_QUEUED_PROMPT_STUDIO"] == 50
    assert applied["JOBS_QUOTA_SUBMITS_PER_MIN_PROMPT_STUDIO"] == 8


def test_apply_prompt_studio_quota_defaults_does_not_override(monkeypatch):
    monkeypatch.setenv("JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO", "3")
    monkeypatch.setenv("PROMPT_STUDIO_MAX_CONCURRENT_JOBS", "9")

    applied = apply_prompt_studio_quota_defaults()

    assert os.getenv("JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO") == "3"
    assert "JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO" not in applied


def test_apply_prompt_studio_quota_defaults_ignores_invalid(monkeypatch):
    monkeypatch.delenv("JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO", raising=False)
    monkeypatch.setenv("PROMPT_STUDIO_MAX_CONCURRENT_JOBS", "bad")

    applied = apply_prompt_studio_quota_defaults()

    assert os.getenv("JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO") is None
    assert applied == {}


@pytest.mark.asyncio
async def test_apply_prompt_studio_quota_policy_sets_user_env(monkeypatch):
    async def fake_effective_config(_user_id):
        return {
            "limits.prompt_studio_max_concurrent_jobs": 4,
            "limits.prompt_studio_max_queued_jobs": 20,
            "limits.prompt_studio_submits_per_min": 6,
        }

    monkeypatch.setenv("TEST_MODE", "false")
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Prompt_Management.prompt_studio.quota_config._load_effective_config",
        fake_effective_config,
        raising=True,
    )
    monkeypatch.delenv("JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO_USER_5", raising=False)
    monkeypatch.delenv("JOBS_QUOTA_MAX_QUEUED_PROMPT_STUDIO_USER_5", raising=False)
    monkeypatch.delenv("JOBS_QUOTA_SUBMITS_PER_MIN_PROMPT_STUDIO_USER_5", raising=False)

    applied = await apply_prompt_studio_quota_policy("5")

    assert os.getenv("JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO_USER_5") == "4"
    assert os.getenv("JOBS_QUOTA_MAX_QUEUED_PROMPT_STUDIO_USER_5") == "20"
    assert os.getenv("JOBS_QUOTA_SUBMITS_PER_MIN_PROMPT_STUDIO_USER_5") == "6"
    assert applied["JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO_USER_5"] == 4
    assert applied["JOBS_QUOTA_MAX_QUEUED_PROMPT_STUDIO_USER_5"] == 20
    assert applied["JOBS_QUOTA_SUBMITS_PER_MIN_PROMPT_STUDIO_USER_5"] == 6


@pytest.mark.asyncio
async def test_apply_prompt_studio_quota_policy_clears_removed(monkeypatch):
    async def config_with_limits(_user_id):
        return {"limits.prompt_studio_max_concurrent_jobs": 2}

    async def config_empty(_user_id):
        return {}

    monkeypatch.setenv("TEST_MODE", "false")
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Prompt_Management.prompt_studio.quota_config._load_effective_config",
        config_with_limits,
        raising=True,
    )
    await apply_prompt_studio_quota_policy("7")
    assert os.getenv("JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO_USER_7") == "2"

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Prompt_Management.prompt_studio.quota_config._load_effective_config",
        config_empty,
        raising=True,
    )
    await apply_prompt_studio_quota_policy("7")
    assert os.getenv("JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO_USER_7") is None
