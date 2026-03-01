#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess

from Helper_Scripts.common.tooling_smoke_runner import build_steps


def main() -> int:
    parser = argparse.ArgumentParser(description="Run unified tooling smoke checks.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL.")
    parser.add_argument("--api-key", default=None, help="Single-user API key.")
    args = parser.parse_args()

    for step in build_steps(base_url=args.base_url, api_key=args.api_key):
        subprocess.run(step.command, check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
