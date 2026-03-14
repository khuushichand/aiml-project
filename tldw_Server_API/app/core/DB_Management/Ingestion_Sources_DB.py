from __future__ import annotations

import json
from typing import Any


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, sort_keys=True)


async def update_ingestion_source_record(
    db,
    *,
    source_id: int,
    source_type: str,
    sink_type: str,
    policy: str,
    enabled: bool,
    schedule_enabled: bool,
    schedule_config: dict[str, Any],
    config: dict[str, Any],
    updated_at: str,
) -> None:
    """Persist the mutable ingestion source definition fields for a source row."""

    await db.execute(
        """
        UPDATE ingestion_sources
        SET source_type = ?,
            sink_type = ?,
            policy = ?,
            enabled = ?,
            schedule_enabled = ?,
            schedule_config_json = ?,
            config_json = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            str(source_type),
            str(sink_type),
            str(policy),
            1 if enabled else 0,
            1 if schedule_enabled else 0,
            _json_dumps(schedule_config),
            _json_dumps(config),
            str(updated_at),
            int(source_id),
        ),
    )
