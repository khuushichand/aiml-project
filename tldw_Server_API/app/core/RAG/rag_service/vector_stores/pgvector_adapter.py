"""
PGVector adapter implementation for VectorStoreAdapter.

Notes:
- Uses psycopg/psycopg2 when available; imports deferred until initialize() to avoid hard dependency at import time.
- Stores each logical collection in a separate table named vs_<sanitized_collection> with a vector column.
- Requires pgvector extension installed in the target database.
"""
from typing import List, Dict, Any, Optional
from loguru import logger
import asyncio
import re

from .base import VectorStoreAdapter, VectorStoreConfig, VectorSearchResult


class PGVectorAdapter(VectorStoreAdapter):
    def __init__(self, config: VectorStoreConfig):
        super().__init__(config)
        self._conn = None  # Will be psycopg/psycopg2 connection
        self._driver = None  # Module handle

    async def initialize(self) -> None:
        if self._initialized:
            return
        try:
            # Prefer psycopg (v3), fallback to psycopg2
            try:
                import psycopg
                self._driver = 'psycopg'
                dsn = self._build_dsn(self.config.connection_params)
                self._conn = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: psycopg.connect(dsn)  # type: ignore
                )
            except Exception:
                import psycopg2  # type: ignore
                self._driver = 'psycopg2'
                dsn = self._build_dsn(self.config.connection_params)
                self._conn = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: psycopg2.connect(dsn)
                )

            # Ensure pgvector extension
            await self._exec("CREATE EXTENSION IF NOT EXISTS vector")
            self._initialized = True
            logger.info("PGVector adapter initialized")
        except Exception as e:
            logger.error(f"Failed to initialize PGVector adapter: {e}")
            self._conn = None
            self._initialized = False

    def _build_dsn(self, params: Dict[str, Any]) -> str:
        # Support both DSN and discrete params
        if params.get('dsn'):
            return str(params['dsn'])
        host = params.get('host', 'localhost')
        port = params.get('port', 5432)
        db = params.get('database', 'postgres')
        user = params.get('user', 'postgres')
        password = params.get('password', '')
        sslmode = params.get('sslmode', 'prefer')
        return f"host={host} port={port} dbname={db} user={user} password={password} sslmode={sslmode}"

    def _sanitize_collection(self, name: str) -> str:
        # Allow only alphanum and underscores; replace others with underscore
        safe = re.sub(r"[^A-Za-z0-9_]+", "_", name)
        return f"vs_{safe}"

    async def _exec(self, sql: str, params: Optional[tuple] = None) -> None:
        if not self._conn:
            raise RuntimeError("PGVector connection not initialized")
        def _run():
            cur = self._conn.cursor()
            cur.execute(sql, params or ())
            self._conn.commit()
            cur.close()
        await asyncio.get_event_loop().run_in_executor(None, _run)

    async def _query(self, sql: str, params: Optional[tuple] = None) -> List[tuple]:
        if not self._conn:
            raise RuntimeError("PGVector connection not initialized")
        def _run():
            cur = self._conn.cursor()
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            cur.close()
            return rows
        return await asyncio.get_event_loop().run_in_executor(None, _run)

    async def create_collection(self, collection_name: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        tbl = self._sanitize_collection(collection_name)
        dim = int(self.config.embedding_dim)
        metric = self.config.distance_metric or 'cosine'
        # Use ivfflat/hnsw only if configured by DBA; here we keep a basic table
        sql = (
            f"CREATE TABLE IF NOT EXISTS {tbl} ("
            "id TEXT PRIMARY KEY, "
            "content TEXT, "
            "metadata JSONB, "
            f"embedding vector({dim})"
            ")"
        )
        await self._exec(sql)
        # Optional index for speed
        if metric == 'cosine':
            idx_sql = f"CREATE INDEX IF NOT EXISTS {tbl}_embedding_cosine ON {tbl} USING ivfflat (embedding vector_cosine_ops)"
        elif metric == 'euclidean':
            idx_sql = f"CREATE INDEX IF NOT EXISTS {tbl}_embedding_l2 ON {tbl} USING ivfflat (embedding vector_l2_ops)"
        else:
            idx_sql = f"CREATE INDEX IF NOT EXISTS {tbl}_embedding_ip ON {tbl} USING ivfflat (embedding vector_ip_ops)"
        try:
            await self._exec(idx_sql)
        except Exception:
            # ivfflat requires ANALYZE and maintenance; ignore if not available
            pass

    async def delete_collection(self, collection_name: str) -> None:
        tbl = self._sanitize_collection(collection_name)
        await self._exec(f"DROP TABLE IF EXISTS {tbl}")

    async def list_collections(self) -> List[str]:
        sql = "SELECT tablename FROM pg_tables WHERE tablename LIKE 'vs_%'"
        rows = await self._query(sql)
        return [r[0] for r in rows]

    async def upsert_vectors(
        self,
        collection_name: str,
        ids: List[str],
        vectors: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]]
    ) -> None:
        self._validate_vectors(vectors)
        tbl = self._sanitize_collection(collection_name)
        values = list(zip(ids, documents, metadatas, vectors))
        # Use simple upsert
        async def _batch():
            if not self._conn:
                raise RuntimeError("PGVector connection not initialized")
            cur = self._conn.cursor()
            for _id, doc, meta, vec in values:
                cur.execute(
                    f"INSERT INTO {tbl}(id, content, metadata, embedding) VALUES (%s, %s, %s, %s) "
                    f"ON CONFLICT (id) DO UPDATE SET content=EXCLUDED.content, metadata=EXCLUDED.metadata, embedding=EXCLUDED.embedding",
                    (_id, doc, JsonDumper.dumps(meta), vec)  # type: ignore
                )
            self._conn.commit()
            cur.close()
        await asyncio.get_event_loop().run_in_executor(None, _batch)

    async def delete_vectors(self, collection_name: str, ids: List[str]) -> None:
        tbl = self._sanitize_collection(collection_name)
        async def _batch():
            cur = self._conn.cursor()
            cur.executemany(f"DELETE FROM {tbl} WHERE id=%s", [(i,) for i in ids])
            self._conn.commit()
            cur.close()
        await asyncio.get_event_loop().run_in_executor(None, _batch)

    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True
    ) -> List[VectorSearchResult]:
        tbl = self._sanitize_collection(collection_name)
        metric = self.config.distance_metric or 'cosine'
        # Build distance expression
        if metric == 'cosine':
            dist_expr = "embedding <=> %s"
        elif metric == 'euclidean':
            dist_expr = "embedding <-> %s"
        else:
            dist_expr = "embedding <#> %s"  # inner product
        sql = f"SELECT id, content, metadata, {dist_expr} AS distance FROM {tbl}"
        where_clauses = []
        params: List[Any] = [query_vector]
        if filter:
            # Simple JSONB @> filter match
            where_clauses.append("metadata @> %s")
            params.append(JsonDumper.dumps(filter))  # type: ignore
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        sql += " ORDER BY distance ASC LIMIT %s"
        params.append(int(k))
        rows = await self._query(sql, tuple(params))
        results: List[VectorSearchResult] = []
        for rid, content, metadata, distance in rows:
            # Convert distance to similarity in [0,1] by heuristic
            try:
                sim = 1.0 / (1.0 + float(distance))
            except Exception:
                sim = 0.0
            results.append(VectorSearchResult(
                id=str(rid),
                content=content or "",
                metadata=metadata if include_metadata and isinstance(metadata, dict) else {},
                score=sim,
                distance=float(distance) if distance is not None else 0.0,
            ))
        return results

    async def multi_search(
        self,
        collection_patterns: List[str],
        query_vector: List[float],
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        # Fetch matching tables and aggregate results
        all_tables = await self.list_collections()
        results: List[VectorSearchResult] = []
        for pattern in collection_patterns:
            regex = re.compile('^' + pattern.replace('*', '.*') + '$')
            for tbl in all_tables:
                if regex.match(tbl):
                    results.extend(await self.search(tbl, query_vector, k=k, filter=filter))
        # Sort by score desc and trim
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:k]

    async def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        tbl = self._sanitize_collection(collection_name)
        rows = await self._query(f"SELECT COUNT(*) FROM {tbl}")
        count = int(rows[0][0]) if rows else 0
        return {
            "collection": collection_name,
            "table": tbl,
            "count": count,
            "dim": self.config.embedding_dim,
            "metric": self.config.distance_metric,
        }

    async def optimize_collection(self, collection_name: str) -> None:
        # VACUUM/ANALYZE basic optimization
        tbl = self._sanitize_collection(collection_name)
        try:
            await self._exec(f"ANALYZE {tbl}")
        except Exception:
            pass

    async def close(self) -> None:
        try:
            if self._conn:
                await asyncio.get_event_loop().run_in_executor(None, self._conn.close)
        except Exception:
            pass
        self._conn = None
        await super().close()


class JsonDumper:
    @staticmethod
    def dumps(obj: Dict[str, Any]) -> str:
        # Avoid importing json at module top as a micro-optimization
        import json as _json
        try:
            return _json.dumps(obj)
        except Exception:
            return '{}'

