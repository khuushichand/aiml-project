"""
Quick connection check for pgvector configuration.

Usage:
  python Helper_Scripts/pgvector_quickcheck.py

Respects either PGVECTOR_DSN or discrete PGVECTOR_* environment variables.
Creates the extension if missing and prints basic server/version info.
"""
import os
import sys


def _build_dsn() -> str:
    dsn = os.getenv("PGVECTOR_DSN")
    if dsn:
        return dsn
    host = os.getenv("PGVECTOR_HOST", "localhost")
    port = os.getenv("PGVECTOR_PORT", "5432")
    db = os.getenv("PGVECTOR_DATABASE", "postgres")
    user = os.getenv("PGVECTOR_USER", "postgres")
    password = os.getenv("PGVECTOR_PASSWORD", "")
    sslmode = os.getenv("PGVECTOR_SSLMODE", "prefer")
    return f"host={host} port={port} dbname={db} user={user} password={password} sslmode={sslmode}"


def main() -> int:
    dsn = _build_dsn()
    try:
        try:
            import psycopg
            conn = psycopg.connect(dsn)  # type: ignore[attr-defined]
            drv = "psycopg3"
        except Exception:
            import psycopg2  # type: ignore
            conn = psycopg2.connect(dsn)
            drv = "psycopg2"
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        print(f"Connected ({drv}). Server: {version}")
        # Ensure extension exists
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.commit()
            print("pgvector extension is present (created if missing).")
        except Exception as e:
            print(f"Warning: could not ensure pgvector extension: {e}")
        cur.close()
        conn.close()
        return 0
    except Exception as e:
        print(f"Connection failed: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
