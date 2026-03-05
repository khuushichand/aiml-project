from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import moderation as moderation_mod
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal
from tldw_Server_API.app.core.Moderation.moderation_service import ModerationPolicy, ModerationService, PatternRule


def _make_principal() -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=["admin"],
        permissions=[SYSTEM_CONFIGURE],
        is_admin=True,
        org_ids=[1],
        team_ids=[],
    )


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(moderation_mod.router, prefix="/api/v1")

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        principal = _make_principal()
        request.state.auth = AuthContext(
            principal=principal,
            ip=None,
            user_agent=None,
            request_id=None,
        )
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    return app


@pytest.mark.unit
def test_moderation_test_sample_matches_selected_rule(monkeypatch):
    svc = ModerationService()
    rule_warn = PatternRule(regex=re.compile(r"alpha", re.IGNORECASE), action="warn")
    rule_block = PatternRule(regex=re.compile(r"beta", re.IGNORECASE), action="block")
    svc._global_policy = ModerationPolicy(
        enabled=True,
        input_enabled=True,
        output_enabled=True,
        input_action="warn",
        output_action="warn",
        redact_replacement="[REDACTED]",
        per_user_overrides=False,
        block_patterns=[rule_warn, rule_block],
        categories_enabled=None,
    )

    monkeypatch.setattr(moderation_mod, "get_moderation_service", lambda: svc)

    app = _build_app()
    text = "alpha " + ("x" * 60) + " beta"

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/moderation/test",
            json={"text": text, "phase": "input"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("action") == "block"
    sample = body.get("sample")
    assert sample
    assert "[REDACTED]" in sample
    assert "alpha" not in sample.lower()
    assert "beta" not in sample.lower()


@pytest.mark.unit
def test_effective_policy_merges_user_rules_and_returns_warn_action():
    svc = ModerationService()
    svc._global_policy = ModerationPolicy(
        enabled=True,
        input_enabled=True,
        output_enabled=True,
        input_action="warn",
        output_action="warn",
        redact_replacement="[REDACTED]",
        per_user_overrides=True,
        block_patterns=[],
        categories_enabled=None,
    )
    svc._user_overrides = {
        "alice": {
            "rules": [
                {
                    "id": "r1",
                    "pattern": "heads up",
                    "is_regex": False,
                    "action": "warn",
                    "phase": "both",
                }
            ]
        }
    }

    policy = svc.get_effective_policy("alice")
    action, _, sample, _ = svc.evaluate_action("please heads up now", policy, "output")
    assert action == "warn"
    assert sample


@pytest.mark.unit
def test_effective_policy_user_rules_apply_with_category_filter_enabled():
    svc = ModerationService()
    svc._global_policy = ModerationPolicy(
        enabled=True,
        input_enabled=True,
        output_enabled=True,
        input_action="warn",
        output_action="warn",
        redact_replacement="[REDACTED]",
        per_user_overrides=True,
        block_patterns=[],
        categories_enabled={"pii"},
    )
    svc._user_overrides = {
        "alice": {
            "rules": [
                {
                    "id": "r1",
                    "pattern": "heads up",
                    "is_regex": False,
                    "action": "block",
                    "phase": "both",
                }
            ]
        }
    }

    policy = svc.get_effective_policy("alice")
    action, category, _, _ = svc.evaluate_action("please heads up now", policy, "input")
    flagged, _ = svc.check_text("please heads up now", policy, phase="input")

    assert action == "block"
    assert flagged is True
    assert category is None
