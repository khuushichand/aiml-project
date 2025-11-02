#!/usr/bin/env python3
"""
PostgreSQL content DB backup/restore helper.

Usage examples:

  # Backup to ./tldw_DB_Backups/postgres with label 'content'
  python Helper_Scripts/pg_backup_restore.py backup \
    --backup-dir ./tldw_DB_Backups/postgres \
    --label content

  # Restore from a .dump file (drops objects first)
  python Helper_Scripts/pg_backup_restore.py restore \
    --dump-file ./tldw_DB_Backups/postgres/content_20240101_000000.dump

Notes:
- The script reads the configured content backend via DB_Manager. Ensure your
  environment/config.txt selects PostgreSQL for the content DB.
- Requires pg_dump/pg_restore on PATH.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from loguru import logger


def _get_pg_backend():
    try:
        from tldw_Server_API.app.core.DB_Management.DB_Manager import (
            get_content_backend_instance,
        )
        backend = get_content_backend_instance()
        return backend
    except Exception as exc:
        logger.error(f"Unable to resolve content backend: {exc}")
        return None


def _backup(args) -> int:
    backup_dir = Path(args.backup_dir or "./tldw_DB_Backups/postgres").resolve()
    label = args.label or "content"

    backend = _get_pg_backend()
    if backend is None:
        logger.error("No content backend is configured. Ensure PostgreSQL mode is enabled.")
        return 2

    from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
    if getattr(backend, "backend_type", None) != BackendType.POSTGRESQL:
        logger.error("Content backend is not PostgreSQL. Switch content DB to PostgreSQL to use this helper.")
        return 2

    from tldw_Server_API.app.core.DB_Management.DB_Backups import create_postgres_backup

    out = create_postgres_backup(backend, backup_dir=str(backup_dir), label=label)
    if not out or not os.path.exists(out):
        logger.error(f"Backup failed: {out}")
        return 1
    logger.info(f"Backup created: {out}")
    print(out)
    return 0


def _restore(args) -> int:
    dump_file = Path(args.dump_file).resolve()
    if not dump_file.exists():
        logger.error(f"Dump file not found: {dump_file}")
        return 2

    backend = _get_pg_backend()
    if backend is None:
        logger.error("No content backend is configured. Ensure PostgreSQL mode is enabled.")
        return 2

    from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
    if getattr(backend, "backend_type", None) != BackendType.POSTGRESQL:
        logger.error("Content backend is not PostgreSQL. Switch content DB to PostgreSQL to use this helper.")
        return 2

    from tldw_Server_API.app.core.DB_Management.DB_Backups import restore_postgres_backup

    status = restore_postgres_backup(backend, dump_file=str(dump_file), drop_first=(not args.no_drop))
    if status != "ok":
        logger.error(f"Restore failed: {status}")
        return 1
    logger.info("Restore completed successfully")
    print("ok")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="PostgreSQL content DB backup/restore helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_backup = sub.add_parser("backup", help="Create a PostgreSQL backup using pg_dump")
    p_backup.add_argument("--backup-dir", default="./tldw_DB_Backups/postgres", help="Output directory for backups")
    p_backup.add_argument("--label", default="content", help="Label prefix for backup filename")
    p_backup.set_defaults(func=_backup)

    p_restore = sub.add_parser("restore", help="Restore a PostgreSQL backup using pg_restore")
    p_restore.add_argument("--dump-file", required=True, help="Path to .dump file created by pg_dump -F c")
    p_restore.add_argument("--no-drop", action="store_true", help="Do not drop objects before restore (omit -c)")
    p_restore.set_defaults(func=_restore)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
