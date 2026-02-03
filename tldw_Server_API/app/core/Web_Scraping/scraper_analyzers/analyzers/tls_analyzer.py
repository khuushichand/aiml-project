from __future__ import annotations

import logging
import random
import warnings
from typing import Any

warnings.filterwarnings("ignore", message="Event loop is closed", category=RuntimeWarning)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

try:
    from curl_cffi.requests import AsyncSession
except ImportError:  # pragma: no cover - optional dependency guard
    AsyncSession = None

from tldw_Server_API.app.core.http_client import afetch

from ..utils.browser_identities import MODERN_BROWSER_IDENTITIES
from ..utils.impersonate_target import get_impersonate_target


async def _run_tls_test(url: str) -> dict[str, Any]:
    """
    Conduct a controlled experiment to detect TLS fingerprinting using a single,
    randomly chosen browser identity for both requests.
    """
    results: dict[str, Any] = {"python_request_blocked": None, "browser_request_blocked": None}
    chosen_identity = random.choice(MODERN_BROWSER_IDENTITIES)
    user_agent = chosen_identity.get("User-Agent", "")

    try:
        resp = await afetch(
            method="GET",
            url=url,
            headers=chosen_identity,
            timeout=20,
            allow_redirects=True,
        )
        try:
            status = getattr(resp, "status_code", None)
            if status is None:
                status = getattr(resp, "status", 0)
            results["python_request_blocked"] = int(status or 0) >= 400
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
            else:
                close = getattr(resp, "close", None)
                if callable(close):
                    close()
    except Exception:
        results["python_request_blocked"] = True

    impersonate_target = get_impersonate_target(user_agent)
    if AsyncSession is None:
        results["browser_request_blocked"] = None
        results["error_code"] = "missing_dependency"
        results["error_message"] = "curl-cffi is required for TLS impersonation."
        return results

    try:
        async with AsyncSession(impersonate=impersonate_target) as session:
            response = await session.get(url, headers=chosen_identity, timeout=20, allow_redirects=True)
            results["browser_request_blocked"] = response.status_code >= 400
    except Exception:
        results["browser_request_blocked"] = True

    return results


async def analyze_tls_fingerprint(url: str) -> dict[str, Any]:
    """
    Main entry point. Run the TLS test and interpret the results.
    """
    test_results = await _run_tls_test(url)

    if test_results.get("error_code") == "missing_dependency":
        return {
            "status": "error",
            "message": test_results["error_message"],
            "error_code": test_results["error_code"],
        }

    python_blocked = test_results["python_request_blocked"]
    browser_blocked = test_results["browser_request_blocked"]

    if python_blocked and not browser_blocked:
        return {
            "status": "active",
            "details": "Site blocks standard Python clients but allows browser-like clients.",
        }
    if not python_blocked and not browser_blocked:
        return {"status": "inactive", "details": "Site does not appear to block based on TLS fingerprint."}
    return {
        "status": "inconclusive",
        "details": "Could not determine fingerprinting status; site may be blocking all requests.",
    }
