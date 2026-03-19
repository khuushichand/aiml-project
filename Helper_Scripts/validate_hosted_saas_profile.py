#!/usr/bin/env python3
"""
Validate the minimum environment contract for the hosted SaaS launch profile.

This script is intentionally narrow. It verifies only the settings that define
the hosted deployment boundary for the first customer-facing release:

- multi-user AuthNZ
- PostgreSQL-backed AuthNZ storage
- production guards enabled
- a public frontend origin for auth emails
- billing redirect hardening locked to the public app host
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse


TRUTHY_VALUES = {"1", "true", "yes", "on", "y"}
HOSTED_PUBLIC_PATH_KEYS = (
    "PUBLIC_PASSWORD_RESET_PATH",
    "PUBLIC_EMAIL_VERIFICATION_PATH",
    "PUBLIC_MAGIC_LINK_PATH",
)


@dataclass(slots=True)
class HostedProfileValidationResult:
    errors: dict[str, str] = field(default_factory=dict)
    warnings: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def _read_text(env: Mapping[str, object], key: str) -> str:
    return str(env.get(key, "") or "").strip()


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in TRUTHY_VALUES


def _is_postgres_database_url(database_url: str) -> bool:
    scheme = urlparse(database_url).scheme.strip().lower()
    return scheme.startswith("postgres")


def _host_matches_allowed_pattern(host: str, pattern: str) -> bool:
    normalized = pattern.strip().lower()
    if not normalized:
        return False
    if normalized.startswith("*."):
        return host.endswith(normalized[1:])
    return host == normalized


def _parse_env_file(env_file: Path) -> dict[str, str]:
    values: dict[str, str] = {}

    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()

    return values


def _build_validation_env(base_env: Mapping[str, str], env_file: str | None) -> Mapping[str, str]:
    values = dict(base_env)
    if not env_file:
        return values

    env_path = Path(env_file)
    if not env_path.is_file():
        raise FileNotFoundError(f"Hosted SaaS env file not found: {env_path}")

    try:
        values.update(_parse_env_file(env_path))
    except OSError as exc:
        raise OSError(f"Failed to read hosted SaaS env file {env_path}: {exc}") from exc

    return values


def validate_hosted_profile(
    env: Mapping[str, object] | None = None,
) -> HostedProfileValidationResult:
    values = env or os.environ
    result = HostedProfileValidationResult()

    auth_mode = _read_text(values, "AUTH_MODE").lower()
    if auth_mode != "multi_user":
        result.errors["AUTH_MODE"] = "Hosted SaaS requires AUTH_MODE=multi_user."

    database_url = _read_text(values, "DATABASE_URL")
    if not database_url:
        result.errors["DATABASE_URL"] = "Hosted SaaS requires DATABASE_URL to be set."
    elif not _is_postgres_database_url(database_url):
        result.errors["DATABASE_URL"] = (
            "Hosted SaaS requires a PostgreSQL DATABASE_URL, not SQLite or another backend."
        )

    if not _is_truthy(_read_text(values, "tldw_production")):
        result.errors["tldw_production"] = (
            "Hosted SaaS requires tldw_production=true so production guardrails stay enabled."
        )

    public_web_base_url = _read_text(values, "PUBLIC_WEB_BASE_URL")
    public_host = ""
    if not public_web_base_url:
        result.errors["PUBLIC_WEB_BASE_URL"] = (
            "Hosted SaaS requires PUBLIC_WEB_BASE_URL so auth emails point at the public app."
        )
    else:
        parsed_public_url = urlparse(public_web_base_url)
        if parsed_public_url.scheme.lower() != "https":
            result.errors["PUBLIC_WEB_BASE_URL"] = (
                "Hosted SaaS requires PUBLIC_WEB_BASE_URL to use https."
            )
        elif not parsed_public_url.hostname:
            result.errors["PUBLIC_WEB_BASE_URL"] = (
                "PUBLIC_WEB_BASE_URL must include a valid hostname."
            )
        elif parsed_public_url.path not in {"", "/"}:
            result.errors["PUBLIC_WEB_BASE_URL"] = (
                "PUBLIC_WEB_BASE_URL must be an origin only, without an extra path segment."
            )
        else:
            public_host = parsed_public_url.hostname.lower()

    for key in HOSTED_PUBLIC_PATH_KEYS:
        custom_path = _read_text(values, key)
        if custom_path and not custom_path.startswith("/"):
            result.errors[key] = f"{key} must start with '/'."

    if not _is_truthy(_read_text(values, "BILLING_REDIRECT_ALLOWLIST_REQUIRED")):
        result.errors["BILLING_REDIRECT_ALLOWLIST_REQUIRED"] = (
            "Hosted SaaS requires BILLING_REDIRECT_ALLOWLIST_REQUIRED=true."
        )

    if not _is_truthy(_read_text(values, "BILLING_REDIRECT_REQUIRE_HTTPS")):
        result.errors["BILLING_REDIRECT_REQUIRE_HTTPS"] = (
            "Hosted SaaS requires BILLING_REDIRECT_REQUIRE_HTTPS=true."
        )

    raw_redirect_hosts = _read_text(values, "BILLING_ALLOWED_REDIRECT_HOSTS")
    allowed_redirect_hosts = [
        entry.strip().lower()
        for entry in raw_redirect_hosts.split(",")
        if entry.strip()
    ]
    if not allowed_redirect_hosts:
        result.errors["BILLING_ALLOWED_REDIRECT_HOSTS"] = (
            "Hosted SaaS requires BILLING_ALLOWED_REDIRECT_HOSTS to include the public app host."
        )
    elif public_host and not any(
        _host_matches_allowed_pattern(public_host, pattern)
        for pattern in allowed_redirect_hosts
    ):
        result.errors["BILLING_ALLOWED_REDIRECT_HOSTS"] = (
            f"BILLING_ALLOWED_REDIRECT_HOSTS must allow the PUBLIC_WEB_BASE_URL host '{public_host}'."
        )

    return result


def main(argv: list[str] | None = None) -> int:
    raw_argv = argv or sys.argv
    parser = argparse.ArgumentParser(
        description="Validate the minimum environment contract for the hosted SaaS launch profile."
    )
    parser.add_argument(
        "--env-file",
        help="Load KEY=value pairs from a .env-style file before validating the hosted profile.",
    )
    args = parser.parse_args(raw_argv[1:])

    try:
        validation_env = _build_validation_env(os.environ, args.env_file)
    except (FileNotFoundError, OSError) as exc:
        print(str(exc))
        return 1

    result = validate_hosted_profile(validation_env)

    if result.ok:
        print("Hosted SaaS profile validation passed.")
        return 0

    print("Hosted SaaS profile validation failed:")
    for key, message in result.errors.items():
        print(f"- {key}: {message}")
    for key, message in result.warnings.items():
        print(f"- warning {key}: {message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
