import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


SCRIPT = r"""
import os
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.config import API_V1_PREFIX

# Build app with real SlowAPI middleware
from tldw_Server_API.app.api.v1.endpoints import watchlists as wl
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from tldw_Server_API.app.api.v1.API_Deps.rate_limiting import limiter as _global_limiter

async def _override_user():
    return User(id=930, username="rluser", email=None, is_active=True)

app = FastAPI()
app.state.limiter = _global_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.include_router(wl.router, prefix=f"{API_V1_PREFIX}")
app.dependency_overrides[get_request_user] = _override_user

with TestClient(app) as c:
    # Minimal OPML import; expect rate-limit headers from middleware/decorator
    opml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<opml version=\"1.0\"><body>"
        "<outline text=\"Feed\" title=\"Feed\" type=\"rss\" xmlUrl=\"https://example.com/feed.xml\"/>"
        "</body></opml>"
    )
    files = {"file": ("feeds.opml", opml, "application/xml"), "active": (None, "1")}
    r = c.post("/api/v1/watchlists/sources/import", files=files)
    print("STATUS:", r.status_code)
    for h in ("X-RateLimit-Limit","X-RateLimit-Remaining","X-RateLimit-Reset","Retry-After"):
        if h in r.headers:
            print("HDR:", h, r.headers[h])
"""


def test_rate_limit_headers_real_middleware(monkeypatch, tmp_path):
    # Ensure a clean env for the subprocess: disable all test bypass flags
    env = dict(os.environ)
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("TEST_MODE", None)
    env.pop("TLDW_TEST_MODE", None)
    env.pop("WATCHLISTS_DISABLE_RATE_LIMITS", None)
    # Route user DB to a writable temp dir
    base_dir = Path.cwd() / "Databases" / "test_user_dbs_rate_limits_real"
    base_dir.mkdir(parents=True, exist_ok=True)
    env["USER_DB_BASE_DIR"] = str(base_dir)
    # Run a short inline script that constructs the app and prints headers
    proc = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path.cwd()),
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "STATUS: 200" in out
    # Deterministically require at least the Limit header when middleware is active
    assert "HDR: X-RateLimit-Limit" in out
