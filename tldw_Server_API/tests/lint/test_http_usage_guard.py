import os
import re
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2] / "app"

# Files that are explicitly allowed to use direct requests/httpx (rare, justified cases)
ALLOWED = {
    # Centralized client and streaming utilities
    "tldw_Server_API/app/core/http_client.py",
    "tldw_Server_API/app/core/LLM_Calls/streaming.py",
    "tldw_Server_API/app/core/LLM_Calls/LLM_API_Calls.py",
    # Some providers/tests keep specific seams; reviewed separately
    "tldw_Server_API/app/core/Web_Scraping/WebSearch_APIs.py",
    "tldw_Server_API/app/services/jobs_webhooks_service.py",
}


PATTERNS = [
    re.compile(r"\brequests\.(get|post|put|delete|head|options|patch|request)\s*\("),
    re.compile(r"\brequests\.Session\s*\("),
    re.compile(r"\bhttpx\.(AsyncClient|Client)\s*\("),
    re.compile(r"\bhttpx\.(get|post|put|delete|head|options|patch|request|stream)\s*\("),
]


def _is_allowed(path: Path) -> bool:
    rel = str(path)
    return any(rel.endswith(allow) for allow in ALLOWED)


def test_no_direct_http_usage_outside_approved_files():
    # Allow incremental rollout: only enforce when explicitly enabled in CI
    if os.getenv("ENFORCE_HTTP_GUARD", "0") not in {"1", "true", "TRUE"}:
        import pytest
        pytest.skip("HTTP guard enforcement disabled (set ENFORCE_HTTP_GUARD=1 to enable)")
    offending = []
    for py in APP_ROOT.rglob("*.py"):
        # Skip tests and migrations
        if "/tests/" in str(py):
            continue
        rel = py.as_posix()
        if _is_allowed(py):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        for pat in PATTERNS:
            if pat.search(text):
                offending.append(rel)
                break
    assert not offending, (
        "Direct requests/httpx usage found outside approved files. "
        "Please use tldw_Server_API.app.core.http_client helpers. Offenders: "
        + ", ".join(sorted(offending))
    )
