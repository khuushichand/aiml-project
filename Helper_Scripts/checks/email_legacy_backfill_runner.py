#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run legacy email media -> normalized email backfill with resumable "
            "checkpoint state."
        )
    )
    parser.add_argument(
        "--db-path",
        required=True,
        help="Path to the target Media DB (SQLite file).",
    )
    parser.add_argument(
        "--tenant-id",
        default=None,
        help="Explicit tenant id for normalized email tables (defaults to MediaDatabase scope).",
    )
    parser.add_argument(
        "--backfill-key",
        default="legacy_media_email",
        help="Checkpoint key namespace (default: legacy_media_email).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Rows per batch (default: 500).",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Optional cap on batches for this run.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    db_path = str(Path(args.db_path).expanduser())
    client_id = str(args.tenant_id or "legacy_backfill_worker")

    db = MediaDatabase(db_path=db_path, client_id=client_id)
    try:
        result: dict[str, Any] = db.run_email_legacy_backfill_worker(
            batch_size=int(args.batch_size),
            tenant_id=args.tenant_id,
            backfill_key=str(args.backfill_key),
            max_batches=args.max_batches,
        )
    finally:
        db.close_connection()

    print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
