import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional
from tldw_Server_API.app.core.config import settings


def _project_root_from(file_path: Path) -> Path:
    # file_path: .../tldw_Server_API/app/core/Embeddings/vector_store_batches_db.py
    return file_path.parent.parent.parent.parent


def get_db_path(user_id: str) -> Path:
    base_dir: Path = settings.get("USER_DB_BASE_DIR")
    user_dir = base_dir / str(user_id) / 'vector_store'
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / 'vector_store_batches.db'


def _prime(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Apply recommended SQLite PRAGMAs for concurrency and resilience."""
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        pass
    try:
        conn.execute("PRAGMA busy_timeout=3000;")
    except Exception:
        pass
    return conn


def _connect(user_id: str) -> sqlite3.Connection:
    return _prime(sqlite3.connect(get_db_path(user_id), check_same_thread=False))


def _ensure_initialized(user_id: str) -> None:
    """Ensure the batches table exists for the given user.

    This guards against cases where the base directory changes during tests
    after module import time, so the original init_db path no longer applies.
    """
    try:
        init_db(user_id)
    except Exception:
        # Best effort; callers will raise if operations still fail
        pass


def init_db(user_id: str) -> None:
    with _connect(user_id) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vector_store_batches (
                id TEXT PRIMARY KEY,
                store_id TEXT NOT NULL,
                user_id TEXT,
                status TEXT NOT NULL,
                upserted INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                meta_json TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()


def create_batch(batch_id: str, store_id: str, user_id: Optional[str], status: str = 'processing',
                 upserted: int = 0, error: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> None:
    ts = int(time.time())
    uid = str(user_id) if user_id is not None else '1'
    _ensure_initialized(uid)
    with _connect(uid) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO vector_store_batches
            (id, store_id, user_id, status, upserted, error, meta_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM vector_store_batches WHERE id = ?), ?), ?)
            """,
            (
                batch_id, store_id, user_id, status, upserted, error or None,
                json.dumps(meta or {}), batch_id, ts, ts
            )
        )
        conn.commit()


def update_batch(batch_id: str, user_id: str, status: Optional[str] = None, upserted: Optional[int] = None,
                 error: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> None:
    _ensure_initialized(str(user_id))
    fields = []
    values = []
    if status is not None:
        fields.append('status = ?')
        values.append(status)
    if upserted is not None:
        fields.append('upserted = ?')
        values.append(upserted)
    if error is not None:
        fields.append('error = ?')
        values.append(error)
    if meta is not None:
        fields.append('meta_json = ?')
        values.append(json.dumps(meta))
    # Always update updated_at
    fields.append('updated_at = ?')
    values.append(int(time.time()))
    values.append(batch_id)

    if not fields:
        return

    with _connect(str(user_id)) as conn:
        conn.execute(f"UPDATE vector_store_batches SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()


def get_batch(batch_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    _ensure_initialized(str(user_id))
    with _connect(str(user_id)) as conn:
        cur = conn.execute(
            "SELECT id, store_id, user_id, status, upserted, error, meta_json, created_at, updated_at\n             FROM vector_store_batches WHERE id = ?",
            (batch_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            'id': row[0],
            'store_id': row[1],
            'user_id': row[2],
            'status': row[3],
            'upserted': row[4],
            'error': row[5],
            'meta': json.loads(row[6] or '{}'),
            'created_at': row[7],
            'updated_at': row[8],
        }


def list_batches(user_id: str, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    _ensure_initialized(str(user_id))
    query = "SELECT id, store_id, user_id, status, upserted, error, meta_json, created_at, updated_at FROM vector_store_batches"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with _connect(str(user_id)) as conn:
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        return [
            {
                'id': r[0],
                'store_id': r[1],
                'user_id': r[2],
                'status': r[3],
                'upserted': r[4],
                'error': r[5],
                'meta': json.loads(r[6] or '{}'),
                'created_at': r[7],
                'updated_at': r[8],
            }
            for r in rows
        ]
