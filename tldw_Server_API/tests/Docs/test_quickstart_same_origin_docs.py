"""Contract tests for same-origin quickstart documentation wording."""

from pathlib import Path

import pytest


def _require(condition: bool, message: str) -> None:
    """Fail with a descriptive assertion message when a contract is broken."""
    if not condition:
        pytest.fail(message)


def _read(path: str) -> str:
    """Read a UTF-8 text file from the repository root."""
    return Path(path).read_text(encoding="utf-8")


def test_root_readme_quickstart_defaults_to_same_origin_webui_proxy() -> None:
    """README quickstart should describe the same-origin WebUI proxy default."""
    text = _read("README.md")
    _require(
        "same-origin browser API requests through the WebUI proxy" in text,
        "README quickstart should say the default Docker + WebUI path uses same-origin browser API requests through the WebUI proxy",
    )
    _require(
        "advanced/custom-host path for LAN, reverse-proxy, or custom-domain browser access" in text,
        "README quickstart should position LAN or custom-host browser access as the advanced path",
    )
    _require(
        "NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=advanced NEXT_PUBLIC_API_URL=http://YOUR_HOST_OR_DOMAIN:8000"
        in text,
        "README quickstart should document the full advanced/custom-host override pair",
    )


def test_getting_started_guides_treat_lan_custom_host_as_advanced() -> None:
    """Getting Started docs should separate default quickstart from advanced host config."""
    index_text = _read("Docs/Getting_Started/README.md")
    profile_text = _read("Docs/Getting_Started/Profile_Docker_Single_User.md")

    _require(
        "same-origin browser API requests through the WebUI proxy" in index_text,
        "Getting Started index should describe the default same-origin WebUI proxy behavior",
    )
    _require(
        "LAN/custom-host browser access as advanced configuration" in index_text,
        "Getting Started index should frame LAN/custom-host browser access as advanced configuration",
    )
    _require(
        "same-origin browser API requests through the WebUI proxy" in profile_text,
        "Docker single-user profile should describe the default same-origin WebUI proxy behavior",
    )
    _require(
        "LAN/custom-host browser access as advanced configuration" in profile_text,
        "Docker single-user profile should frame LAN/custom-host browser access as advanced configuration",
    )
    _require(
        "NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=advanced" in profile_text,
        "Docker single-user profile should point advanced/custom-host readers to the advanced deployment mode override",
    )


def test_single_user_profile_runs_webui_quickstart_and_verifies_webui() -> None:
    """Docker single-user profile should launch and verify the WebUI quickstart path."""
    profile_text = _read("Docs/Getting_Started/Profile_Docker_Single_User.md")

    _require(
        "make quickstart" in profile_text or "docker-compose.webui.yml" in profile_text,
        "Docker single-user profile should launch the WebUI quickstart path instead of the API-only compose stack",
    )
    _require(
        "http://127.0.0.1:8080" in profile_text,
        "Docker single-user profile should verify the WebUI endpoint on 127.0.0.1:8080",
    )


def test_root_readme_no_make_webui_example_uses_full_advanced_override_pair() -> None:
    """README no-make WebUI example should show the full advanced/custom-host override pair."""
    text = _read("README.md")

    _require(
        '# $env:NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE="advanced"' in text,
        "README no-make WebUI example should set NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=advanced for non-localhost browser access",
    )
    _require(
        '# $env:NEXT_PUBLIC_API_URL="http://YOUR_HOST_OR_DOMAIN:8000"' in text,
        "README no-make WebUI example should set NEXT_PUBLIC_API_URL for non-localhost browser access",
    )


def test_website_and_frontend_readmes_match_same_origin_quickstart_story() -> None:
    """Website quick start and frontend README should mirror the default networking story."""
    website_text = _read("Docs/Website/index.html")
    frontend_text = _read("apps/tldw-frontend/README.md")

    _require(
        "same-origin browser API requests through the WebUI proxy" in website_text,
        "Website quick start should say the default path uses same-origin browser API requests through the WebUI proxy",
    )
    _require(
        "API-only Docker and local dev remain supported alternative setup profiles." in website_text,
        "Website quick start should keep API-only Docker and local dev as normal setup profiles",
    )
    _require(
        "LAN/custom-host browser access is the advanced configuration path." in website_text,
        "Website quick start should frame LAN/custom-host browser access as advanced configuration",
    )
    _require(
        "Quickstart networking (default Docker WebUI path)" in frontend_text,
        "Frontend README should explain the default quickstart networking path",
    )
    _require(
        "Advanced/custom-host networking" in frontend_text,
        "Frontend README should explain the advanced/custom-host networking path separately",
    )
    _require(
        "NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=advanced" in frontend_text,
        "Frontend README should document the advanced deployment mode override for custom-host networking",
    )
