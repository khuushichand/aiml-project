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
    return {
        "source_type": source_type,
        "sink_type": sink_type,
        "policy": policy,
        "enabled": enabled,
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

    cursor = await db.execute(
        """
        INSERT INTO ingestion_sources (
            user_id,
            source_type,
            sink_type,
            policy,
            enabled,
            config_json,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(user_id),
            normalized["source_type"],
            normalized["sink_type"],
            normalized["policy"],
            1 if normalized["enabled"] else 0,
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
        SELECT id, user_id, source_type, sink_type, policy, enabled, config_json, created_at, updated_at
        FROM ingestion_sources
        WHERE id = ?
        """,
        (source_id,),
    )
    row = await row_cur.fetchone()
    result = _row_to_dict(row)
    if "config_json" in result:
        result["config"] = json.loads(result.pop("config_json") or "{}")
    if "enabled" in result:
        result["enabled"] = bool(result["enabled"])
    return result
