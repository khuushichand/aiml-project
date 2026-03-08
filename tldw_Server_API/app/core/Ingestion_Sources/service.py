from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from tldw_Server_API.app.core.Ingestion_Sources.models import (
    SINK_TYPES,
    SOURCE_POLICIES,
    SOURCE_TYPES,
)
from tldw_Server_API.app.core.exceptions import IngestionSourceValidationError


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _normalize_choice(value: Any, *, field_name: str, allowed: frozenset[str], default: str | None = None) -> str:
    raw = str(value if value is not None else default or "").strip().lower()
    if raw not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise IngestionSourceValidationError(
            f"Unsupported {field_name} '{raw}'. Allowed values: {allowed_values}"
        )
    return raw


def normalize_source_payload(data: dict[str, Any]) -> dict[str, Any]:
    source_type = _normalize_choice(
        data.get("source_type"),
        field_name="source_type",
        allowed=SOURCE_TYPES,
    )
    sink_type = _normalize_choice(
        data.get("sink_type"),
        field_name="sink_type",
        allowed=SINK_TYPES,
    )
    policy = _normalize_choice(
        data.get("policy"),
        field_name="policy",
        allowed=SOURCE_POLICIES,
        default="canonical",
    )
    enabled_raw = data.get("enabled")
    enabled = True if enabled_raw is None else bool(enabled_raw)
    schedule_config = data.get("schedule") or data.get("schedule_config") or {}
    schedule_enabled_raw = data.get("schedule_enabled")
    schedule_enabled = bool(schedule_config) if schedule_enabled_raw is None else bool(schedule_enabled_raw)
    return {
        "source_type": source_type,
        "sink_type": sink_type,
        "policy": policy,
        "enabled": enabled,
        "schedule_enabled": schedule_enabled,
        "schedule_config": schedule_config if isinstance(schedule_config, dict) else {},
    }


