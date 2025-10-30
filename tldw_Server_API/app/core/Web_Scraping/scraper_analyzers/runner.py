from __future__ import annotations

import asyncio
from typing import Any, Dict, Literal, Optional, TypedDict

from .analyzers.behavioral_detector import detect_honeypots
from .analyzers.captcha_detector import detect_captcha
from .analyzers.js_detector import analyze_js_rendering
from .analyzers.rate_limit_profiler import profile_rate_limits
from .analyzers.robots_checker import check_robots_txt
from .analyzers.tls_analyzer import analyze_tls_fingerprint
from .analyzers.waf_detector import detect_waf
from .recommendations.recommender import generate_recommendations
from .scoring.scoring_engine import calculate_difficulty_score

ScanDepth = Literal["default", "thorough", "deep"]


class AnalysisOutput(TypedDict):
    results: Dict[str, Any]
    score: Dict[str, Any]
    recommendations: Dict[str, Any]


async def gather_analysis(
    url: str,
    *,
    find_all: bool = False,
    impersonate: bool = False,
    scan_depth: Optional[ScanDepth] = None,
) -> AnalysisOutput:
    """
    Run the full suite of analyzers against ``url`` and return aggregated results.
    """
    robots_result = check_robots_txt(url)
    crawl_delay = robots_result.get("crawl_delay")

    tls_result = await analyze_tls_fingerprint(url)
    js_result = analyze_js_rendering(url)

    depth = scan_depth or "default"
    behavioral_result = detect_honeypots(url, scan_depth=depth)
    captcha_result = detect_captcha(url)

    rate_limit_result = await profile_rate_limits(url, crawl_delay, impersonate=impersonate)
    waf_result = detect_waf(url, find_all=find_all)

    results: Dict[str, Any] = {
        "robots": robots_result,
        "tls": tls_result,
        "js": js_result,
        "behavioral": behavioral_result,
        "captcha": captcha_result,
        "rate_limit": rate_limit_result,
        "waf": waf_result,
    }

    score_card = calculate_difficulty_score(results)
    recommendations = generate_recommendations(results)

    return {"results": results, "score": score_card, "recommendations": recommendations}


def run_analysis(
    url: str,
    *,
    find_all: bool = False,
    impersonate: bool = False,
    scan_depth: Optional[ScanDepth] = None,
) -> AnalysisOutput:
    """
    Synchronous convenience wrapper around :func:`gather_analysis`.

    This helper should only be used when no event loop is currently running.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            gather_analysis(url, find_all=find_all, impersonate=impersonate, scan_depth=scan_depth)
        )

    raise RuntimeError("run_analysis cannot be used inside an active event loop; use 'await gather_analysis' instead.")
