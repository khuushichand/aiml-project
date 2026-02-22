#!/usr/bin/env python3
"""
Smoke checks for Jobs unification staging validation.

Validates:
- /api/v1/jobs/prune (dry_run)
- /api/v1/jobs/stats
- /api/v1/jobs/list
- /api/v1/embeddings/orchestrator/summary (optional)
- Optional non-admin access check on /api/v1/jobs/list
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _env_first(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value and str(value).strip():
            return str(value).strip()
    return None


def _build_headers(api_key: Optional[str], bearer: Optional[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["X-API-KEY"] = api_key
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    return headers


def _decode_body(raw: bytes) -> str:
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return str(raw)


def _request_json(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[Dict[str, Any]],
    timeout: float,
) -> Tuple[int, Optional[Any], str]:
    payload = None
    req_headers = dict(headers)
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = Request(url, data=payload, method=method)
    for key, value in req_headers.items():
        req.add_header(key, value)
    try:
        with urlopen(req, timeout=timeout) as resp:  # nosec B310
            status = int(resp.getcode())
            raw = _decode_body(resp.read() or b"")
    except HTTPError as exc:
        status = int(getattr(exc, "code", 0) or 0)
        raw = _decode_body(exc.read() or b"")
    except URLError as exc:
        return 0, None, f"URL error: {exc}"
    except Exception as exc:
        return 0, None, f"Request error: {exc}"

    data = None
    if raw:
        try:
            data = json.loads(raw)
        except Exception:
            data = None
    return status, data, raw


def _record(results: list[Tuple[str, bool, bool, str]], name: str, ok: bool, detail: str, *, skipped: bool = False) -> None:
    results.append((name, ok, skipped, detail))
    label = "SKIP" if skipped else ("PASS" if ok else "FAIL")
    print(f"[{label}] {name} - {detail}")


def _trim(text: str, limit: int = 240) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Smoke checks for Jobs unification staging validation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--base-url", default=_env_first("TLDW_BASE_URL", "BASE_URL") or "http://127.0.0.1:8000")
    parser.add_argument("--api-key", default=_env_first("SINGLE_USER_API_KEY", "X_API_KEY", "TLDW_API_KEY"))
    parser.add_argument("--bearer", default=_env_first("ADMIN_BEARER", "TLDW_BEARER"))
    parser.add_argument("--nonadmin-api-key", default=_env_first("NONADMIN_API_KEY"))
    parser.add_argument("--nonadmin-bearer", default=_env_first("NONADMIN_BEARER"))
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--skip-prune", action="store_true", help="Skip jobs/prune dry-run check")
    parser.add_argument("--skip-jobs-admin", action="store_true", help="Skip jobs/stats and jobs/list checks")
    parser.add_argument("--skip-orchestrator", action="store_true", help="Skip embeddings orchestrator summary check")
    parser.add_argument("--require-orchestrator", action="store_true", help="Fail if orchestrator summary is forbidden")
    args = parser.parse_args(argv)

    base_url = args.base_url.rstrip("/")
    admin_headers = _build_headers(args.api_key, args.bearer)
    nonadmin_headers = _build_headers(args.nonadmin_api_key, args.nonadmin_bearer)

    if not admin_headers.get("X-API-KEY") and not admin_headers.get("Authorization"):
        print("[WARN] No admin credentials provided; admin checks may fail (set --api-key or --bearer).")

    results: list[Tuple[str, bool, bool, str]] = []

    if args.skip_prune:
        _record(results, "jobs/prune dry-run", ok=True, skipped=True, detail="skipped by flag")
    else:
        url = f"{base_url}/api/v1/jobs/prune"
        body = {"statuses": ["completed", "failed", "cancelled"], "older_than_days": 30, "dry_run": True}
        status, data, raw = _request_json("POST", url, admin_headers, body, args.timeout)
        if status == 200 and isinstance(data, dict) and "deleted" in data:
            _record(results, "jobs/prune dry-run", ok=True, detail=f"deleted={data.get('deleted')}")
        else:
            _record(results, "jobs/prune dry-run", ok=False, detail=f"status={status} body={_trim(raw)}")

    if args.skip_jobs_admin:
        _record(results, "jobs/stats", ok=True, skipped=True, detail="skipped by flag")
        _record(results, "jobs/list", ok=True, skipped=True, detail="skipped by flag")
    else:
        url = f"{base_url}/api/v1/jobs/stats"
        status, data, raw = _request_json("GET", url, admin_headers, None, args.timeout)
        if status == 200 and isinstance(data, list):
            _record(results, "jobs/stats", ok=True, detail=f"items={len(data)}")
        else:
            _record(results, "jobs/stats", ok=False, detail=f"status={status} body={_trim(raw)}")

        url = f"{base_url}/api/v1/jobs/list?limit=1"
        status, data, raw = _request_json("GET", url, admin_headers, None, args.timeout)
        if status == 200 and isinstance(data, list):
            _record(results, "jobs/list", ok=True, detail=f"items={len(data)}")
        else:
            _record(results, "jobs/list", ok=False, detail=f"status={status} body={_trim(raw)}")

    if args.skip_orchestrator:
        _record(results, "embeddings/orchestrator/summary", ok=True, skipped=True, detail="skipped by flag")
    else:
        url = f"{base_url}/api/v1/embeddings/orchestrator/summary"
        status, data, raw = _request_json("GET", url, admin_headers, None, args.timeout)
        if status in (401, 403) and not args.require_orchestrator:
            _record(
                results,
                "embeddings/orchestrator/summary",
                ok=True,
                skipped=True,
                detail=f"forbidden (status={status})",
            )
        elif status == 200 and isinstance(data, dict):
            missing = [key for key in ("queues", "stages", "ts") if key not in data]
            note = f"missing={','.join(missing)}" if missing else "ok"
            _record(results, "embeddings/orchestrator/summary", ok=True, detail=note)
        else:
            _record(results, "embeddings/orchestrator/summary", ok=False, detail=f"status={status} body={_trim(raw)}")

    if nonadmin_headers.get("X-API-KEY") or nonadmin_headers.get("Authorization"):
        url = f"{base_url}/api/v1/jobs/list?limit=1"
        status, data, raw = _request_json("GET", url, nonadmin_headers, None, args.timeout)
        if status in (401, 403):
            _record(results, "jobs/list non-admin", ok=True, detail=f"status={status}")
        else:
            _record(results, "jobs/list non-admin", ok=False, detail=f"status={status} body={_trim(raw)}")
    else:
        _record(results, "jobs/list non-admin", ok=True, skipped=True, detail="no non-admin creds provided")

    failed = [r for r in results if not r[1] and not r[2]]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
