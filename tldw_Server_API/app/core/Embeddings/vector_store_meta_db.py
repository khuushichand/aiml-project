import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
from tldw_Server_API.app.core.config import settings
import time


def _db_path(user_id: str) -> Path:
    base_dir: Path = settings.get("USER_DB_BASE_DIR")
    user_dir = base_dir / str(user_id) / 'vector_store'
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / 'vector_store_meta.db'


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


def init_meta_db(user_id: str) -> None:
    with _connect(user_id) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vector_stores (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                name_lower TEXT NOT NULL UNIQUE,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()


def register_store(user_id: str, store_id: str, name: str) -> None:
    ts = int(time.time())
    with _connect(user_id) as conn:
        conn.execute(
            "INSERT INTO vector_stores (id, name, name_lower, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (store_id, name, name.strip().lower(), ts, ts)
        )
        conn.commit()


def rename_store(user_id: str, store_id: str, new_name: str) -> None:
    ts = int(time.time())
    with _connect(user_id) as conn:
        conn.execute(
            "UPDATE vector_stores SET name = ?, name_lower = ?, updated_at = ? WHERE id = ?",
            (new_name, new_name.strip().lower(), ts, store_id)
        )
        conn.commit()


def delete_store(user_id: str, store_id: str) -> None:
    with _connect(user_id) as conn:
        conn.execute("DELETE FROM vector_stores WHERE id = ?", (store_id,))
        conn.commit()


def find_store_by_name(user_id: str, name: str) -> Optional[Dict[str, Any]]:
    with _connect(user_id) as conn:
        cur = conn.execute(
            "SELECT id, name, name_lower, created_at, updated_at FROM vector_stores WHERE name_lower = ?",
            (name.strip().lower(),)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            'id': row[0],
            'name': row[1],
            'name_lower': row[2],
            'created_at': row[3],
            'updated_at': row[4]
        }


def list_stores(user_id: str) -> List[Dict[str, Any]]:
    with _connect(user_id) as conn:
        cur = conn.execute(
            "SELECT id, name, name_lower, created_at, updated_at FROM vector_stores ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
        return [
            {
                'id': r[0], 'name': r[1], 'name_lower': r[2], 'created_at': r[3], 'updated_at': r[4]
            } for r in rows
        ]
