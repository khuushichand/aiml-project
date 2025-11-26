"""
Watchlists suite configuration.

For these tests we need the full app profile (not the minimal test app) so
the watchlists router is registered. This fixture flips the relevant env vars
before any tests import the FastAPI app.
"""

import os
import sys
import importlib

import pytest


@pytest.fixture(scope="session", autouse=True)
def enable_full_app_for_watchlists():
    orig_minimal = os.getenv("MINIMAL_TEST_APP")
    orig_disable = os.getenv("ROUTES_DISABLE")
    orig_enable = os.getenv("ROUTES_ENABLE")

    # Force full router set so /api/v1/watchlists/* endpoints are available
    os.environ["MINIMAL_TEST_APP"] = "0"

    # Ensure watchlists routes are not disabled and explicitly enabled
    disable = os.getenv("ROUTES_DISABLE", "")
    disable_parts = [p.strip() for p in disable.replace(" ", ",").split(",") if p.strip()]
    disable_parts = [p for p in disable_parts if p.lower() != "watchlists"]
    os.environ["ROUTES_DISABLE"] = ",".join(dict.fromkeys(disable_parts))

    enable = os.getenv("ROUTES_ENABLE", "")
    enable_parts = [p.strip() for p in enable.replace(" ", ",").split(",") if p.strip()]
    if "watchlists" not in {p.lower() for p in enable_parts}:
        enable_parts.append("watchlists")
    os.environ["ROUTES_ENABLE"] = ",".join(dict.fromkeys(enable_parts))

    # Reload app module so the new env is observed even if it was imported earlier
    sys.modules.pop("tldw_Server_API.app.main", None)
    importlib.invalidate_caches()

    yield

    # Restore prior env so other suites keep their defaults
    if orig_minimal is None:
        os.environ.pop("MINIMAL_TEST_APP", None)
    else:
        os.environ["MINIMAL_TEST_APP"] = orig_minimal

    if orig_disable is None:
        os.environ.pop("ROUTES_DISABLE", None)
    else:
        os.environ["ROUTES_DISABLE"] = orig_disable

    if orig_enable is None:
        os.environ.pop("ROUTES_ENABLE", None)
    else:
        os.environ["ROUTES_ENABLE"] = orig_enable

    sys.modules.pop("tldw_Server_API.app.main", None)
    importlib.invalidate_caches()
