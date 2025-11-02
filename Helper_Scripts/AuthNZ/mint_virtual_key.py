#!/usr/bin/env python3
"""
Mint a short-lived, scoped JWT ("virtual key") and optionally emit shell export lines
or write to a dotenv file for the Workflows scheduler service.

Usage examples:
  # Basic: print token only
  python -m Helper_Scripts.AuthNZ.mint_virtual_key --user-id 1 --username admin --role admin \
      --scope workflows --ttl-minutes 30

  # Print export lines for scheduler
  python -m Helper_Scripts.AuthNZ.mint_virtual_key --user-id 1 --username admin --role admin \
      --print-export

  # Write to a .env-style file
  python -m Helper_Scripts.AuthNZ.mint_virtual_key --user-id 1 --username admin --role admin \
      --dotenv tldw_Server_API/Config_Files/workflows.env

Notes
  - The JWT is signed using the configured AuthNZ settings (python-jose) and includes
    claims: sub, username, role, type=access, scope, iat, exp, jti, and optional schedule_id.
  - Scope defaults to 'workflows'.
  - Meant for multi-user mode; in single-user, prefer X-API-KEY.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

try:
    from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
except Exception as e:
    print(f"ERROR: Unable to import AuthNZ services: {e}", file=sys.stderr)
    sys.exit(2)


def _emit_exports(token: str) -> None:
    print(f"export WORKFLOWS_DEFAULT_BEARER_TOKEN='{token}'")
    print("export WORKFLOWS_VALIDATE_DEFAULT_AUTH='true'")


def _write_dotenv(path: str, token: str) -> None:
    p = Path(path)
    try:
        lines = []
        if p.exists():
            try:
                lines = p.read_text(encoding="utf-8").splitlines()
            except Exception:
                lines = []
        kv = {
            "WORKFLOWS_DEFAULT_BEARER_TOKEN": token,
            "WORKFLOWS_VALIDATE_DEFAULT_AUTH": "true",
        }
        # Replace or append keys
        existing = {k.split("=", 1)[0] for k in lines if "=" in k}
        for k, v in kv.items():
            entry = f"{k}={v}"
            if k in existing:
                lines = [entry if (ln.startswith(f"{k}=") or ln.startswith(f"export {k}=")) else ln for ln in lines]
            else:
                lines.append(entry)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Wrote: {p}")
    except Exception as e:
        print(f"ERROR: Failed to write dotenv: {e}", file=sys.stderr)
        sys.exit(2)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mint a short-lived scoped JWT (virtual key)")
    ap.add_argument("--user-id", type=int, required=True, help="Subject user id")
    ap.add_argument("--username", type=str, required=False, default="user")
    ap.add_argument("--role", type=str, required=False, default="user", choices=["user", "admin"])
    ap.add_argument("--scope", type=str, default="workflows")
    ap.add_argument("--ttl-minutes", type=int, default=60)
    ap.add_argument("--schedule-id", type=str, default=None)
    ap.add_argument("--print-export", action="store_true", help="Print shell export lines for scheduler")
    ap.add_argument("--dotenv", type=str, default=None, help="Write token and flags to .env-style file")
    args = ap.parse_args(argv)

    settings = get_settings()
    svc = JWTService(settings)
    token = svc.create_virtual_access_token(
        user_id=int(args.user_id),
        username=str(args.username or "user"),
        role=str(args.role or "user"),
        scope=str(args.scope or "workflows"),
        ttl_minutes=int(args.ttl_minutes),
        schedule_id=(str(args.schedule_id) if args.schedule_id else None),
    )

    print(token)
    if args.print_export:
        _emit_exports(token)
    if args.dotenv:
        _write_dotenv(args.dotenv, token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
