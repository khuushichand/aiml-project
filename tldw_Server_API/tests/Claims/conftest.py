import os

import pytest


_DISABLE_ROUTES = ("media", "audio", "audio-websocket")


def _merge_routes_disable(existing: str | None) -> str:
    parts = []
    seen = set()
    for raw in ((existing or "").split(",") + list(_DISABLE_ROUTES)):
        token = (raw or "").strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        parts.append(token)
    return ",".join(parts)


@pytest.fixture(scope="session", autouse=True)
def _claims_suite_minimal_app_env():
    original = {
        "MINIMAL_TEST_APP": os.environ.get("MINIMAL_TEST_APP"),
        "ROUTES_DISABLE": os.environ.get("ROUTES_DISABLE"),
    }
    os.environ["MINIMAL_TEST_APP"] = "1"
    os.environ["ROUTES_DISABLE"] = _merge_routes_disable(original["ROUTES_DISABLE"])
    try:
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
