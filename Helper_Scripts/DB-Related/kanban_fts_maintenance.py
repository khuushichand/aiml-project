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

from tldw_Server_API.app.core.DB_Management.Kanban_DB import KanbanDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


def _parse_args() -> argparse.Namespace:
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
    args = _parse_args()
    if args.db_path:
        db_path = Path(args.db_path).expanduser()
    else:
        db_path = DatabasePaths.get_kanban_db_path(args.user_id)

    db = KanbanDB(db_path=str(db_path), user_id=str(args.user_id))
    if args.action == "rebuild":
        db.rebuild_fts()
    else:
        db.optimize_fts()

    print(f"Kanban FTS {args.action} completed for user_id={args.user_id} (db={db_path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
