"""
CLI utility to validate the shared content database backend.

Usage:
    python -m tldw_Server_API.app.core.DB_Management.content_migrate
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the configured content database backend (PostgreSQL)."
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Suppress success output (still prints errors to stderr).",
    )
    args = parser.parse_args()

    from tldw_Server_API.app.core.DB_Management.DB_Manager import (
        validate_postgres_content_backend,
    )

    try:
        validate_postgres_content_backend()
    except RuntimeError as exc:
        print(f"[content_migrate] validation failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive guardrail
        print(f"[content_migrate] unexpected error: {exc}", file=sys.stderr)
        return 1

    if not args.silent:
        print("[content_migrate] PostgreSQL content backend is up to date and secured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
