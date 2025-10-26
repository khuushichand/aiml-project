import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional, List
from tldw_Server_API.app.core.config import settings


def _db_path(user_id: str) -> Path:
    base_dir: Path = settings.get("USER_DB_BASE_DIR")
    user_dir = base_dir / str(user_id) / 'vector_store'
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / 'media_embedding_jobs.db'


def _prime(conn: sqlite3.Connection) -> sqlite3.Connection:
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
    return _prime(sqlite3.connect(_db_path(user_id), check_same_thread=False))


def init_db(user_id: str) -> None:
    with _connect(user_id) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS media_embedding_jobs (
                id TEXT PRIMARY KEY,
                media_id INTEGER NOT NULL,
                user_id TEXT,
                status TEXT NOT NULL,
                embedding_model TEXT,
                embedding_count INTEGER DEFAULT 0,
                chunks_processed INTEGER DEFAULT 0,
                error TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()


def create_job(job_id: str, media_id: int, user_id: Optional[str], embedding_model: str, status: str = 'processing') -> None:
    ts = int(time.time())
    uid = str(user_id) if user_id is not None else '1'
    with _connect(uid) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO media_embedding_jobs
            (id, media_id, user_id, status, embedding_model, embedding_count, chunks_processed, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, COALESCE((SELECT embedding_count FROM media_embedding_jobs WHERE id = ?), 0),
                    COALESCE((SELECT chunks_processed FROM media_embedding_jobs WHERE id = ?), 0),
                    COALESCE((SELECT error FROM media_embedding_jobs WHERE id = ?), NULL),
                    COALESCE((SELECT created_at FROM media_embedding_jobs WHERE id = ?), ?), ?)
            """,
            (
                job_id, media_id, user_id, status, embedding_model,
                job_id, job_id, job_id, job_id, ts, ts
            )
        )
        conn.commit()


def update_job(job_id: str, user_id: str, status: Optional[str] = None, embedding_count: Optional[int] = None,
               chunks_processed: Optional[int] = None, error: Optional[str] = None) -> None:
    fields = []
    values: List[Any] = []
    if status is not None:
        fields.append('status = ?')
        values.append(status)
    if embedding_count is not None:
        fields.append('embedding_count = ?')
        values.append(int(embedding_count))
    if chunks_processed is not None:
        fields.append('chunks_processed = ?')
        values.append(int(chunks_processed))
    if error is not None:
        fields.append('error = ?')
        values.append(error)
    fields.append('updated_at = ?')
    values.append(int(time.time()))
    values.append(job_id)
    if not fields:
        return
    with _connect(str(user_id)) as conn:
        conn.execute(f"UPDATE media_embedding_jobs SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()


def get_job(job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    with _connect(str(user_id)) as conn:
        cur = conn.execute(
            """
            SELECT id, media_id, user_id, status, embedding_model, embedding_count, chunks_processed, error, created_at, updated_at
            FROM media_embedding_jobs WHERE id = ?
            """,
            (job_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            'id': row[0],
            'media_id': row[1],
            'user_id': row[2],
            'status': row[3],
            'embedding_model': row[4],
            'embedding_count': row[5],
            'chunks_processed': row[6],
            'error': row[7],
            'created_at': row[8],
            'updated_at': row[9],
        }


def list_jobs(user_id: str, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    query = (
        "SELECT id, media_id, user_id, status, embedding_model, embedding_count, chunks_processed, error, created_at, updated_at "
        "FROM media_embedding_jobs"
    )
    params: List[Any] = []
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
                'id': r[0], 'media_id': r[1], 'user_id': r[2], 'status': r[3], 'embedding_model': r[4],
                'embedding_count': r[5], 'chunks_processed': r[6], 'error': r[7], 'created_at': r[8], 'updated_at': r[9]
            }
            for r in rows
        ]
