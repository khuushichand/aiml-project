import importlib
from types import SimpleNamespace

import pytest


pytestmark = pytest.mark.unit


def test_web_outbound_policy_mode_reads_config_when_env_unset(monkeypatch):
    monkeypatch.delenv("WEB_OUTBOUND_POLICY_MODE", raising=False)

    config_mod = importlib.import_module("tldw_Server_API.app.core.config")

    class _ConfigStub:
        def get(self, section, option, fallback=None):
            if section == "Web-Scraper" and option == "web_outbound_policy_mode":
                return "strict"
            return fallback

    monkeypatch.setattr(
        config_mod,
        "load_comprehensive_config",
        lambda: _ConfigStub(),
        raising=False,
    )

    assert config_mod.web_outbound_policy_mode() == "strict"


def test_web_outbound_policy_sync_denies_provider_request(monkeypatch):
    monkeypatch.delenv("WEB_OUTBOUND_POLICY_MODE", raising=False)
    policy = importlib.import_module(
        "tldw_Server_API.app.core.Web_Scraping.outbound_policy"
    )

    monkeypatch.setattr(
        policy,
        "evaluate_url_policy",
        lambda _url: SimpleNamespace(allowed=False, reason="deny_test"),
        raising=False,
    )

    decision = policy.decide_web_outbound_policy_sync(
        "https://example.com/search",
        respect_robots=False,
        source="websearch_provider",
        stage="provider_request",
    )

    assert decision.allowed is False
    assert decision.mode == "compat"
    assert decision.reason == "deny_test"
    assert decision.stage == "provider_request"
    assert decision.source == "websearch_provider"


def test_web_outbound_policy_sync_emits_decision_metric(monkeypatch):
    monkeypatch.delenv("WEB_OUTBOUND_POLICY_MODE", raising=False)
    policy = importlib.import_module(
        "tldw_Server_API.app.core.Web_Scraping.outbound_policy"
    )

    metric_calls: list[tuple[str, float, dict[str, str]]] = []

    monkeypatch.setattr(
        policy,
        "evaluate_url_policy",
        lambda _url: SimpleNamespace(allowed=False, reason="deny_test"),
        raising=False,
    )
    monkeypatch.setattr(
        policy,
        "increment_counter",
        lambda name, value=1, labels=None: metric_calls.append(
            (name, value, dict(labels or {}))
        ),
        raising=False,
    )

    decision = policy.decide_web_outbound_policy_sync(
        "https://example.com/search",
        respect_robots=False,
        source="websearch_provider",
        stage="provider_request",
    )

    assert decision.allowed is False
    assert metric_calls == [
        (
            "web_outbound_policy_decisions_total",
            1,
            {
                "mode": "compat",
                "source": "websearch_provider",
                "stage": "provider_request",
                "outcome": "blocked",
                "reason": "deny_test",
            },
        )
    ]


@pytest.mark.asyncio
async def test_web_outbound_policy_compat_allows_when_robots_fetch_errors(monkeypatch):
    monkeypatch.setenv("WEB_OUTBOUND_POLICY_MODE", "compat")
    policy = importlib.import_module(
        "tldw_Server_API.app.core.Web_Scraping.outbound_policy"
    )

    monkeypatch.setattr(
        policy,
        "evaluate_url_policy",
        lambda _url: SimpleNamespace(allowed=True, reason="allowed"),
        raising=False,
    )

    async def boom(self, _url):
        raise RuntimeError("robots timeout")

    monkeypatch.setattr(policy.RobotsFilter, "allowed", boom, raising=False)

    decision = await policy.decide_web_outbound_policy(
        "https://example.com/page",
        respect_robots=True,
        user_agent="UA",
        source="article_extract",
        stage="pre_fetch",
    )

    assert decision.allowed is True
    assert decision.mode == "compat"
    assert decision.reason == "robots_unreachable_allowed"
    assert decision.stage == "pre_fetch"
    assert decision.source == "article_extract"


@pytest.mark.asyncio
async def test_web_outbound_policy_strict_blocks_when_robots_fetch_errors(monkeypatch):
    monkeypatch.setenv("WEB_OUTBOUND_POLICY_MODE", "strict")
    policy = importlib.import_module(
        "tldw_Server_API.app.core.Web_Scraping.outbound_policy"
    )

    monkeypatch.setattr(
        policy,
        "evaluate_url_policy",
        lambda _url: SimpleNamespace(allowed=True, reason="allowed"),
        raising=False,
    )

    async def boom(self, _url):
        raise RuntimeError("robots timeout")

    monkeypatch.setattr(policy.RobotsFilter, "allowed", boom, raising=False)

    decision = await policy.decide_web_outbound_policy(
        "https://example.com/page",
        respect_robots=True,
        user_agent="UA",
        source="article_extract",
        stage="pre_fetch",
    )

    assert decision.allowed is False
    assert decision.mode == "strict"
    assert decision.reason == "robots_unreachable"
    assert decision.stage == "pre_fetch"
    assert decision.source == "article_extract"
