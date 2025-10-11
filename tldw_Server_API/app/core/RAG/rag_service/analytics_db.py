
"""
Analytics database schema and management for server-side QA metrics.

This module handles the creation and management of the Analytics database
for storing anonymized metrics and quality assurance data across both
SQLite and PostgreSQL backends.
"""

from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from configparser import ConfigParser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from loguru import logger

from tldw_Server_API.app.core.DB_Management.backends.base import (
    BackendType,
    DatabaseBackend,
    DatabaseConfig,
    DatabaseError as BackendDatabaseError,
    QueryResult,
)
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.DB_Management.backends.query_utils import (
    prepare_backend_statement,
)
from tldw_Server_API.app.core.DB_Management.content_backend import get_content_backend
from tldw_Server_API.app.core.config import load_comprehensive_config


class BackendCursorAdapter:
    """Adapter exposing QueryResult via a cursor-like interface."""

    def __init__(self, result: QueryResult):
        self._result = result
        self._index = 0
        self.rowcount = result.rowcount
        self.lastrowid = result.lastrowid
        self.description = result.description

    def fetchall(self):
        return list(self._result.rows)

    def fetchone(self):
        if self._index >= len(self._result.rows):
            return None
        row = self._result.rows[self._index]
        self._index += 1
        return row

    def fetchmany(self, size: Optional[int] = None):
        if size is None or size <= 0:
            size = len(self._result.rows) - self._index
        end = min(self._index + size, len(self._result.rows))
        rows = self._result.rows[self._index:end]
        self._index = end
        return list(rows)

    def __iter__(self):
        return iter(self._result.rows)

    def close(self):
        self._result = QueryResult(rows=[], rowcount=0)
        self.rowcount = 0
        self.lastrowid = None
        self.description = None


