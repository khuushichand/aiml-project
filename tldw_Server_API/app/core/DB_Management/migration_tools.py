
"""Utilities for migrating SQLite content databases to PostgreSQL."""

from __future__ import annotations

import argparse
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseBackend, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase


logger = logging.getLogger(__name__)


@dataclass
class TableMeta:
    """Metadata describing a table within the source SQLite database."""

    name: str
    source_name: str
    columns: List[str]
    pg_columns: List[str]
    pk_columns: List[str]
    sequence_columns: List[str]
    dependencies: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.name = self.name.lower()
        self.dependencies = {dep.lower() for dep in self.dependencies}
        self.pg_columns = [col.lower() for col in self.pg_columns]
        self.pk_columns = [col.lower() for col in self.pk_columns]
        self.sequence_columns = [col.lower() for col in self.sequence_columns]


_DEFAULT_SKIP_SUFFIXES = (
    '_fts',
    '_fts_data',
    '_fts_idx',
    '_fts_docsize',
    '_fts_config',
)


def migrate_sqlite_to_postgres(
    sqlite_path: Path | str,
    postgres_config: DatabaseConfig,
    *,
    batch_size: int = 500,
    skip_tables: Optional[Iterable[str]] = None,
    label: str = 'content',
) -> None:
    """Copy rows from a SQLite database into a PostgreSQL database."""

    sqlite_path = Path(sqlite_path)
    if not sqlite_path.exists():
        raise FileNotFoundError(f'SQLite database not found: {sqlite_path}')

    logger.info('Starting migration of %s database from %s', label, sqlite_path)
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row
    try:
        tables = _introspect_sqlite_schema(sqlite_conn, skip_tables)
        if not tables:
            logger.warning('No tables discovered in %s; skipping migration', sqlite_path)
            return

        insertion_order = _topological_sort(tables)
        logger.debug('Insertion order for %s: %s', label, insertion_order)

        backend = DatabaseBackendFactory.create_backend(postgres_config)
        try:
            with backend.transaction() as pg_conn:
                _truncate_tables(backend, pg_conn, insertion_order)
                for table_name in insertion_order:
                    meta = tables[table_name]
                    _copy_table(sqlite_conn, backend, pg_conn, meta, batch_size)
                _sync_sequences(backend, pg_conn, tables)
        finally:
            try:
                backend.get_pool().close_all()
            except Exception:  # pragma: no cover - defensive close
                pass
    finally:
        sqlite_conn.close()
    logger.info('Completed migration of %s database from %s', label, sqlite_path)


