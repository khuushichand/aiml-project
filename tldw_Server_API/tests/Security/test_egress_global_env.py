import os
from tldw_Server_API.app.core.Security.egress import evaluate_url_policy


def test_global_egress_denylist_blocks(monkeypatch):
    # Ensure global deny blocks the host regardless of workflows-specific envs
    monkeypatch.setenv("EGRESS_DENYLIST", "blocked.example.com")
    monkeypatch.delenv("WORKFLOWS_EGRESS_DENYLIST", raising=False)
    res = evaluate_url_policy("https://blocked.example.com/path")
    assert res.allowed is False
    assert isinstance(getattr(res, 'reason', ''), str)


def test_global_egress_allowlist_allows_when_strict(monkeypatch):
    # Strict profile requires allowlist entries; ensure global allowlist is honored
    monkeypatch.setenv("ENVIRONMENT", "prod")  # force strict default
    monkeypatch.setenv("EGRESS_ALLOWLIST", "ok.example.com")
    # Disable private IP check to avoid DNS in test
    monkeypatch.setenv("WORKFLOWS_EGRESS_BLOCK_PRIVATE", "false")
    monkeypatch.delenv("WORKFLOWS_EGRESS_ALLOWLIST", raising=False)
    res_ok = evaluate_url_policy("https://ok.example.com")
    assert res_ok.allowed is True
    res_bad = evaluate_url_policy("https://nope.example.com")
    assert res_bad.allowed is False
