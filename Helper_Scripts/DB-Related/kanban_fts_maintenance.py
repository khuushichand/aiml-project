#!/usr/bin/env python3
"""
Run FTS5 maintenance for a user's Kanban database.

Usage examples:
  python Helper_Scripts/DB-Related/kanban_fts_maintenance.py --user-id 1 --action optimize
  python Helper_Scripts/DB-Related/kanban_fts_maintenance.py --user-id 1 --action rebuild
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger

from tldw_Server_API.app.core.DB_Management.Kanban_DB import KanbanDB, KanbanDBError
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for Kanban FTS maintenance.

    Args:
        None.
    Returns:
        argparse.Namespace: Parsed options for --user-id (Kanban owner ID),
        --action (optimize or rebuild), and --db-path (explicit Kanban DB path).
    """
    parser = argparse.ArgumentParser(description="Run Kanban FTS maintenance for a user database.")
    parser.add_argument("--user-id", type=int, required=True, help="User ID owning the Kanban DB.")
    parser.add_argument(
        "--action",
        choices=("optimize", "rebuild"),
        default="optimize",
        help="FTS maintenance action to run.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Optional explicit path to Kanban.db (overrides user_id lookup).",
    )
    return parser.parse_args()


def main() -> int:
    """Run Kanban FTS maintenance for the requested user or database path.

    Args:
        None.
    Returns:
        int: 0 on success; non-zero on failure.
    Raises:
        None. KanbanDBError and unexpected exceptions are caught and logged.
    """
    args = _parse_args()
    if args.db_path:
        db_path = Path(args.db_path).expanduser()
        if not db_path.exists():
            logger.error("Kanban DB not found at %s (user_id=%s)", db_path, args.user_id)
            return 2
    else:
        db_path = DatabasePaths.get_kanban_db_path(args.user_id)

    try:
        db = KanbanDB(
            db_path=str(db_path),
            user_id=str(args.user_id),
            allow_external_db_path=bool(args.db_path),
        )
        if args.action == "rebuild":
            db.rebuild_fts()
        else:
            db.optimize_fts()
    except KanbanDBError as exc:
        logger.error(
            "Kanban FTS %s failed for user_id=%s (db=%s): %s",
            args.action,
            args.user_id,
            db_path,
            exc,
        )
        return 1
    except Exception as exc:
        logger.error(
            "Kanban FTS %s failed for user_id=%s (db=%s): %s",
            args.action,
            args.user_id,
            db_path,
            exc,
        )
        return 1

    logger.success(
        "Kanban FTS %s completed for user_id=%s (db=%s)",
        args.action,
        args.user_id,
        db_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