class AnalyticsDatabase:
    """
    Manages analytics storage for server-side QA metrics across supported backends.

    The database records anonymized metrics that help evaluate retrieval and
    generation quality without storing any PII. When PostgreSQL is configured
    as the content backend, analytics automatically use the same backend to
    ensure all large-scale deployments avoid SQLite.
    """

    _SCHEMA_SQLITE = """
    CREATE TABLE IF NOT EXISTS search_analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        query_hash TEXT NOT NULL,
        query_length INTEGER,
        query_complexity TEXT,
        search_type TEXT,
        results_count INTEGER,
        max_score REAL,
        avg_score REAL,
        response_time_ms INTEGER,
        cache_hit BOOLEAN,
        reranking_used BOOLEAN,
        expansion_used BOOLEAN,
        filters_used TEXT,
        error_occurred BOOLEAN DEFAULT FALSE,
        error_type TEXT
    );

    CREATE TABLE IF NOT EXISTS document_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        document_hash TEXT NOT NULL,
        document_type TEXT,
        chunk_size INTEGER,
        retrieval_count INTEGER DEFAULT 0,
        avg_relevance_score REAL,
        citation_count INTEGER DEFAULT 0,
        feedback_positive INTEGER DEFAULT 0,
        feedback_negative INTEGER DEFAULT 0,
        last_accessed TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS feedback_analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        session_hash TEXT NOT NULL,
        query_hash TEXT NOT NULL,
        feedback_type TEXT,
        rating INTEGER,
        response_quality TEXT,
        retrieval_accuracy TEXT,
        response_time_acceptable BOOLEAN,
        categories TEXT,
        improvement_areas TEXT
    );

    CREATE TABLE IF NOT EXISTS citation_analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        citation_style TEXT,
        document_count INTEGER,
        chunk_count INTEGER,
        verification_requested BOOLEAN,
        format_errors INTEGER DEFAULT 0,
        generation_time_ms INTEGER
    );

    CREATE TABLE IF NOT EXISTS error_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        error_type TEXT NOT NULL,
        error_category TEXT,
        error_hash TEXT,
        component TEXT,
        severity TEXT,
        frequency INTEGER DEFAULT 1,
        resolved BOOLEAN DEFAULT FALSE,
        resolution_time TIMESTAMP,
        stack_trace_hash TEXT
    );

    CREATE TABLE IF NOT EXISTS system_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metric_type TEXT NOT NULL,
        metric_value REAL,
        component TEXT,
        operation TEXT,
        duration_ms INTEGER,
        memory_mb REAL,
        cpu_percent REAL
    );

    CREATE TABLE IF NOT EXISTS feature_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        feature_name TEXT NOT NULL,
        usage_count INTEGER DEFAULT 1,
        success_count INTEGER DEFAULT 0,
        failure_count INTEGER DEFAULT 0,
        avg_execution_time_ms INTEGER,
        last_used TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS query_patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern_hash TEXT UNIQUE NOT NULL,
        pattern_type TEXT,
        frequency INTEGER DEFAULT 1,
        avg_results_quality REAL,
        avg_response_time_ms INTEGER,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ab_testing (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        test_name TEXT NOT NULL,
        variant TEXT NOT NULL,
        session_hash TEXT,
        metric_name TEXT,
        metric_value REAL,
        conversion BOOLEAN
    );
    """

    _SCHEMA_POSTGRES = """
    CREATE TABLE IF NOT EXISTS search_analytics (
        id BIGSERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        query_hash TEXT NOT NULL,
        query_length INTEGER,
        query_complexity TEXT,
        search_type TEXT,
        results_count INTEGER,
        max_score DOUBLE PRECISION,
        avg_score DOUBLE PRECISION,
        response_time_ms INTEGER,
        cache_hit BOOLEAN,
        reranking_used BOOLEAN,
        expansion_used BOOLEAN,
        filters_used TEXT,
        error_occurred BOOLEAN DEFAULT FALSE,
        error_type TEXT
    );

    CREATE TABLE IF NOT EXISTS document_performance (
        id BIGSERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        document_hash TEXT NOT NULL,
        document_type TEXT,
        chunk_size INTEGER,
        retrieval_count INTEGER DEFAULT 0,
        avg_relevance_score DOUBLE PRECISION,
        citation_count INTEGER DEFAULT 0,
        feedback_positive INTEGER DEFAULT 0,
        feedback_negative INTEGER DEFAULT 0,
        last_accessed TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS feedback_analytics (
        id BIGSERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        session_hash TEXT NOT NULL,
        query_hash TEXT NOT NULL,
        feedback_type TEXT,
        rating INTEGER,
        response_quality TEXT,
        retrieval_accuracy TEXT,
        response_time_acceptable BOOLEAN,
        categories TEXT,
        improvement_areas TEXT
    );

    CREATE TABLE IF NOT EXISTS citation_analytics (
        id BIGSERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        citation_style TEXT,
        document_count INTEGER,
        chunk_count INTEGER,
        verification_requested BOOLEAN,
        format_errors INTEGER DEFAULT 0,
        generation_time_ms INTEGER
    );

    CREATE TABLE IF NOT EXISTS error_tracking (
        id BIGSERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        error_type TEXT NOT NULL,
        error_category TEXT,
        error_hash TEXT,
        component TEXT,
        severity TEXT,
        frequency INTEGER DEFAULT 1,
        resolved BOOLEAN DEFAULT FALSE,
        resolution_time TIMESTAMP,
        stack_trace_hash TEXT
    );

    CREATE TABLE IF NOT EXISTS system_performance (
        id BIGSERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metric_type TEXT NOT NULL,
        metric_value DOUBLE PRECISION,
        component TEXT,
        operation TEXT,
        duration_ms INTEGER,
        memory_mb DOUBLE PRECISION,
        cpu_percent DOUBLE PRECISION
    );

    CREATE TABLE IF NOT EXISTS feature_usage (
        id BIGSERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        feature_name TEXT NOT NULL,
        usage_count INTEGER DEFAULT 1,
        success_count INTEGER DEFAULT 0,
        failure_count INTEGER DEFAULT 0,
        avg_execution_time_ms INTEGER,
        last_used TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS query_patterns (
        id BIGSERIAL PRIMARY KEY,
        pattern_hash TEXT UNIQUE NOT NULL,
        pattern_type TEXT,
        frequency INTEGER DEFAULT 1,
        avg_results_quality DOUBLE PRECISION,
        avg_response_time_ms INTEGER,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ab_testing (
        id BIGSERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        test_name TEXT NOT NULL,
        variant TEXT NOT NULL,
        session_hash TEXT,
        metric_name TEXT,
        metric_value DOUBLE PRECISION,
        conversion BOOLEAN
    );
    """

    _INDEX_STATEMENTS: Tuple[str, ...] = (
        "CREATE INDEX IF NOT EXISTS idx_search_timestamp ON search_analytics(timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_document_hash ON document_performance(document_hash)",
        "CREATE INDEX IF NOT EXISTS idx_feedback_session ON feedback_analytics(session_hash)",
        "CREATE INDEX IF NOT EXISTS idx_error_type ON error_tracking(error_type, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_feature_name ON feature_usage(feature_name, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_query_pattern ON query_patterns(pattern_hash)",
        "CREATE INDEX IF NOT EXISTS idx_ab_test ON ab_testing(test_name, variant)"
    )

    def __init__(
        self,
        db_path: str = "Analytics.db",
        *,
        backend: Optional[DatabaseBackend] = None,
        config: Optional[ConfigParser] = None,
    ) -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        self._local = threading.local()

        self.backend = self._resolve_backend(db_path=db_path, backend=backend, config=config)
        self.backend_type = self.backend.backend_type
        self._db_identifier = self._describe_backend()

        if self.backend_type == BackendType.SQLITE:
            path_obj = Path(db_path).expanduser().resolve()
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = str(path_obj)

        logger.info(
            "Initializing AnalyticsDatabase (backend=%s) at %s",
            self.backend_type.value,
            self._db_identifier,
        )
        self._initialize_database()

    def _load_config(self) -> Optional[ConfigParser]:
        try:
            return load_comprehensive_config()
        except Exception:
            return None

    def _describe_backend(self) -> str:
        if self.backend_type == BackendType.SQLITE:
            return str(Path(self.db_path).expanduser())
        cfg = self.backend.config
        if cfg.connection_string:
            return cfg.connection_string
        host = cfg.pg_host or "localhost"
        database = cfg.pg_database or "tldw_content"
        return f"{host}:{cfg.pg_port}/{database}"

    def _resolve_backend(
        self,
        *,
        db_path: str,
        backend: Optional[DatabaseBackend],
        config: Optional[ConfigParser],
    ) -> DatabaseBackend:
        if backend is not None:
            return backend

        parser = config or self._load_config()
        if parser is not None:
            candidate = get_content_backend(parser)
            if candidate and candidate.backend_type == BackendType.POSTGRESQL:
                return candidate

        sqlite_config = DatabaseConfig(
            backend_type=BackendType.SQLITE,
            sqlite_path=str(Path(db_path).expanduser()),
        )
        return DatabaseBackendFactory.create_backend(sqlite_config)

    def _initialize_database(self) -> None:
        schema = self._SCHEMA_SQLITE if self.backend_type == BackendType.SQLITE else self._SCHEMA_POSTGRES
        try:
            with self.backend.transaction() as conn:
                self.backend.create_tables(schema, connection=conn)
                for statement in self._INDEX_STATEMENTS:
                    self._execute(conn, statement)
            logger.info("Analytics database initialized at %s", self._db_identifier)
        except Exception as exc:
            logger.error("Failed to initialize analytics database: %s", exc)
            raise

    def _prepare_backend_statement(
        self,
        query: str,
        params: Optional[Union[Tuple, List, Dict]] = None,
    ) -> Tuple[str, Optional[Union[Tuple, Dict]]]:
        return prepare_backend_statement(
            self.backend_type,
            query,
            params,
            ensure_returning=self.backend_type == BackendType.POSTGRESQL,
        )

    def _execute(
        self,
        conn,
        query: str,
        params: Optional[Union[Tuple, List, Dict]] = None,
    ):
        prepared_query, prepared_params = self._prepare_backend_statement(query, params)

        if self.backend_type == BackendType.SQLITE:
            cursor = conn.cursor()
            cursor.execute(prepared_query, prepared_params or ())
            return cursor

        try:
            result = self.backend.execute(
                prepared_query,
                prepared_params,
                connection=conn,
            )
            return BackendCursorAdapter(result)
        except BackendDatabaseError as exc:
            logger.error("Backend execute failed: %s", exc)
            raise

    def _fetchone(
        self,
        conn,
        query: str,
        params: Optional[Union[Tuple, List, Dict]] = None,
    ) -> Optional[Dict[str, Any]]:
        cursor = self._execute(conn, query, params)
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def _fetchall(
        self,
        conn,
        query: str,
        params: Optional[Union[Tuple, List, Dict]] = None,
    ) -> List[Dict[str, Any]]:
        cursor = self._execute(conn, query, params)
        rows = cursor.fetchall() or []
        return [dict(r) for r in rows]

    @contextmanager
    def transaction(self):
        with self.backend.transaction() as conn:
            yield conn

    def record_search(self, search_data: Dict[str, Any]) -> None:
        try:
            with self.transaction() as conn:
                query_hash = hashlib.sha256(search_data.get('query', '').encode()).hexdigest()[:16]
                raw_query = (
                    """
                    INSERT INTO search_analytics (
                        query_hash, query_length, query_complexity, search_type,
                        results_count, max_score, avg_score, response_time_ms,
                        cache_hit, reranking_used, expansion_used, filters_used,
                        error_occurred, error_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                )
                raw_params = (
                    query_hash,
                    search_data.get('query_length'),
                    search_data.get('query_complexity'),
                    search_data.get('search_type'),
                    search_data.get('results_count'),
                    search_data.get('max_score'),
                    search_data.get('avg_score'),
                    search_data.get('response_time_ms'),
                    search_data.get('cache_hit', False),
                    search_data.get('reranking_used', False),
                    search_data.get('expansion_used', False),
                    json.dumps(search_data.get('filters_used', [])),
                    search_data.get('error_occurred', False),
                    search_data.get('error_type'),
                )
                prepared_query, prepared_params = self._prepare_backend_statement(raw_query, raw_params)
                self._execute(conn, prepared_query, prepared_params)
                logger.debug("Recorded search analytics for query hash: %s", query_hash)
        except Exception as exc:
            logger.error("Failed to record search analytics: %s", exc)

    def record_document_performance(self, doc_data: Dict[str, Any]) -> None:
        try:
            with self.transaction() as conn:
                doc_hash = hashlib.sha256(str(doc_data.get('document_id', '')).encode()).hexdigest()[:16]
                existing = self._fetchone(
                    conn,
                    """
                    SELECT id, retrieval_count, citation_count,
                           feedback_positive, feedback_negative
                      FROM document_performance
                     WHERE document_hash = ?
                    """,
                    (doc_hash,),
                )

                if existing:
                    self._execute(
                        conn,
                        """
                        UPDATE document_performance
                           SET retrieval_count = retrieval_count + ?,
                               citation_count = citation_count + ?,
                               feedback_positive = feedback_positive + ?,
                               feedback_negative = feedback_negative + ?,
                               avg_relevance_score =
                                   (avg_relevance_score * retrieval_count + ?) /
                                   (retrieval_count + 1),
                               last_accessed = CURRENT_TIMESTAMP
                         WHERE document_hash = ?
                        """,
                        (
                            1 if doc_data.get('retrieved') else 0,
                            1 if doc_data.get('cited') else 0,
                            1 if doc_data.get('feedback') == 'positive' else 0,
                            1 if doc_data.get('feedback') == 'negative' else 0,
                            doc_data.get('relevance_score', 0),
                            doc_hash,
                        ),
                    )
                else:
                    self._execute(
                        conn,
                        """
                        INSERT INTO document_performance (
                            document_hash, document_type, chunk_size,
                            retrieval_count, avg_relevance_score, citation_count,
                            feedback_positive, feedback_negative, last_accessed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            doc_hash,
                            doc_data.get('document_type'),
                            doc_data.get('chunk_size'),
                            1 if doc_data.get('retrieved') else 0,
                            doc_data.get('relevance_score', 0),
                            1 if doc_data.get('cited') else 0,
                            1 if doc_data.get('feedback') == 'positive' else 0,
                            1 if doc_data.get('feedback') == 'negative' else 0,
                        ),
                    )
                logger.debug("Recorded document performance for hash: %s", doc_hash)
        except Exception as exc:
            logger.error("Failed to record document performance: %s", exc)

    def record_feedback(self, feedback_data: Dict[str, Any]) -> None:
        try:
            with self.transaction() as conn:
                session_hash = hashlib.sha256(str(feedback_data.get('session_id', '')).encode()).hexdigest()[:16]
                query_hash = hashlib.sha256(feedback_data.get('query', '').encode()).hexdigest()[:16]
                self._execute(
                    conn,
                    """
                    INSERT INTO feedback_analytics (
                        session_hash, query_hash, feedback_type, rating,
                        response_quality, retrieval_accuracy,
                        response_time_acceptable, categories, improvement_areas
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_hash,
                        query_hash,
                        feedback_data.get('feedback_type'),
                        feedback_data.get('rating'),
                        feedback_data.get('response_quality'),
                        feedback_data.get('retrieval_accuracy'),
                        feedback_data.get('response_time_acceptable'),
                        json.dumps(feedback_data.get('categories', [])),
                        json.dumps(feedback_data.get('improvement_areas', [])),
                    ),
                )
                logger.debug("Recorded feedback for session: %s", session_hash)
        except Exception as exc:
            logger.error("Failed to record feedback: %s", exc)

    def record_error(self, error_data: Dict[str, Any]) -> None:
        try:
            with self.transaction() as conn:
                error_hash = hashlib.sha256(
                    f"{error_data.get('error_type', '')}:{error_data.get('component', '')}".encode()
                ).hexdigest()[:16]
                stack_hash = None
                if error_data.get('stack_trace'):
                    stack_hash = hashlib.sha256(error_data['stack_trace'].encode()).hexdigest()[:16]

                existing = self._fetchone(
                    conn,
                    """
                    SELECT id, frequency FROM error_tracking
                     WHERE error_hash = ? AND resolved = FALSE
                    """,
                    (error_hash,),
                )

                if existing:
                    self._execute(
                        conn,
                        """
                        UPDATE error_tracking
                           SET frequency = frequency + 1,
                               timestamp = CURRENT_TIMESTAMP
                         WHERE id = ?
                        """,
                        (existing['id'],),
                    )
                else:
                    self._execute(
                        conn,
                        """
                        INSERT INTO error_tracking (
                            error_type, error_category, error_hash, component,
                            severity, frequency, stack_trace_hash
                        ) VALUES (?, ?, ?, ?, ?, 1, ?)
                        """,
                        (
                            error_data.get('error_type'),
                            error_data.get('error_category'),
                            error_hash,
                            error_data.get('component'),
                            error_data.get('severity', 'medium'),
                            stack_hash,
                        ),
                    )
                logger.debug("Recorded error: %s", error_hash)
        except Exception as exc:
            logger.error("Failed to record error: %s", exc)

    def record_feature_usage(self, feature_data: Dict[str, Any]) -> None:
        try:
            with self.transaction() as conn:
                feature_name = feature_data.get('feature_name')
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                tomorrow_start = today_start + timedelta(days=1)

                existing = self._fetchone(
                    conn,
                    """
                    SELECT id FROM feature_usage
                     WHERE feature_name = ?
                       AND timestamp >= ?
                       AND timestamp < ?
                    """,
                    (
                        feature_name,
                        today_start.isoformat(),
                        tomorrow_start.isoformat(),
                    ),
                )

                if existing:
                    self._execute(
                        conn,
                        """
                        UPDATE feature_usage
                           SET usage_count = usage_count + 1,
                               success_count = success_count + ?,
                               failure_count = failure_count + ?,
                               avg_execution_time_ms =
                                   (avg_execution_time_ms * usage_count + ?) /
                                   (usage_count + 1),
                               last_used = CURRENT_TIMESTAMP
                         WHERE id = ?
                        """,
                        (
                            1 if feature_data.get('success') else 0,
                            1 if not feature_data.get('success') else 0,
                            feature_data.get('execution_time_ms', 0),
                            existing['id'],
                        ),
                    )
                else:
                    self._execute(
                        conn,
                        """
                        INSERT INTO feature_usage (
                            feature_name, usage_count, success_count,
                            failure_count, avg_execution_time_ms, last_used
                        ) VALUES (?, 1, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            feature_name,
                            1 if feature_data.get('success') else 0,
                            1 if not feature_data.get('success') else 0,
                            feature_data.get('execution_time_ms', 0),
                        ),
                    )
                logger.debug("Recorded feature usage: %s", feature_name)
        except Exception as exc:
            logger.error("Failed to record feature usage: %s", exc)

    def get_analytics_summary(self, days: int = 7) -> Dict[str, Any]:
        try:
            with self._lock:
                threshold = datetime.utcnow() - timedelta(days=days)
                threshold_iso = threshold.isoformat()
                with self.transaction() as conn:
                    search_stats = self._fetchone(
                        conn,
                        """
                        SELECT
                            COUNT(*) AS total_searches,
                            AVG(response_time_ms) AS avg_response_time,
                            AVG(results_count) AS avg_results,
                            CASE WHEN COUNT(*) = 0 THEN 0
                                 ELSE SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
                            END AS cache_hit_rate,
                            CASE WHEN COUNT(*) = 0 THEN 0
                                 ELSE SUM(CASE WHEN error_occurred THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
                            END AS error_rate
                          FROM search_analytics
                         WHERE timestamp > ?
                        """,
                        (threshold_iso,),
                    ) or {
                        'total_searches': 0,
                        'avg_response_time': 0,
                        'avg_results': 0,
                        'cache_hit_rate': 0,
                        'error_rate': 0,
                    }

                    doc_stats = self._fetchone(
                        conn,
                        """
                        SELECT
                            COUNT(*) AS total_documents,
                            SUM(retrieval_count) AS total_retrievals,
                            SUM(citation_count) AS total_citations,
                            AVG(avg_relevance_score) AS avg_relevance,
                            SUM(feedback_positive) AS positive_feedback,
                            SUM(feedback_negative) AS negative_feedback
                          FROM document_performance
                         WHERE timestamp > ?
                        """,
                        (threshold_iso,),
                    ) or {
                        'total_documents': 0,
                        'total_retrievals': 0,
                        'total_citations': 0,
                        'avg_relevance': 0,
                        'positive_feedback': 0,
                        'negative_feedback': 0,
                    }

                    top_features = self._fetchall(
                        conn,
                        """
                        SELECT
                            feature_name,
                            SUM(usage_count) AS total_usage,
                            CASE WHEN SUM(usage_count) = 0 THEN 0
                                 ELSE SUM(success_count) * 100.0 / SUM(usage_count)
                            END AS success_rate
                          FROM feature_usage
                         WHERE timestamp > ?
                         GROUP BY feature_name
                         ORDER BY total_usage DESC
                         LIMIT 5
                        """,
                        (threshold_iso,),
                    )

                    top_errors = self._fetchall(
                        conn,
                        """
                        SELECT
                            error_type,
                            COUNT(*) AS occurrences,
                            MAX(timestamp) AS last_seen
                          FROM error_tracking
                         WHERE timestamp > ?
                         GROUP BY error_type
                         ORDER BY occurrences DESC
                         LIMIT 5
                        """,
                        (threshold_iso,),
                    )

                return {
                    'period_days': days,
                    'search_analytics': search_stats,
                    'document_performance': doc_stats,
                    'top_features': top_features,
                    'top_errors': top_errors,
                    'generated_at': datetime.utcnow().isoformat(),
                }
        except Exception as exc:
            logger.error("Failed to get analytics summary: %s", exc)
            return {}

    def cleanup_old_data(self, days_to_keep: int = 90) -> int:
        try:
            threshold = datetime.utcnow() - timedelta(days=days_to_keep)
            threshold_iso = threshold.isoformat()
            total_deleted = 0

            with self.transaction() as conn:
                for table in (
                    'search_analytics',
                    'document_performance',
                    'feedback_analytics',
                    'citation_analytics',
                    'error_tracking',
                    'system_performance',
                    'feature_usage',
                    'ab_testing',
                ):
                    cursor = self._execute(
                        conn,
                        f"DELETE FROM {table} WHERE timestamp < ?",
                        (threshold_iso,),
                    )
                    total_deleted += cursor.rowcount or 0

            if total_deleted and self.backend_type == BackendType.SQLITE:
                try:
                    self.backend.vacuum()
                except Exception as exc:
                    logger.warning("SQLite vacuum failed after cleanup: %s", exc)

            logger.info("Cleanup complete. Deleted %s total records", total_deleted)
            return total_deleted
        except Exception as exc:
            logger.error("Failed to cleanup old data: %s", exc)
            return 0

    def close(self) -> None:
        logger.debug("AnalyticsDatabase.close called for backend %s", self.backend_type.value)


_analytics_db: Optional[AnalyticsDatabase] = None
_analytics_lock = threading.Lock()


def get_analytics_db(
    db_path: str = "Analytics.db",
    *,
    backend: Optional[DatabaseBackend] = None,
    config: Optional[ConfigParser] = None,
) -> AnalyticsDatabase:
    global _analytics_db

    with _analytics_lock:
        if _analytics_db is None:
            _analytics_db = AnalyticsDatabase(db_path, backend=backend, config=config)
        return _analytics_db
