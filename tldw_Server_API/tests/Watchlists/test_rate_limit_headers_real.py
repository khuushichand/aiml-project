import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


SCRIPT = r"""
import os
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.config import API_V1_PREFIX

# Build app with RG middleware
from tldw_Server_API.app.api.v1.endpoints import watchlists as wl
from tldw_Server_API.app.core.Resource_Governance.middleware_simple import RGSimpleMiddleware

async def _override_user():
    return User(id=930, username="rluser", email=None, is_active=True)

app = FastAPI()
app.add_middleware(RGSimpleMiddleware)
app.include_router(wl.router, prefix=f"{API_V1_PREFIX}")
app.dependency_overrides[get_request_user] = _override_user

with TestClient(app) as c:
    token = uuid4().hex[:10]
    # Minimal OPML import; expect rate-limit headers from middleware/decorator
    opml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<opml version=\"1.0\"><body>"
        f"<outline text=\"Feed {token}\" title=\"Feed {token}\" type=\"rss\" xmlUrl=\"https://example.com/feed-{token}.xml\"/>"
        "</body></opml>"
    )
    files = {"file": ("feeds.opml", opml, "application/xml"), "active": (None, "1")}
    r = c.post("/api/v1/watchlists/sources/import", files=files)
    print("STATUS_OPML:", r.status_code)
    for h in ("X-RateLimit-Limit","X-RateLimit-Remaining","X-RateLimit-Reset","Retry-After"):
        if h in r.headers:
            print("HDR_OPML:", h, r.headers[h])

    # Build source/job then exercise filters endpoints under the same non-test env.
    s = c.post(
        "/api/v1/watchlists/sources",
        json={"name": f"RateLimit Feed {token}", "url": f"https://example.com/feed2-{token}.xml", "source_type": "rss"},
    )
    print("STATUS_SOURCE:", s.status_code)
    j = c.post(
        "/api/v1/watchlists/jobs",
        json={"name": f"RateLimit Job {token}", "scope": {"sources": [s.json()["id"]]}, "active": True},
    )
    print("STATUS_JOB:", j.status_code)
    job_id = j.json()["id"]

    rp = c.patch(
        f"/api/v1/watchlists/jobs/{job_id}/filters",
        json={"filters": [{"type": "keyword", "action": "include", "value": {"keywords": ["hello"], "match": "any"}}]},
    )
    print("STATUS_FILTERS_PATCH:", rp.status_code)
    for h in ("X-RateLimit-Limit","X-RateLimit-Remaining","X-RateLimit-Reset","Retry-After"):
        if h in rp.headers:
            print("HDR_FILTERS_PATCH:", h, rp.headers[h])

    ra = c.post(
        f"/api/v1/watchlists/jobs/{job_id}/filters:add",
        json={"filters": [{"type": "regex", "action": "exclude", "value": {"pattern": "spam", "flags": "i"}}]},
    )
    print("STATUS_FILTERS_ADD:", ra.status_code)
    for h in ("X-RateLimit-Limit","X-RateLimit-Remaining","X-RateLimit-Reset","Retry-After"):
        if h in ra.headers:
            print("HDR_FILTERS_ADD:", h, ra.headers[h])
"""


def test_rate_limit_headers_real_middleware(monkeypatch, tmp_path):


     # Ensure a clean env for the subprocess: disable all test bypass flags
    env = dict(os.environ)
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("TEST_MODE", None)
    env.pop("TLDW_TEST_MODE", None)
    env.pop("WATCHLISTS_DISABLE_RATE_LIMITS", None)
    policy_path = Path(__file__).resolve().parents[2] / "Config_Files" / "resource_governor_policies.yaml"
    env["RG_POLICY_PATH"] = str(policy_path)
    # Route user DB to a unique writable temp dir to avoid cross-run state leakage.
    base_dir = tmp_path / "test_user_dbs_rate_limits_real"
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
    assert "STATUS_OPML: 200" in out
    assert "STATUS_SOURCE: 200" in out
    assert "STATUS_JOB: 200" in out
    assert "STATUS_FILTERS_PATCH: 200" in out
    assert "STATUS_FILTERS_ADD: 200" in out
    # Deterministically require at least the Limit header when middleware is active.
    assert "HDR_OPML: X-RateLimit-Limit" in out
    assert "HDR_FILTERS_PATCH: X-RateLimit-Limit" in out
    assert "HDR_FILTERS_ADD: X-RateLimit-Limit" in out
