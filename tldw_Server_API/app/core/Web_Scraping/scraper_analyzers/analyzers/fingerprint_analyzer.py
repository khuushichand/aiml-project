from __future__ import annotations

import json
import random
from typing import Any, Dict, List

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
except ImportError:  # pragma: no cover - optional dependency guard
    PlaywrightTimeoutError = TimeoutError  # type: ignore[misc,assignment]
    sync_playwright = None

from ..utils.browser_identities import MODERN_BROWSER_IDENTITIES


KNOWN_BOT_DETECTION_SCRIPTS: Dict[str, List[str]] = {
    "PerimeterX (HUMAN)": [
        "client.perimeterx.net",
        "px-cdn.net",
        "collector-px.perimeterx.net",
    ],
    "DataDome": [
        "datadome.co/js",
        "api.datadome.co/js",
        "js.datadome.co",
    ],
    "Akamai Bot Manager": [
        "akam-bm.net",
        "ak-bm.net",
        "ds-aksb-a.akamaihd.net",
    ],
    "Cloudflare Bot Management": [
        "/cf-challenge/",
        "cdn-cgi/challenge-platform",
        "cf_bm",
    ],
    "Imperva (Incapsula)": [
        "incapsula.com",
        "/_Incapsula_Resource",
    ],
    "Kasada": [
        "api.kasada.io",
        "/kasada-api/",
    ],
    "Shape Security (F5)": [
        "shapeshifter.io",
        "shape-only.com",
        "/F5-shape-security-js",
    ],
    "CHEQ": [
        "cheqzone.com",
        "api.cheq.ai",
    ],
    "Radware Bot Manager": [
        "radwarebotmanager.com",
        "/rbm/rbm.js",
    ],
}

KNOWN_BOT_GLOBAL_OBJECTS: Dict[str, List[str]] = {
    "PerimeterX (HUMAN)": ["_px", "PX", "px"],
    "DataDome": ["ddjskey", "datadome"],
    "Akamai Bot Manager": ["bmak"],
    "Imperva (Incapsula)": ["Reese84"],
    "Kasada": ["kasada"],
    "Shape Security (F5)": ["_sd"],
}

JS_PROBE_SCRIPT = """
() => {
    window.__caniscrape_listeners_log = [];
    const log = window.__caniscrape_listeners_log;

    const originalAddEventListener = EventTarget.prototype.addEventListener;
    const suspiciousEvents = ['mousemove', 'mousedown', 'mouseup', 'keydown', 'keyup', 'scroll', 'touchstart', 'touchend'];

    EventTarget.prototype.addEventListener = function(type, listener, options) {
        if (suspiciousEvents.includes(type)) {
            log.push(type);
        }
        return originalAddEventListener.call(this, type, listener, options);
    };
};
"""


def analyze_fingerprinting(url: str) -> Dict[str, Any]:
    """
    Probe a page for advanced fingerprinting/bot detection signals.
    """
    if sync_playwright is None:
        return {
            "status": "error",
            "message": "playwright is not installed; install the 'scrape-analyzers[browser]' extra.",
            "error_code": "missing_dependency",
        }

    results: Dict[str, Any] = {
        "status": "error",
        "message": "Analysis did not complete.",
        "detected_services": [],
        "canvas_fingerprinting_signal": False,
        "behavioral_listeners_detected": [],
    }

    captured_script_urls: set[str] = set()
    browser_identity = random.choice(MODERN_BROWSER_IDENTITIES)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(extra_http_headers=browser_identity)
                page.route(
                    "**/*",
                    lambda route: route.abort()
                    if route.request.resource_type in ["image", "font", "media"]
                    else route.continue_(),
                )
                page.add_init_script(JS_PROBE_SCRIPT)
                page.on("request", lambda request: captured_script_urls.add(request.url))

                page.goto(url, wait_until="load", timeout=30_000)
                page.wait_for_timeout(3_000)

                static_probes = page.evaluate(
                    f"""
                () => {{
                    const results = {{
                        canvas_patched: HTMLCanvasElement.prototype.toDataURL.toString().indexOf('native code') === -1,
                        found_globals: []
                    }};

                    const global_objects = {json.dumps(KNOWN_BOT_GLOBAL_OBJECTS)};

                    for (const [service, objects] of Object.entries(global_objects)) {{
                        for (const obj_name of objects) {{
                            if (window[obj_name]) {{
                                results.found_globals.push(service);
                                break;
                            }}
                        }}
                    }}
                    return results;
                }}
                """
                )
                listener_log = page.evaluate("() => window.__caniscrape_listeners_log")
            finally:
                browser.close()

        for service, patterns in KNOWN_BOT_DETECTION_SCRIPTS.items():
            for url_part in patterns:
                if any(url_part in script_url for script_url in captured_script_urls):
                    if service not in results["detected_services"]:
                        results["detected_services"].append(service)

        if static_probes.get("canvas_patched"):
            results["canvas_fingerprinting_signal"] = True

        for service in static_probes.get("found_globals", []) or []:
            if service not in results["detected_services"]:
                results["detected_services"].append(service)

        if listener_log:
            results["behavioral_listeners_detected"] = sorted(set(listener_log))

        results["status"] = "success"
        results["message"] = "Analysis complete."
        return results
    except PlaywrightTimeoutError:
        results["message"] = "Page load timed out."
        return results
    except Exception as exc:  # pragma: no cover - defensive catch
        results["message"] = str(exc)
        return results
