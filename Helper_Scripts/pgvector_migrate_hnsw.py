#!/usr/bin/env python3
"""
Helper: migrate a pgvector table to HNSW with minimal downtime by creating a
new table, building index, copying data in batches, then swapping names.

Usage:
  PG_DSN=postgresql://user:pass@host:5432/db \
  python Helper_Scripts/pgvector_migrate_hnsw.py \
    --table vs_collection \
    --new-table vs_collection_hnsw \
    --metric cosine --m 16 --efc 200 --batch 10000 --dry-run

Notes:
  - Ensure pgvector >= 0.7 for HNSW.
  - This script performs best-effort; validate in staging.
  - Final swap requires an exclusive lock and may block briefly.
"""
import os
import sys
import argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dsn', default=os.getenv('PG_DSN') or os.getenv('PG_TEST_DSN'), help='Postgres DSN')
    ap.add_argument('--table', required=True, help='Existing table name (embedding column name must be embedding)')
    ap.add_argument('--new-table', required=True, help='New table name to create')
    ap.add_argument('--metric', default='cosine', choices=['cosine','euclidean','ip'])
    ap.add_argument('--m', type=int, default=16)
    ap.add_argument('--efc', type=int, default=200)
    ap.add_argument('--batch', type=int, default=10000)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--swap-now', action='store_true', help='Perform final swap automatically (exclusive lock)')
    ap.add_argument('--source-where', default='', help='Optional WHERE clause to filter source rows')
    args = ap.parse_args()

    if not args.dsn:
        print('Provide DSN via --dsn or PG_DSN'); sys.exit(1)
    try:
        import psycopg
    except Exception as e:
        print('psycopg is required:', e); sys.exit(1)

    ops = 'vector_cosine_ops' if args.metric=='cosine' else ('vector_l2_ops' if args.metric=='euclidean' else 'vector_ip_ops')

    plan = [
        f"CREATE TABLE IF NOT EXISTS \"{args.new_table}\" (id TEXT PRIMARY KEY, content TEXT, metadata JSONB, embedding vector);",
        f"CREATE INDEX IF NOT EXISTS {args.new_table}_embedding_hnsw ON \"{args.new_table}\" USING hnsw (embedding {ops}) WITH (m={args.m}, ef_construction={args.efc});",
        f"ANALYZE \"{args.new_table}\";",
        f"-- Copy in batches from \"{args.table}\" WHERE {args.source_where or 'TRUE'}",
    ]

    if args.dry_run:
        print('\n'.join(plan));
        return

    with psycopg.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            for stmt in plan[:-1]:
                print('EXEC:', stmt)
                cur.execute(stmt)
            conn.commit()
            # Batch copy
            where = f"WHERE {args.source_where}" if args.source_where else ""
            print('Starting batch copy...')
            cur.execute(f"SELECT COUNT(1) FROM \"{args.table}\" {where}")
            total = cur.fetchone()[0]
            cur.execute(f"DECLARE cur_copy NO SCROLL CURSOR FOR SELECT id, content, metadata, embedding FROM \"{args.table}\" {where}")
            copied = 0
            while True:
                cur.execute(f"FETCH FORWARD {args.batch} FROM cur_copy")
                rows = cur.fetchall()
                if not rows:
                    break
                args_list = rows
                cur.executemany(
                    f"INSERT INTO \"{args.new_table}\" (id, content, metadata, embedding) VALUES (%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
                    args_list
                )
                conn.commit()
                copied += len(rows)
                print(f"Copied {copied}/{total}")
            # Final swap
            swap_stmt = f"BEGIN; ALTER TABLE \"{args.table}\" RENAME TO \"{args.table}_old\"; ALTER TABLE \"{args.new_table}\" RENAME TO \"{args.table}\"; COMMIT;"
            if args.swap_now:
                print('Performing final swap...')
                cur.execute(swap_stmt)
                conn.commit()
                print('Swap complete.')
            else:
                print('Ready for final swap. Run the swap manually during a low-traffic window:')
                print(swap_stmt)

if __name__ == '__main__':
    main()
