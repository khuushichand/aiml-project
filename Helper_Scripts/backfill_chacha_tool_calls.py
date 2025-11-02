#!/usr/bin/env python3
"""
Backfill message_metadata.tool_calls from inline "[tool_calls]: <json>" suffix in assistant messages.

Usage:
  python -m Helper_Scripts.backfill_chacha_tool_calls --base-dir /path/to/USER_DB_BASE_DIR [--strip-inline]
  python -m Helper_Scripts.backfill_chacha_tool_calls --db /path/to/ChaChaNotes.db [--strip-inline]

Defaults:
  If neither --base-dir nor --db is provided, tries env USER_DB_BASE_DIR and scans all user subdirectories.

Notes:
  - Uses CharactersRAGDB.backfill_tool_calls_from_inline.
  - When --strip-inline is provided, removes the inline suffix from message content via optimistic locking.
"""

import argparse
import os
from pathlib import Path
from typing import List

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


def process_db(db_path: Path, strip_inline: bool) -> None:
    # Use a generic client_id for migration
    db = CharactersRAGDB(db_path=str(db_path), client_id="migration")
    stats = db.backfill_tool_calls_from_inline(strip_inline=strip_inline)
    print(f"{db_path}: scanned={stats['scanned']} matched={stats['matched']} backfilled={stats['backfilled']} stripped={stats['stripped']}")


def main():
    parser = argparse.ArgumentParser(description="Backfill ChaCha message_metadata tool_calls from inline markers")
    parser.add_argument("--base-dir", type=str, default=None, help="Base dir containing per-user subdirs with ChaChaNotes.db")
    parser.add_argument("--db", type=str, default=None, help="Path to a single ChaChaNotes.db file")
    parser.add_argument("--strip-inline", action="store_true", help="Strip inline [tool_calls]: JSON from message content after backfill")
    args = parser.parse_args()

    if args.db:
        path = Path(args.db)
        if not path.exists():
            print(f"DB path not found: {path}")
            raise SystemExit(1)
        process_db(path, args.strip_inline)
        return

    base_dir = args.base_dir or os.environ.get("USER_DB_BASE_DIR")
    if not base_dir:
        print("Provide --base-dir or set USER_DB_BASE_DIR, or pass --db")
        raise SystemExit(2)
    base = Path(base_dir)
    if not base.exists():
        print(f"Base dir not found: {base}")
        raise SystemExit(3)

    # Scan for per-user ChaChaNotes.db files: <base>/<user_id>/ChaChaNotes.db
    dbs: List[Path] = []
    for child in base.iterdir():
        if child.is_dir():
            candidate = child / "ChaChaNotes.db"
            if candidate.exists():
                dbs.append(candidate)

    if not dbs:
        print("No ChaChaNotes.db files found under base dir")
        raise SystemExit(0)

    for db_path in dbs:
        process_db(db_path, args.strip_inline)


if __name__ == "__main__":
    main()
