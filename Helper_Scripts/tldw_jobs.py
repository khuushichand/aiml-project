#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import json


def _api_key_header() -> tuple[str, str]:
    # Prefer server settings if importable; fallback to env
    api_key = None
    try:
        from tldw_Server_API.app.core.AuthNZ.settings import get_settings
        api_key = get_settings().SINGLE_USER_API_KEY
    except Exception:
        api_key = os.getenv("SINGLE_USER_API_KEY")
    if not api_key:
        return ("Authorization", "")
    return ("X-API-KEY", api_key)


def _curl(cmd: str, method: str = "GET", data: dict | None = None) -> str:
    host = os.getenv("TLDW_BASE_URL", "http://127.0.0.1:8000")
    h_name, h_val = _api_key_header()
    hdr = f"-H '{h_name}: {h_val}'" if h_val else ""
    body = f"-H 'Content-Type: application/json' -d '{json.dumps(data)}'" if data is not None else ""
    return f"curl -sS -X {method} {hdr} {body} '{host}{cmd}'"


def cmd_stats(args):
    qs = []
    if args.domain:
        qs.append(f"domain={args.domain}")
    if args.queue:
        qs.append(f"queue={args.queue}")
    if args.job_type:
        qs.append(f"job_type={args.job_type}")
    path = "/api/v1/jobs/stats" + ("?" + "&".join(qs) if qs else "")
    if args.run:
        _run_http(path)
    else:
        print(_curl(path))


def cmd_list(args):
    qs = []
    for k in ("domain","queue","status","owner_user_id","job_type","limit","sort_by","sort_order"):
        v = getattr(args, k, None)
        if v is not None:
            qs.append(f"{k}={v}")
    path = "/api/v1/jobs/list" + ("?" + "&".join(qs) if qs else "")
    if args.run:
        _run_http(path)
    else:
        print(_curl(path))


def cmd_prune(args):
    body = {
        "statuses": args.statuses or ["completed","failed","cancelled"],
        "older_than_days": args.older_than_days,
        "domain": args.domain,
        "queue": args.queue,
        "job_type": args.job_type,
        "dry_run": args.dry_run,
    }
    path = "/api/v1/jobs/prune"
    if args.run:
        _run_http(path, method="POST", data=body, confirm=(not args.dry_run))
    else:
        curl = _curl(path, method="POST", data=body)
        if not args.dry_run:
            curl = curl + " -H 'X-Confirm: true'"
        print(curl)


def cmd_ttl(args):
    body = {
        "age_seconds": args.age_seconds,
        "runtime_seconds": args.runtime_seconds,
        "action": args.action,
        "domain": args.domain,
        "queue": args.queue,
        "job_type": args.job_type,
    }
    path = "/api/v1/jobs/ttl/sweep"
    if args.run:
        _run_http(path, method="POST", data=body, confirm=True)
    else:
        curl = _curl(path, method="POST", data=body) + " -H 'X-Confirm: true'"
        print(curl)


def cmd_archive_meta(args):
    path = f"/api/v1/jobs/archive/meta?job_id={args.job_id}"
    if args.run:
        _run_http(path)
    else:
        print(_curl(path))

def _run_http(path: str, method: str = "GET", data: dict | None = None, confirm: bool = False) -> None:
    try:
        import httpx
    except Exception:
        print("httpx not installed; printing cURL instead:")
        print(_curl(path, method=method, data=data))
        return
    base = os.getenv("TLDW_BASE_URL", "http://127.0.0.1:8000")
    url = f"{base}{path}"
    headers = {}
    k, v = _api_key_header()
    if v:
        headers[k] = v
    if confirm:
        headers["X-Confirm"] = "true"
    if data is not None:
        headers["Content-Type"] = "application/json"
    with httpx.Client(timeout=30.0) as client:
        resp = client.request(method, url, headers=headers, json=data)
        print(resp.status_code)
        try:
            print(json.dumps(resp.json(), indent=2))
        except Exception:
            print(resp.text)

