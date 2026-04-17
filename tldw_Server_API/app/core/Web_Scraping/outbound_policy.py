from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

from loguru import logger

from tldw_Server_API.app.core.Security.egress import evaluate_url_policy
from tldw_Server_API.app.core.Web_Scraping.filters import RobotsFilter
from tldw_Server_API.app.core.config import load_and_log_configs


_Mode = Literal["compat", "strict"]


@dataclass(slots=True, frozen=True)
class WebOutboundPolicyDecision:
    allowed: bool
    mode: _Mode
    reason: str
    stage: str
    source: str
    details: dict[str, Any] | None = None


def get_web_outbound_policy_mode(config: dict[str, Any] | None = None) -> _Mode:
    raw_mode = os.getenv("WEB_OUTBOUND_POLICY_MODE")
    if raw_mode is None:
        loaded = config if config is not None else (load_and_log_configs() or {})
        raw_mode = str(
            ((loaded.get("web_scraper", {}) or {}).get("web_outbound_policy_mode", "compat"))
        )

    mode = str(raw_mode or "compat").strip().lower()
    return "strict" if mode == "strict" else "compat"


def _decision(
    allowed: bool,
    *,
    mode: _Mode,
    reason: str,
    stage: str,
    source: str,
    details: dict[str, Any] | None = None,
) -> WebOutboundPolicyDecision:
    return WebOutboundPolicyDecision(
        allowed=allowed,
        mode=mode,
        reason=reason,
        stage=stage,
        source=source,
        details=details,
    )


def decide_web_outbound_policy_sync(
    url: str,
    *,
    respect_robots: bool,
    source: str,
    stage: str,
    config: dict[str, Any] | None = None,
) -> WebOutboundPolicyDecision:
    mode = get_web_outbound_policy_mode(config)
    raw = evaluate_url_policy(url)
    if not getattr(raw, "allowed", False):
        return _decision(
            False,
            mode=mode,
            reason=str(getattr(raw, "reason", "egress_denied")),
            stage=stage,
            source=source,
        )

    if respect_robots:
        reason = "robots_sync_unsupported" if mode == "strict" else "robots_skipped"
        return _decision(mode != "strict", mode=mode, reason=reason, stage=stage, source=source)

    return _decision(True, mode=mode, reason="allowed", stage=stage, source=source)


async def decide_web_outbound_policy(
    url: str,
    *,
    respect_robots: bool,
    user_agent: str | None,
    source: str,
    stage: str,
    config: dict[str, Any] | None = None,
) -> WebOutboundPolicyDecision:
    mode = get_web_outbound_policy_mode(config)
    raw = evaluate_url_policy(url)
    if not getattr(raw, "allowed", False):
        return _decision(
            False,
            mode=mode,
            reason=str(getattr(raw, "reason", "egress_denied")),
            stage=stage,
            source=source,
        )

    if not respect_robots:
        return _decision(True, mode=mode, reason="robots_skipped", stage=stage, source=source)

    robots_filter = RobotsFilter(user_agent=user_agent or "*")
    try:
        allowed = await robots_filter.allowed(url)
    except Exception as exc:  # pragma: no cover - explicit behavior covered by monkeypatched tests
        logger.debug(f"Web outbound policy robots check failed for {url}: {exc}")
        if mode == "strict":
            return _decision(False, mode=mode, reason="robots_unreachable", stage=stage, source=source)
        return _decision(
            True,
            mode=mode,
            reason="robots_unreachable_allowed",
            stage=stage,
            source=source,
        )

    if not allowed:
        return _decision(False, mode=mode, reason="robots_disallowed", stage=stage, source=source)

    return _decision(True, mode=mode, reason="allowed", stage=stage, source=source)