def migrate_workflows_sqlite_to_postgres(
    sqlite_path: Path | str,
    postgres_config: DatabaseConfig,
    *,
    batch_size: int = 500,
) -> None:
    """Copy workflows SQLite database contents into PostgreSQL."""

    sqlite_path = Path(sqlite_path)
    if not sqlite_path.exists():
        raise FileNotFoundError(f'Workflows SQLite database not found: {sqlite_path}')

    logger.info('Starting migration of workflows database from %s', sqlite_path)
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row

    backend = DatabaseBackendFactory.create_backend(postgres_config)
    try:
        # Initialise the PostgreSQL schema using the workflows adapter.
        # Do NOT close the backend pool here; we still need it for copying rows.
        _ = WorkflowsDatabase(db_path=':memory:', backend=backend)

        with backend.transaction() as pg_conn:
            for table in ('workflow_artifacts', 'workflow_events', 'workflow_step_runs', 'workflow_runs', 'workflows'):
                backend.execute(f'DELETE FROM {table}', connection=pg_conn)

        cursor = sqlite_conn.execute("SELECT * FROM workflows")
        with backend.transaction() as pg_conn:
            insert_order = [
                'tenant_id', 'name', 'version', 'owner_id', 'visibility', 'description', 'tags',
                'definition_json', 'created_at', 'updated_at', 'is_active', 'id'
            ]
            while rows := cursor.fetchmany(batch_size):
                params = []
                for row in rows:
                    values = []
                    for col in insert_order:
                        val = row[col]
                        if col == 'is_active' and val is not None:
                            val = bool(val)
                        values.append(val)
                    params.append(tuple(values))
                backend.execute_many(
                    (
                        'INSERT INTO workflows ('
                        'tenant_id, name, version, owner_id, visibility, description, tags, definition_json, '
                        'created_at, updated_at, is_active, id'
                        ') VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) '
                        'ON CONFLICT (id) DO NOTHING'
                    ),
                    params,
                    connection=pg_conn,
                )

        for table in (
            ('workflow_runs', 'run_id'),
            ('workflow_step_runs', 'step_run_id'),
            ('workflow_events', 'event_id'),
            ('workflow_artifacts', 'artifact_id'),
        ):
            name, pk = table
            columns = [col['name'] for col in sqlite_conn.execute(f'PRAGMA table_info("{name}")')]
            select_sql = f'SELECT {", ".join(columns)} FROM "{name}"'
            cursor = sqlite_conn.execute(select_sql)
            with backend.transaction() as pg_conn:
                # Discover boolean columns for coercion
                try:
                    pg_cols_info = backend.get_table_info(name, connection=pg_conn)
                    bool_cols = {
                        (row.get('name') or '').lower()
                        for row in pg_cols_info
                        if isinstance(row.get('type'), str) and 'bool' in row['type'].lower()
                    }
                except Exception:
                    bool_cols = set()
                while rows := cursor.fetchmany(batch_size):
                    params = []
                    for row in rows:
                        vals = []
                        for col in columns:
                            v = row[col]
                            if col.lower() in bool_cols and v is not None:
                                if isinstance(v, bool):
                                    vals.append(v)
                                elif isinstance(v, (int,)):
                                    vals.append(bool(v))
                                elif isinstance(v, str) and v.strip().lower() in {'0','1','t','f','true','false'}:
                                    vals.append(v.strip().lower() in {'1','t','true'})
                                else:
                                    vals.append(bool(v))
                            else:
                                vals.append(v)
                        params.append(tuple(vals))
                    placeholders = ', '.join(['%s'] * len(columns))
                    backend.execute_many(
                        (
                            f'INSERT INTO {name} ({", ".join(columns)}) '
                            f'VALUES ({placeholders}) ON CONFLICT ({pk}) DO NOTHING'
                        ),
                        params,
                        connection=pg_conn,
                    )

        with backend.transaction() as pg_conn:
            result_runs = backend.execute(
                'SELECT COUNT(*) AS cnt FROM workflow_runs',
                connection=pg_conn,
            )
            result_defs = backend.execute(
                'SELECT COUNT(*) AS cnt FROM workflows',
                connection=pg_conn,
            )
        run_count = int(result_runs.scalar or 0)
        def_count = int(result_defs.scalar or 0)
        logger.info(
            'Completed migration of workflows database (%s definitions, %s runs)',
            def_count,
            run_count,
        )
    finally:
        try:
            backend.get_pool().close_all()
        except Exception:
            pass
        sqlite_conn.close()


def _introspect_sqlite_schema(
    conn: sqlite3.Connection,
    skip_tables: Optional[Iterable[str]] = None,
) -> Dict[str, TableMeta]:
    configured_skips = {name.lower() for name in (skip_tables or [])}
    tables: Dict[str, TableMeta] = {}

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = [row[0] for row in cursor.fetchall()]

    for raw_name in table_names:
        normalized = raw_name.lower()
        if normalized.startswith('sqlite_'):
            continue
        if any(normalized.endswith(suffix) for suffix in _DEFAULT_SKIP_SUFFIXES):
            continue
        if normalized in configured_skips:
            continue

        columns_info = conn.execute(f'PRAGMA table_info("{raw_name}")').fetchall()
        if not columns_info:
            continue
        columns = [row['name'] for row in columns_info]
        pk_columns = [row['name'] for row in columns_info if row['pk']]
        sequence_columns = [
            row['name']
            for row in columns_info
            if row['pk'] and (row['type'] or '').upper().find('INT') != -1
        ]

        dependencies = set()
        fk_rows = conn.execute(f'PRAGMA foreign_key_list("{raw_name}")').fetchall()
        for fk in fk_rows:
            ref_table = fk['table'].lower()
            if ref_table and ref_table not in configured_skips:
                dependencies.add(ref_table)

        meta = TableMeta(
            name=normalized,
            source_name=raw_name,
            columns=columns,
            pg_columns=columns.copy(),
            pk_columns=pk_columns,
            sequence_columns=sequence_columns,
            dependencies=dependencies,
        )
        tables[meta.name] = meta
    return tables


