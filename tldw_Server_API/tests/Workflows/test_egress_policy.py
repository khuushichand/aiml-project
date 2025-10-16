import os
from tldw_Server_API.app.core.Security.egress import evaluate_url_policy, is_url_allowed_for_tenant


def test_egress_profile_strict_requires_allow(tmp_path, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("WORKFLOWS_EGRESS_PROFILE", raising=False)
    monkeypatch.delenv("WORKFLOWS_EGRESS_ALLOWLIST", raising=False)
    r = evaluate_url_policy("https://example.com")
    assert not r.allowed and "allowlist" in (r.reason or "")


def test_egress_global_allow_allows_public(monkeypatch):
    monkeypatch.setenv("WORKFLOWS_EGRESS_PROFILE", "strict")
    monkeypatch.setenv("WORKFLOWS_EGRESS_ALLOWLIST", "example.com")
    # Avoid DNS resolution in sandbox
    monkeypatch.setenv("WORKFLOWS_EGRESS_BLOCK_PRIVATE", "false")
    r = evaluate_url_policy("https://sub.example.com/path")
    assert r.allowed


def test_egress_tenant_allow_overrides_union(monkeypatch):
    tenant = "acme"
    monkeypatch.setenv("WORKFLOWS_EGRESS_PROFILE", "strict")
    monkeypatch.setenv("WORKFLOWS_EGRESS_ALLOWLIST", "example.com")
    monkeypatch.setenv("WORKFLOWS_EGRESS_BLOCK_PRIVATE", "false")
    # Not in global allowlist
    monkeypatch.setenv(f"WORKFLOWS_EGRESS_ALLOWLIST_{tenant.upper()}", "allowed.acme.io")
    ok = is_url_allowed_for_tenant("https://allowed.acme.io/foo", tenant)
    assert ok is True


def test_egress_deny_wins(monkeypatch):
    tenant = "acme"
    monkeypatch.setenv("WORKFLOWS_EGRESS_PROFILE", "permissive")
    monkeypatch.setenv("WORKFLOWS_EGRESS_DENYLIST", "blocked.com")
    assert evaluate_url_policy("https://blocked.com").allowed is False
    # Tenant allow cannot bypass deny
    monkeypatch.setenv(f"WORKFLOWS_EGRESS_ALLOWLIST_{tenant.upper()}", "blocked.com")
    assert is_url_allowed_for_tenant("https://blocked.com", tenant) is False
