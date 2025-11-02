"""
pg_load_synonyms.py

Tiny admin helper to bulk-load fts_synonyms from Config_Files/Synonyms/<corpus>.json into Postgres.

Usage:
  python -m Helper_Scripts.DB-Related.pg_load_synonyms --corpus my_corpus

Connection sources (priority):
  1) Environment variables: PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD, PG_SSLMODE
  2) settings.RAG.pgvector.{host,port,database,user,password,sslmode}

This script will create the fts_synonyms table and synonyms_expand() function if missing.
"""

from __future__ import annotations

import argparse
import os
from typing import Dict, List

from loguru import logger

from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseConfig, BackendType, DatabaseError
from tldw_Server_API.app.core.DB_Management.backends.postgresql_backend import PostgreSQLBackend
from tldw_Server_API.app.core.RAG.rag_service.synonyms_registry import get_corpus_synonyms


def _build_config_from_env_and_settings() -> DatabaseConfig:
    # Try env first
    host = os.getenv("PG_HOST")
    port = int(os.getenv("PG_PORT", "5432") or 5432)
    database = os.getenv("PG_DATABASE") or os.getenv("PG_DB")
    user = os.getenv("PG_USER")
    password = os.getenv("PG_PASSWORD")
    sslmode = os.getenv("PG_SSLMODE", "prefer")

    # Fallback to settings if missing
    if not host or not database or not user:
        try:
            from tldw_Server_API.app.core.config import settings as _settings  # type: ignore
            pg = (_settings.get("RAG", {}) or {}).get("pgvector", {})
            host = host or pg.get("host")
            port = port or int(pg.get("port") or 5432)
            database = database or pg.get("database")
            user = user or pg.get("user")
            password = password or pg.get("password")
            sslmode = sslmode or pg.get("sslmode") or "prefer"
        except Exception:
            pass

    if not host or not database or not user:
        raise RuntimeError("Missing required PG connection info. Set PG_HOST, PG_DATABASE, PG_USER (and PG_PASSWORD if needed).")

    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=host,
        pg_port=port,
        pg_database=database,
        pg_user=user,
        pg_password=password,
        pg_sslmode=str(sslmode or "prefer"),
        pool_size=1,
    )


def _ensure_support_and_upsert(backend: PostgreSQLBackend, syn_map: Dict[str, List[str]]) -> int:
    # Best-effort: ensure table+function
    backend.ensure_synonyms_support()
    if not syn_map:
        return 0
    # Upsert synonyms
    params = []
    for term, aliases in syn_map.items():
        # store normalized term as-lower; synonyms as array
        t = str(term or "").strip().lower()
        if not t:
            continue
        arr = [str(a).strip().lower() for a in (aliases or []) if str(a).strip()]
        params.append((t, arr))
    if not params:
        return 0
    q = (
        "INSERT INTO fts_synonyms(term, synonyms) VALUES (%s, %s) "
        "ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms"
    )
    backend.execute_many(q, params)
    return len(params)


def main():
    ap = argparse.ArgumentParser(description="Load synonyms into Postgres fts_synonyms table")
    ap.add_argument("--corpus", required=True, help="Corpus name (maps to Config_Files/Synonyms/<corpus>.json)")
    args = ap.parse_args()

    try:
        syn_map = get_corpus_synonyms(args.corpus)
        if not syn_map:
            logger.warning(f"No synonyms loaded for corpus '{args.corpus}'. Check file exists and contains mappings.")
        cfg = _build_config_from_env_and_settings()
        backend = PostgreSQLBackend(cfg)
        count = _ensure_support_and_upsert(backend, syn_map)
        logger.info(f"Loaded/updated {count} synonym rows into fts_synonyms for corpus '{args.corpus}'")
    except DatabaseError as de:
        logger.error(f"Database error: {de}")
        raise
    except Exception as e:
        logger.error(f"Failed to load synonyms: {e}")
        raise


if __name__ == "__main__":
    main()