def _topological_sort(tables: Dict[str, TableMeta]) -> List[str]:
    indegree: Dict[str, int] = {name: 0 for name in tables}
    adjacency: Dict[str, Set[str]] = {name: set() for name in tables}

    for table in tables.values():
        for dep in table.dependencies:
            if dep not in tables:
                continue
            indegree[table.name] += 1
            adjacency.setdefault(dep, set()).add(table.name)

    queue: List[str] = [name for name, degree in indegree.items() if degree == 0]
    order: List[str] = []

    while queue:
        current = queue.pop(0)
        order.append(current)
        for neighbour in adjacency.get(current, set()):
            indegree[neighbour] -= 1
            if indegree[neighbour] == 0:
                queue.append(neighbour)

    if len(order) != len(tables):
        unresolved = {name for name, degree in indegree.items() if degree > 0}
        raise RuntimeError(f'Cycle detected in table dependencies: {unresolved}')

    return order


def _truncate_tables(
    backend: DatabaseBackend,
    pg_conn,
    insertion_order: Sequence[str],
) -> None:
    for table_name in reversed(list(insertion_order)):
        sql = f'DELETE FROM {table_name}'
        try:
            backend.execute(sql, connection=pg_conn)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning('Unable to clear table %s: %s', table_name, exc)


def _copy_table(
    sqlite_conn: sqlite3.Connection,
    backend: DatabaseBackend,
    pg_conn,
    meta: TableMeta,
    batch_size: int,
) -> None:
    column_list = ', '.join([f'"{col}"' for col in meta.columns])
    select_sql = f'SELECT {column_list} FROM "{meta.source_name}"'
    insert_columns = ', '.join(meta.pg_columns)
    placeholders = ', '.join(['%s'] * len(meta.pg_columns))
    insert_sql = (
        f'INSERT INTO {meta.name} ({insert_columns}) '
        f'VALUES ({placeholders}) ON CONFLICT DO NOTHING'
    )

    # Discover boolean columns on the target table for type coercion
    try:
        pg_columns_info = backend.get_table_info(meta.name, connection=pg_conn)
        boolean_columns = {
            (row.get('name') or '').lower()
            for row in pg_columns_info
            if isinstance(row.get('type'), str) and 'bool' in row['type'].lower()
        }
    except Exception:
        boolean_columns = set()

    cursor = sqlite_conn.execute(select_sql)
    total = 0
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        converted_params: List[Tuple] = []
        for row in rows:
            values: List = []
            for col in meta.columns:
                val = row[col]
                if col.lower() in boolean_columns and val is not None:
                    try:
                        if isinstance(val, bool):
                            coerced = val
                        elif isinstance(val, (int,)):
                            coerced = bool(val)
                        elif isinstance(val, str) and val.strip() in {'0', '1', 't', 'f', 'true', 'false'}:
                            low = val.strip().lower()
                            coerced = True if low in {'1', 't', 'true'} else False
                        else:
                            coerced = bool(val)
                        values.append(coerced)
                    except Exception:
                        values.append(val)
                else:
                    values.append(val)
            converted_params.append(tuple(values))
        params = converted_params
        backend.execute_many(insert_sql, params, connection=pg_conn)
        total += len(params)
    logger.info('Copied %s rows into %s', total, meta.name)


