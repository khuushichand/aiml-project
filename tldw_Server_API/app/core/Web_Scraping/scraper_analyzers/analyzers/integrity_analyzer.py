from __future__ import annotations

from typing import Any, Dict, List

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
except ImportError:  # pragma: no cover - optional dependency guard
    PlaywrightTimeoutError = TimeoutError  # type: ignore[misc,assignment]
    sync_playwright = None


FUNCTIONS_TO_CHECK: List[str] = [
    "HTMLCanvasElement.prototype.toDataURL",
    "HTMLCanvasElement.prototype.getImageData",
    "HTMLCanvasElement.prototype.getContext",
    "navigator.plugins.length",
    "navigator.mimeTypes.length",
    "navigator.webdriver",
    "window.fetch",
    "XMLHttpRequest.prototype.open",
    "Date.now",
    "performance.now",
    "console.log",
]

FUNCTION_SUSPICION_MAP: Dict[str, str] = {
    "HTMLCanvasElement.prototype.toDataURL": "Strong indicator of Canvas fingerprinting.",
    "HTMLCanvasElement.prototype.getImageData": "Strong indicator of Canvas fingerprinting.",
    "HTMLCanvasElement.prototype.getContext": "Strong indicator of Canvas fingerprinting.",
    "navigator.plugins.length": "Indicator of headless browser evasion (plugin spoofing).",
    "navigator.mimeTypes.length": "Indicator of headless browser evasion (mime type spoofing).",
    "navigator.webdriver": "Indicator of headless browser evasion.",
    "window.fetch": "Indicator of network traffic monitoring.",
    "XMLHttpRequest.prototype.open": "Indicator of network traffic monitoring.",
    "Date.now": "Indicator of timing/behavioral analysis.",
    "performance.now": "Indicator of timing/behavioral analysis.",
    "console.log": "Indicator of anti-debugging techniques.",
}


def _get_function_signatures(page, functions: List[str]) -> Dict[str, str]:
    """
    Execute JS in the page to get string representations of functions.
    """
    js_script = """
    (func_paths) => {
        const signatures = {};
        for (const path of func_paths) {
            try {
                let obj = window;
                const parts = path.split('.');
                for (let i = 0; i < parts.length; i++) {
                    if (obj === undefined || obj === null) {
                        break;
                    }
                    obj = obj[parts[i]];
                }
                signatures[path] = String(obj);
            } catch (err) {
                signatures[path] = 'Error: ' + err.message;
            }
        }
        return signatures;
    }
    """
    return page.evaluate(js_script, functions)


def analyze_function_integrity(url: str) -> Dict[str, Any]:
    """
    Compare critical browser function signatures between a clean page and the target.
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
        "modified_functions": {},
    }

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                clean_context = browser.new_context()
                clean_page = clean_context.new_page()
                clean_page.route(
                    "**/*",
                    lambda route: route.abort()
                    if route.request.resource_type in ["image", "font", "media"]
                    else route.continue_(),
                )
                clean_page.goto("about:blank")
                clean_signatures = _get_function_signatures(clean_page, FUNCTIONS_TO_CHECK)
                clean_context.close()

                target_context = browser.new_context()
                target_page = target_context.new_page()
                target_page.route(
                    "**/*",
                    lambda route: route.abort()
                    if route.request.resource_type in ["image", "font", "media"]
                    else route.continue_(),
                )
                target_page.goto(url, wait_until="load", timeout=30_000)
                target_signatures = _get_function_signatures(target_page, FUNCTIONS_TO_CHECK)
                target_context.close()
            finally:
                browser.close()

        modified: Dict[str, str] = {}
        for func_path, clean_sig in clean_signatures.items():
            target_sig = target_signatures.get(func_path)
            if clean_sig != target_sig:
                modified[func_path] = FUNCTION_SUSPICION_MAP.get(func_path, "Unknown modification.")

        results["status"] = "success"
        results["message"] = "Analysis complete."
        results["modified_functions"] = modified
        return results
    except PlaywrightTimeoutError:
        results["message"] = "Page load timed out."
        return results
    except Exception as exc:  # pragma: no cover - defensive catch
        results["message"] = str(exc)
        return results
