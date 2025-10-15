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
from tldw_Server_API.app.core.DB_Management.backends.pg_rls_policies import (
    ensure_prompt_studio_rls,
    ensure_chacha_rls,
    build_prompt_studio_rls_sql,
    build_chacha_rls_sql,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply or preview Postgres RLS policies (Prompt Studio + ChaChaNotes)")
    parser.add_argument("--apply", action="store_true", help="Apply policies (idempotent)")
    parser.add_argument("--dry-run", action="store_true", help="Log-only preview of SQL; no DB connection required")
    args = parser.parse_args()

    if args.dry_run and not args.apply:
        # Log the SQL that would be applied for both modules
        logger.info("[DRY RUN] Prompt Studio RLS SQL:")
        for stmt in build_prompt_studio_rls_sql():
            logger.info(stmt)
        logger.info("[DRY RUN] ChaChaNotes RLS SQL:")
        for stmt in build_chacha_rls_sql():
            logger.info(stmt)
        return 0

    cfg = DatabaseConfig.from_env()
    if cfg.backend != BackendType.POSTGRESQL:
        logger.error("This tool requires a Postgres DATABASE_URL or PG_* env")
        return 2

    backend = DatabaseBackendFactory.create_backend(cfg)
    if not args.apply:
        logger.info("Nothing to do. Use --apply to execute policy statements, or --dry-run to preview.")
        return 0

    ps_ok = ensure_prompt_studio_rls(backend)
    cc_ok = ensure_chacha_rls(backend)
    if ps_ok or cc_ok:
        logger.info(f"RLS policies applied (prompt_studio={ps_ok}, chacha={cc_ok})")
        return 0
    logger.warning("No policies applied; confirm backend is PostgreSQL and reachable.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