def _sync_sequences(
    backend: DatabaseBackend,
    pg_conn,
    tables: Dict[str, TableMeta],
) -> None:
    for meta in tables.values():
        for column in meta.sequence_columns:
            sql = (
                f"SELECT setval("
                f"pg_get_serial_sequence('{meta.name}', '{column}'), "
                f"COALESCE((SELECT MAX({column}) FROM {meta.name}), 0) + 1, false)"
            )
            try:
                backend.execute(sql, connection=pg_conn)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning('Sequence sync failed for %s.%s: %s', meta.name, column, exc)


def _build_postgres_config_from_args(args: argparse.Namespace) -> DatabaseConfig:
    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_database=args.pg_database,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
        pg_sslmode=args.pg_sslmode,
        pool_size=args.pg_pool_size,
        max_overflow=args.pg_max_overflow,
        connect_timeout=args.pg_timeout,
    )


def _iter_migration_targets(args: argparse.Namespace) -> Iterator[Tuple[str, Path]]:
    if args.content_sqlite:
        yield 'content', Path(args.content_sqlite)
    if args.chacha_sqlite:
        yield 'chacha', Path(args.chacha_sqlite)
    if args.analytics_sqlite:
        yield 'analytics', Path(args.analytics_sqlite)
    if getattr(args, 'evaluations_sqlite', None):
        yield 'evaluations', Path(args.evaluations_sqlite)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description='Migrate SQLite databases to PostgreSQL.')
    parser.add_argument('--content-sqlite', help='Path to Media_DB_v2.db to migrate')
    parser.add_argument('--chacha-sqlite', help='Path to ChaChaNotes.db to migrate (optional)')
    parser.add_argument('--analytics-sqlite', help='Path to Analytics.db to migrate (optional)')
    parser.add_argument('--evaluations-sqlite', help='Path to evaluations.db to migrate (optional)')
    parser.add_argument('--workflows-sqlite', help='Path to workflows.db to migrate (optional)')
    parser.add_argument('--pg-host', default='localhost')
    parser.add_argument('--pg-port', default=5432, type=int)
    parser.add_argument('--pg-database', default='tldw_content')
    parser.add_argument('--pg-user', default='tldw_user')
    parser.add_argument('--pg-password', default='')
    parser.add_argument('--pg-sslmode', default='prefer')
    parser.add_argument('--pg-pool-size', default=10, type=int)
    parser.add_argument('--pg-max-overflow', default=20, type=int)
    parser.add_argument('--pg-timeout', default=10, type=int)
    parser.add_argument('--batch-size', default=500, type=int)
    parser.add_argument('--skip-table', action='append', help='Additional tables to skip')
    parser.add_argument('--log-level', default='INFO')

    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    targets = list(_iter_migration_targets(args))
    if args.workflows_sqlite:
        workflow_path = Path(args.workflows_sqlite)
        if not workflow_path.exists():
            parser.error(f'Workflows SQLite database not found: {workflow_path}')
    if not targets and not args.workflows_sqlite:
        parser.error('At least one SQLite database path must be provided')

    config = _build_postgres_config_from_args(args)
    # Pre-initialize target PostgreSQL schemas where needed so row copy succeeds
    try:
        # Only initialize Evaluations schema if that target is requested
        if any(label == 'evaluations' for (label, _path) in targets):
            from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory as _Fac
            from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase as _Evals
            _backend = _Fac.create_backend(config)
            # Instantiate to create tables/indexes; uses provided backend
            _ = _Evals(db_path=':memory:', backend=_backend)
            try:
                _backend.get_pool().close_all()
            except Exception:
                pass
    except Exception as _init_exc:  # pragma: no cover - defensive
        logger.warning('Could not pre-initialize PostgreSQL schema: %s', _init_exc)
    for label, path in targets:
        migrate_sqlite_to_postgres(
            path,
            config,
            batch_size=args.batch_size,
            skip_tables=args.skip_table,
            label=label,
        )

    if args.workflows_sqlite:
        migrate_workflows_sqlite_to_postgres(
            Path(args.workflows_sqlite),
            config,
            batch_size=args.batch_size,
        )
    return 0


if __name__ == '__main__':  # pragma: no cover - CLI entry
    raise SystemExit(main())
