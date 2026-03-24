#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import inspect
import os
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _ensure_minimal_env() -> None:
    os.environ.setdefault(
        "SINGLE_USER_API_KEY",
        "media-db-runtime-ownership-count-local-key-1234567890",
    )


def _configure_minimal_logging() -> None:
    try:
        from loguru import logger
    except Exception:
        return

    logger.remove()
    logger.add(sys.stderr, level="ERROR")


def get_legacy_owned_method_names() -> list[str]:
    _ensure_minimal_env()
    _configure_minimal_logging()

    from tldw_Server_API.app.core.DB_Management.media_db.legacy_identifiers import (
        LEGACY_MEDIA_DB_MODULE,
    )

    media_database = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.media_db.media_database"
    )

    return sorted(
        name
        for name, value in media_database.MediaDatabase.__dict__.items()
        if inspect.isfunction(value)
        and value.__globals__.get("__name__") == LEGACY_MEDIA_DB_MODULE
    )


def get_legacy_owned_method_count() -> int:
    return len(get_legacy_owned_method_names())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Count canonical MediaDatabase methods still owned by the legacy module.",
    )
    parser.add_argument(
        "--names",
        action="store_true",
        help="Print the method names after the count.",
    )
    args = parser.parse_args()

    names = get_legacy_owned_method_names()
    print(len(names))
    if args.names:
        for name in names:
            print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
