#!/usr/bin/env python3
"""Hosted staging preflight checks for the SaaS launch profile."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from Helper_Scripts.validate_hosted_saas_profile import (
    _build_validation_env,
    validate_hosted_profile,
)


FetchResult = tuple[int, str, str]
FetchFn = Callable[[str, float], FetchResult]

SELF_HOST_MARKERS = {
    "/login": ("server url",),
    "/signup": (
        "hosted signup is only available in managed mode",
        "self-host deployments keep account setup inside the local server configuration flow.",
    ),
}
STRICT_HOSTED_MARKERS = {
    "/login": ("hosted tldw keeps the first-run path focused",),
    "/signup": ("create your hosted account",),
}


def _trim(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _decode_body(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def _fetch_url(url: str, timeout: float) -> FetchResult:
    request = Request(url, method="GET")
    request.add_header("Accept", "text/html,application/json")

    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310
            return int(response.getcode()), _decode_body(response.read() or b""), ""
    except HTTPError as exc:
        return int(getattr(exc, "code", 0) or 0), _decode_body(exc.read() or b""), ""
    except URLError as exc:
        return 0, "", f"URL error: {exc}"
    except Exception as exc:  # pragma: no cover - defensive fallback
        return 0, "", f"Request error: {exc}"


def _record(name: str, ok: bool, detail: str) -> None:
    label = "PASS" if ok else "FAIL"
    print(f"[{label}] {name} - {detail}")


def _check_status(name: str, url: str, timeout: float, fetch: FetchFn) -> bool:
    status, body, error = fetch(url, timeout)
    if status == 200:
        _record(name, True, f"status=200 url={url}")
        return True

    detail = error or f"status={status} body={_trim(body)}"
    _record(name, False, detail)
    return False


def _check_public_page(path: str, url: str, timeout: float, strict: bool, fetch: FetchFn) -> bool:
    status, body, error = fetch(url, timeout)
    if status != 200:
        detail = error or f"status={status} body={_trim(body)}"
        _record(path, False, detail)
        return False

    body_lower = body.lower()
    negative_markers = SELF_HOST_MARKERS[path]
    if any(marker in body_lower for marker in negative_markers):
        _record(path, False, "rendered self-host placeholder copy")
        return False

    if strict:
        positive_markers = STRICT_HOSTED_MARKERS[path]
        if not any(marker in body_lower for marker in positive_markers):
            _record(path, False, "hosted copy markers missing in strict mode")
            return False

    _record(path, True, f"status=200 url={url}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run hosted staging preflight checks for the SaaS launch profile."
    )
    parser.add_argument("--env-file", help="Load the hosted env contract from a .env-style file.")
    parser.add_argument("--base-url", help="Public base URL for hosted frontend checks.")
    parser.add_argument(
        "--api-base-url",
        help="Optional API base URL override for health, readiness, and billing checks.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require known hosted copy markers on public auth pages.",
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)

    try:
        validation_env = _build_validation_env(os.environ, args.env_file)
    except (FileNotFoundError, OSError) as exc:
        print(str(exc))
        return 1

    validation_result = validate_hosted_profile(validation_env)
    if not validation_result.ok:
        print("Hosted staging preflight failed hosted profile validation:")
        for key, message in validation_result.errors.items():
            print(f"- {key}: {message}")
        return 1

    base_url = (args.base_url or str(validation_env.get("PUBLIC_WEB_BASE_URL", "")).strip()).rstrip("/")
    if not base_url:
        print("Hosted staging preflight requires --base-url or PUBLIC_WEB_BASE_URL.")
        return 1

    api_base_url = (args.api_base_url or base_url).rstrip("/")
    fetch = _fetch_url

    checks = (
        _check_status("/health", f"{api_base_url}/health", args.timeout, fetch),
        _check_status("/ready", f"{api_base_url}/ready", args.timeout, fetch),
        _check_public_page("/login", f"{base_url}/login", args.timeout, args.strict, fetch),
        _check_public_page("/signup", f"{base_url}/signup", args.timeout, args.strict, fetch),
        _check_status(
            "/api/v1/billing/plans",
            f"{api_base_url}/api/v1/billing/plans",
            args.timeout,
            fetch,
        ),
    )

    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