def _verify_sig(args) -> None:
    import hmac, hashlib, sys
    ts = args.timestamp
    sig_header = args.signature
    secrets = [s.strip() for s in (args.secrets or '').split(',') if s.strip()]
    if args.body:
        with open(args.body, 'rb') as f:
            body = f.read()
    else:
        body = sys.stdin.buffer.read()
    try:
        scheme, value = sig_header.split('=', 1)
    except Exception:
        print('invalid: bad signature header format')
        sys.exit(2)
    if scheme != 'v1':
        print('invalid: unsupported signature scheme')
        sys.exit(2)
    msg = f"{ts}.".encode() + body
    for sk in secrets:
        calc = hmac.new(sk.encode(), msg, hashlib.sha256).hexdigest()
        if hmac.compare_digest(calc, value):
            print('valid')
            return
    print('invalid')
    sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="tldw-jobs: developer CLI for Jobs admin endpoints (prints cURL)")
    sub = p.add_subparsers(dest="cmd")

    s_stats = sub.add_parser("stats", help="Show queue stats")
    s_stats.add_argument("--domain")
    s_stats.add_argument("--queue")
    s_stats.add_argument("--job_type")
    s_stats.add_argument("--run", action="store_true", help="Execute the request instead of printing cURL")
    s_stats.set_defaults(func=cmd_stats)

    s_list = sub.add_parser("list", help="List jobs")
    s_list.add_argument("--domain")
    s_list.add_argument("--queue")
    s_list.add_argument("--status")
    s_list.add_argument("--owner_user_id")
    s_list.add_argument("--job_type")
    s_list.add_argument("--limit", type=int, default=100)
    s_list.add_argument("--sort_by")
    s_list.add_argument("--sort_order")
    s_list.add_argument("--run", action="store_true")
    s_list.set_defaults(func=cmd_list)

    s_prune = sub.add_parser("prune", help="Prune jobs")
    s_prune.add_argument("--statuses", nargs="*")
    s_prune.add_argument("--older_than_days", type=int, default=30)
    s_prune.add_argument("--domain")
    s_prune.add_argument("--queue")
    s_prune.add_argument("--job_type")
    s_prune.add_argument("--dry_run", action="store_true")
    s_prune.add_argument("--run", action="store_true")
    s_prune.set_defaults(func=cmd_prune)

    s_ttl = sub.add_parser("ttl", help="TTL sweep")
    s_ttl.add_argument("--age_seconds", type=int)
    s_ttl.add_argument("--runtime_seconds", type=int)
    s_ttl.add_argument("--action", choices=["cancel","fail"], default="cancel")
    s_ttl.add_argument("--domain")
    s_ttl.add_argument("--queue")
    s_ttl.add_argument("--job_type")
    s_ttl.add_argument("--run", action="store_true")
    s_ttl.set_defaults(func=cmd_ttl)

    s_meta = sub.add_parser("archive-meta", help="Fetch archive compression meta for a job id")
    s_meta.add_argument("--job_id", type=int, required=True)
    s_meta.add_argument("--run", action="store_true")
    s_meta.set_defaults(func=cmd_archive_meta)

    s_verify = sub.add_parser("verify-signature", help="Verify Jobs webhook signature (reads body from file or stdin)")
    s_verify.add_argument("--timestamp", required=True, help="X-Jobs-Timestamp header value")
    s_verify.add_argument("--signature", required=True, help="X-Jobs-Signature header (e.g., v1=...)")
    s_verify.add_argument("--secrets", required=True, help="Comma-separated secrets (latest first)")
    s_verify.add_argument("--body", help="Path to a file with request body; if omitted, read from stdin")
    s_verify.set_defaults(func=lambda args: _verify_sig(args))

    args = p.parse_args()
    if not getattr(args, "func", None):
        p.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