async def ensure_ingestion_sources_schema(db) -> None:
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS ingestion_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_type TEXT NOT NULL,
            sink_type TEXT NOT NULL,
            policy TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            schedule_enabled INTEGER NOT NULL DEFAULT 0,
            schedule_config_json TEXT NOT NULL DEFAULT '{}',
            config_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ingestion_source_state (
            source_id INTEGER PRIMARY KEY,
            active_job_id TEXT,
            last_successful_snapshot_id INTEGER,
            last_sync_started_at TEXT,
            last_sync_completed_at TEXT,
            last_sync_status TEXT,
            last_error TEXT,
            FOREIGN KEY(source_id) REFERENCES ingestion_sources(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ingestion_source_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            snapshot_kind TEXT NOT NULL,
            status TEXT NOT NULL,
            summary_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(source_id) REFERENCES ingestion_sources(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ingestion_source_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            normalized_relative_path TEXT NOT NULL,
            content_hash TEXT,
            sync_status TEXT NOT NULL DEFAULT 'pending',
            binding_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(source_id, normalized_relative_path),
            FOREIGN KEY(source_id) REFERENCES ingestion_sources(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ingestion_item_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            item_path TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(source_id) REFERENCES ingestion_sources(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ingestion_source_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            snapshot_id INTEGER,
            artifact_kind TEXT NOT NULL,
            status TEXT NOT NULL,
            storage_path TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(source_id) REFERENCES ingestion_sources(id) ON DELETE CASCADE,
            FOREIGN KEY(snapshot_id) REFERENCES ingestion_source_snapshots(id) ON DELETE SET NULL
        );
        """
    )
    await db.commit()


def _row_to_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    keys = getattr(row, "keys", None)
    if callable(keys):
        return {key: row[key] for key in row.keys()}
    return dict(row)


async def create_source(db, *, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_source_payload(payload)
    now = _utc_now_text()
    config_json = json.dumps(payload.get("config") or {}, sort_keys=True)
    schedule_config_json = json.dumps(normalized.get("schedule_config") or {}, sort_keys=True)

    cursor = await db.execute(
        """
        INSERT INTO ingestion_sources (
            user_id,
            source_type,
            sink_type,
            policy,
            enabled,
            schedule_enabled,
            schedule_config_json,
            config_json,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(user_id),
            normalized["source_type"],
            normalized["sink_type"],
            normalized["policy"],
            1 if normalized["enabled"] else 0,
            1 if normalized["schedule_enabled"] else 0,
            schedule_config_json,
            config_json,
            now,
            now,
        ),
    )
    source_id = int(cursor.lastrowid)
    await db.execute(
        """
        INSERT INTO ingestion_source_state (
            source_id,
            active_job_id,
            last_successful_snapshot_id,
            last_sync_started_at,
            last_sync_completed_at,
            last_sync_status,
            last_error
        ) VALUES (?, NULL, NULL, NULL, NULL, NULL, NULL)
        """,
        (source_id,),
    )
    await db.commit()

    row_cur = await db.execute(
        """
        SELECT
            id,
            user_id,
            source_type,
            sink_type,
            policy,
            enabled,
            schedule_enabled,
            schedule_config_json,
            config_json,
            created_at,
            updated_at
        FROM ingestion_sources
        WHERE id = ?
        """,
        (source_id,),
    )
    row = await row_cur.fetchone()
    result = _row_to_dict(row)
    if "config_json" in result:
        result["config"] = json.loads(result.pop("config_json") or "{}")
    if "schedule_config_json" in result:
        result["schedule_config"] = json.loads(result.pop("schedule_config_json") or "{}")
    if "enabled" in result:
        result["enabled"] = bool(result["enabled"])
    if "schedule_enabled" in result:
        result["schedule_enabled"] = bool(result["schedule_enabled"])
    return result


def _deserialize_source_row(row: Any) -> dict[str, Any]:
    result = _row_to_dict(row)
    if not result:
        return result
    if "config_json" in result:
        result["config"] = json.loads(result.pop("config_json") or "{}")
    if "schedule_config_json" in result:
        result["schedule_config"] = json.loads(result.pop("schedule_config_json") or "{}")
    if "enabled" in result:
        result["enabled"] = bool(result["enabled"])
    if "schedule_enabled" in result:
        result["schedule_enabled"] = bool(result["schedule_enabled"])
    return result


async def get_source_by_id(db, *, source_id: int, user_id: int | None = None) -> dict[str, Any]:
    query = """
        SELECT
            s.id,
            s.user_id,
            s.source_type,
            s.sink_type,
            s.policy,
            s.enabled,
            s.schedule_enabled,
            s.schedule_config_json,
            s.config_json,
            s.created_at,
            s.updated_at,
            st.active_job_id,
            st.last_successful_snapshot_id,
            st.last_sync_started_at,
            st.last_sync_completed_at,
            st.last_sync_status,
            st.last_error
        FROM ingestion_sources s
        JOIN ingestion_source_state st ON st.source_id = s.id
        WHERE s.id = ?
    """
    params: list[Any] = [int(source_id)]
    if user_id is not None:
        query += " AND s.user_id = ?"
        params.append(int(user_id))
    cursor = await db.execute(query, tuple(params))
    row = await cursor.fetchone()
    return _deserialize_source_row(row)


async def list_sources_for_scheduler(db) -> list[dict[str, Any]]:
    cursor = await db.execute(
        """
        SELECT
            s.id,
            s.user_id,
            s.source_type,
            s.sink_type,
            s.policy,
            s.enabled,
            s.schedule_enabled,
            s.schedule_config_json,
            s.config_json,
            st.active_job_id,
            st.last_successful_snapshot_id,
            st.last_sync_started_at,
            st.last_sync_completed_at,
            st.last_sync_status,
            st.last_error
        FROM ingestion_sources s
        JOIN ingestion_source_state st ON st.source_id = s.id
        WHERE s.enabled = 1
          AND s.schedule_enabled = 1
        ORDER BY s.id ASC
        """
    )
    rows = await cursor.fetchall()
    return [_deserialize_source_row(row) for row in rows]


async def list_sources_by_user(db, *, user_id: int) -> list[dict[str, Any]]:
    cursor = await db.execute(
        """
        SELECT
            s.id,
            s.user_id,
            s.source_type,
            s.sink_type,
            s.policy,
            s.enabled,
            s.schedule_enabled,
            s.schedule_config_json,
            s.config_json,
            s.created_at,
            s.updated_at,
            st.active_job_id,
            st.last_successful_snapshot_id,
            st.last_sync_started_at,
            st.last_sync_completed_at,
            st.last_sync_status,
            st.last_error
        FROM ingestion_sources s
        JOIN ingestion_source_state st ON st.source_id = s.id
        WHERE s.user_id = ?
        ORDER BY s.id ASC
        """,
        (int(user_id),),
    )
    rows = await cursor.fetchall()
    return [_deserialize_source_row(row) for row in rows]


async def start_source_sync_job(db, *, source_id: int, job_id: str) -> dict[str, Any]:
    now = _utc_now_text()
    await db.execute(
        """
        UPDATE ingestion_source_state
        SET active_job_id = ?,
            last_sync_started_at = ?,
            last_sync_status = ?,
            last_error = NULL
        WHERE source_id = ?
          AND (
              active_job_id IS NULL
              OR active_job_id = ''
              OR active_job_id = ?
          )
        """,
        (str(job_id), now, "running", int(source_id), str(job_id)),
    )
    cursor = await db.execute(
        """
        SELECT
            source_id,
            active_job_id,
            last_successful_snapshot_id,
            last_sync_started_at,
            last_sync_completed_at,
            last_sync_status,
            last_error
        FROM ingestion_source_state
        WHERE source_id = ?
        """,
        (int(source_id),),
    )
    return _row_to_dict(await cursor.fetchone())


async def finish_source_sync_job(
    db,
    *,
    source_id: int,
    job_id: str,
    outcome: str,
    error: str | None = None,
    snapshot_id: int | None = None,
) -> dict[str, Any]:
    now = _utc_now_text()
    await db.execute(
        """
        UPDATE ingestion_source_state
        SET active_job_id = NULL,
            last_successful_snapshot_id = CASE
                WHEN ? = 'success' AND ? IS NOT NULL THEN ?
                ELSE last_successful_snapshot_id
            END,
            last_sync_completed_at = ?,
            last_sync_status = ?,
            last_error = ?
        WHERE source_id = ?
          AND active_job_id = ?
        """,
        (
            str(outcome),
            snapshot_id,
            snapshot_id,
            now,
            str(outcome),
            None if error is None else str(error),
            int(source_id),
            str(job_id),
        ),
    )
    cursor = await db.execute(
        """
        SELECT
            source_id,
            active_job_id,
            last_successful_snapshot_id,
            last_sync_started_at,
            last_sync_completed_at,
            last_sync_status,
            last_error
        FROM ingestion_source_state
        WHERE source_id = ?
        """,
        (int(source_id),),
    )
    return _row_to_dict(await cursor.fetchone())
