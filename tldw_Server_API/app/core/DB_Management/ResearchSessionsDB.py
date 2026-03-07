"""Persistence for deep research sessions, checkpoints, and artifacts."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_json_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


@dataclass(frozen=True)
class ResearchSessionRow:
    id: str
    owner_user_id: str
    status: str
    phase: str
    query: str
    source_policy: str
    autonomy_mode: str
    limits_json: dict[str, Any]
    provider_overrides_json: dict[str, Any]
    active_job_id: str | None
    latest_checkpoint_id: str | None
    created_at: str
    updated_at: str
    completed_at: str | None


@dataclass(frozen=True)
class ResearchCheckpointRow:
    id: str
    session_id: str
    checkpoint_type: str
    status: str
    resolution: str | None
    proposed_payload: dict[str, Any]
    user_patch_payload: dict[str, Any]
    created_at: str
    resolved_at: str | None


@dataclass(frozen=True)
class ResearchArtifactRow:
    id: str
    session_id: str
    artifact_name: str
    artifact_version: int
    storage_path: str
    content_type: str
    byte_size: int
    checksum: str
    phase: str
    job_id: str | None
    created_at: str


class ResearchSessionsDB:
    """SQLite-backed storage for research sessions and related metadata."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS research_sessions (
                    id TEXT PRIMARY KEY,
                    owner_user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    query TEXT NOT NULL,
                    source_policy TEXT NOT NULL,
                    autonomy_mode TEXT NOT NULL,
                    limits_json TEXT NOT NULL DEFAULT '{}',
                    provider_overrides_json TEXT NOT NULL DEFAULT '{}',
                    active_job_id TEXT,
                    latest_checkpoint_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS research_checkpoints (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    checkpoint_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    resolution TEXT,
                    proposed_payload TEXT NOT NULL DEFAULT '{}',
                    user_patch_payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES research_sessions(id)
                );

                CREATE TABLE IF NOT EXISTS research_artifacts (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    artifact_name TEXT NOT NULL,
                    artifact_version INTEGER NOT NULL,
                    storage_path TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    checksum TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    job_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES research_sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_research_sessions_owner
                    ON research_sessions(owner_user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_research_checkpoints_session
                    ON research_checkpoints(session_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_research_artifacts_session
                    ON research_artifacts(session_id, artifact_name, artifact_version DESC);
                """
            )
            columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info('research_sessions')").fetchall()}
            if "provider_overrides_json" not in columns:
                conn.execute(
                    "ALTER TABLE research_sessions ADD COLUMN provider_overrides_json TEXT NOT NULL DEFAULT '{}'"
                )

    @staticmethod
    def _session_from_row(row: sqlite3.Row | None) -> ResearchSessionRow | None:
        if row is None:
            return None
        keys = set(row.keys())
        return ResearchSessionRow(
            id=str(row["id"]),
            owner_user_id=str(row["owner_user_id"]),
            status=str(row["status"]),
            phase=str(row["phase"]),
            query=str(row["query"]),
            source_policy=str(row["source_policy"]),
            autonomy_mode=str(row["autonomy_mode"]),
            limits_json=_parse_json_dict(row["limits_json"]),
            provider_overrides_json=(
                _parse_json_dict(row["provider_overrides_json"])
                if "provider_overrides_json" in keys
                else {}
            ),
            active_job_id=str(row["active_job_id"]) if row["active_job_id"] else None,
            latest_checkpoint_id=str(row["latest_checkpoint_id"]) if row["latest_checkpoint_id"] else None,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            completed_at=str(row["completed_at"]) if row["completed_at"] else None,
        )

    @staticmethod
    def _checkpoint_from_row(row: sqlite3.Row | None) -> ResearchCheckpointRow | None:
        if row is None:
            return None
        return ResearchCheckpointRow(
            id=str(row["id"]),
            session_id=str(row["session_id"]),
            checkpoint_type=str(row["checkpoint_type"]),
            status=str(row["status"]),
            resolution=str(row["resolution"]) if row["resolution"] else None,
            proposed_payload=_parse_json_dict(row["proposed_payload"]),
            user_patch_payload=_parse_json_dict(row["user_patch_payload"]),
            created_at=str(row["created_at"]),
            resolved_at=str(row["resolved_at"]) if row["resolved_at"] else None,
        )

    @staticmethod
    def _artifact_from_row(row: sqlite3.Row | None) -> ResearchArtifactRow | None:
        if row is None:
            return None
        return ResearchArtifactRow(
            id=str(row["id"]),
            session_id=str(row["session_id"]),
            artifact_name=str(row["artifact_name"]),
            artifact_version=int(row["artifact_version"]),
            storage_path=str(row["storage_path"]),
            content_type=str(row["content_type"]),
            byte_size=int(row["byte_size"]),
            checksum=str(row["checksum"]),
            phase=str(row["phase"]),
            job_id=str(row["job_id"]) if row["job_id"] else None,
            created_at=str(row["created_at"]),
        )

    def create_session(
        self,
        *,
        owner_user_id: str,
        query: str,
        source_policy: str,
        autonomy_mode: str,
        limits_json: dict[str, Any],
        provider_overrides_json: dict[str, Any] | None = None,
        status: str = "queued",
        phase: str = "drafting_plan",
    ) -> ResearchSessionRow:
        session_id = f"rs_{uuid.uuid4().hex[:12]}"
        now = _utc_now()
        payload = json.dumps(limits_json or {}, sort_keys=True)
        provider_payload = json.dumps(provider_overrides_json or {}, sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO research_sessions (
                    id, owner_user_id, status, phase, query, source_policy,
                    autonomy_mode, limits_json, provider_overrides_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    str(owner_user_id),
                    status,
                    phase,
                    query,
                    source_policy,
                    autonomy_mode,
                    payload,
                    provider_payload,
                    now,
                    now,
                ),
            )
        session = self.get_session(session_id)
        if session is None:
            raise RuntimeError("failed_to_create_research_session")
        return session

    def get_session(self, session_id: str) -> ResearchSessionRow | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM research_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return self._session_from_row(row)

    def update_phase(
        self,
        session_id: str,
        *,
        phase: str,
        status: str,
        completed_at: str | None = None,
    ) -> ResearchSessionRow:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE research_sessions
                SET phase = ?, status = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (phase, status, completed_at, now, session_id),
            )
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def attach_active_job(self, session_id: str, job_id: str | None) -> ResearchSessionRow:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE research_sessions
                SET active_job_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (job_id, now, session_id),
            )
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def create_checkpoint(
        self,
        *,
        session_id: str,
        checkpoint_type: str,
        proposed_payload: dict[str, Any],
        status: str = "pending",
    ) -> ResearchCheckpointRow:
        checkpoint_id = f"cp_{uuid.uuid4().hex[:12]}"
        now = _utc_now()
        proposed_json = json.dumps(proposed_payload or {}, sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO research_checkpoints (
                    id, session_id, checkpoint_type, status, proposed_payload,
                    user_patch_payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint_id,
                    session_id,
                    checkpoint_type,
                    status,
                    proposed_json,
                    "{}",
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE research_sessions
                SET latest_checkpoint_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (checkpoint_id, now, session_id),
            )
        checkpoint = self.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise RuntimeError("failed_to_create_research_checkpoint")
        return checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> ResearchCheckpointRow | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM research_checkpoints WHERE id = ?",
                (checkpoint_id,),
            ).fetchone()
        return self._checkpoint_from_row(row)

    def resolve_checkpoint(
        self,
        checkpoint_id: str,
        *,
        resolution: str,
        user_patch_payload: dict[str, Any] | None = None,
    ) -> ResearchCheckpointRow:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE research_checkpoints
                SET status = ?, resolution = ?, user_patch_payload = ?, resolved_at = ?
                WHERE id = ?
                """,
                (
                    "resolved",
                    resolution,
                    json.dumps(user_patch_payload or {}, sort_keys=True),
                    now,
                    checkpoint_id,
                ),
            )
        checkpoint = self.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise KeyError(checkpoint_id)
        return checkpoint

    def record_artifact(
        self,
        *,
        session_id: str,
        artifact_name: str,
        artifact_version: int,
        storage_path: str,
        content_type: str,
        byte_size: int,
        checksum: str,
        phase: str,
        job_id: str | None = None,
    ) -> ResearchArtifactRow:
        artifact_id = f"ra_{uuid.uuid4().hex[:12]}"
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO research_artifacts (
                    id, session_id, artifact_name, artifact_version, storage_path,
                    content_type, byte_size, checksum, phase, job_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    session_id,
                    artifact_name,
                    int(artifact_version),
                    storage_path,
                    content_type,
                    int(byte_size),
                    checksum,
                    phase,
                    job_id,
                    now,
                ),
            )
        artifact = self.get_artifact(artifact_id)
        if artifact is None:
            raise RuntimeError("failed_to_record_research_artifact")
        return artifact

    def get_artifact(self, artifact_id: str) -> ResearchArtifactRow | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM research_artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()
        return self._artifact_from_row(row)

    def list_artifacts(self, session_id: str) -> list[ResearchArtifactRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM research_artifacts
                WHERE session_id = ?
                ORDER BY artifact_name ASC, artifact_version DESC, created_at DESC
                """,
                (session_id,),
            ).fetchall()
        return [artifact for row in rows if (artifact := self._artifact_from_row(row)) is not None]


__all__ = [
    "ResearchArtifactRow",
    "ResearchCheckpointRow",
    "ResearchSessionRow",
    "ResearchSessionsDB",
]
