"""
Simple SSE client to stream A/B test progress updates.

Usage:
  python Helper_Scripts/Examples/abtest_sse_client.py --base http://localhost:8000 --test-id abtest_123 --api-key YOUR_KEY
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse


def _ensure_repo_root() -> None:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "tldw_Server_API").is_dir():
            p = str(parent)
            if p not in sys.path:
                sys.path.insert(0, p)
            return


def _configure_local_egress(url: str) -> None:
    try:
        parsed = urlparse(url)
    except Exception:
        return
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "0.0.0.0"} or host.startswith("127.") or host == "::1":
        os.environ.setdefault("WORKFLOWS_EGRESS_BLOCK_PRIVATE", "false")
        if "WORKFLOWS_EGRESS_ALLOWED_PORTS" not in os.environ:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            os.environ["WORKFLOWS_EGRESS_ALLOWED_PORTS"] = f"{port},80,443"


_ensure_repo_root()

try:
    from tldw_Server_API.app.core import http_client
    from tldw_Server_API.app.core.http_client import RetryPolicy
except ImportError as err:
    print("tldw_Server_API not available; run from the repo root or set PYTHONPATH.", file=sys.stderr)
    raise SystemExit(1) from err


async def stream_events(base_url: str, test_id: str, api_key: str) -> None:
    url = f"{base_url.rstrip('/')}/api/v1/evaluations/embeddings/abtest/{test_id}/events"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    retry_policy = RetryPolicy(attempts=3)
    async for event in http_client.astream_sse(
        url=url,
        headers=headers,
        retry=retry_policy,
        timeout=30.0,
    ):
        data = (event.data or "").strip()
        if data:
            print(data)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True, help='Base server URL, e.g., http://localhost:8000')
    ap.add_argument('--test-id', required=True, help='AB test ID')
    ap.add_argument('--api-key', default='', help='API key or JWT token')
    args = ap.parse_args()
    _configure_local_egress(args.base)
    try:
        asyncio.run(stream_events(args.base, args.test_id, args.api_key))
    finally:
        try:
            asyncio.run(http_client.shutdown_http_client())
        except Exception as exc:
            print(f"Warning: failed to shut down HTTP client: {exc}", file=sys.stderr)
