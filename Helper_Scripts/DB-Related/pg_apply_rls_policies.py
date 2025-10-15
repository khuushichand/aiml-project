"""
CLI helper to apply Postgres RLS policies for Prompt Studio.

Env:
  DATABASE_URL=postgresql://user:pass@host:port/dbname   (or set PG_* in config)

Usage:
  python -m Helper_Scripts.DB-Related.pg_apply_rls_policies --apply
"""
from __future__ import annotations

import argparse
from loguru import logger

from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseConfig, BackendType
from tldw_Server_API.app.core.DB_Management.backends.pg_rls_policies import ensure_prompt_studio_rls


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Prompt Studio RLS policies to Postgres")
    parser.add_argument("--apply", action="store_true", help="Apply policies (idempotent)")
    args = parser.parse_args()

    cfg = DatabaseConfig.from_env()
    if cfg.backend != BackendType.POSTGRESQL:
        logger.error("This tool requires a Postgres DATABASE_URL or PG_* env")
        return 2

    backend = DatabaseBackendFactory.create_backend(cfg)
    if not args.apply:
        logger.info("Nothing to do. Use --apply to execute policy statements.")
        return 0

    ok = ensure_prompt_studio_rls(backend)
    if ok:
        logger.info("RLS policies applied (or already present)")
        return 0
    logger.warning("No policies applied; confirm backend is PostgreSQL and reachable.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

