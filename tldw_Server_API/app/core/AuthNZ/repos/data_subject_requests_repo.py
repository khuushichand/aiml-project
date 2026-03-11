from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool


@dataclass
class AuthnzDataSubjectRequestsRepo:
    """Repository for AuthNZ data subject request records."""

    db_pool: DatabasePool

    def _is_postgres_backend(self) -> bool:
        """Return True when the current AuthNZ backend is PostgreSQL."""
        return bool(getattr(self.db_pool, "pool", None))

    async def ensure_schema(self) -> None:
        """Ensure the DSR table exists for the current backend."""
        try:
            if self._is_postgres_backend():
                from tldw_Server_API.app.core.AuthNZ.pg_migrations_extra import (
                    ensure_data_subject_requests_table_pg,
                )

                await ensure_data_subject_requests_table_pg(self.db_pool)
                return

            from pathlib import Path

            from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables

            db_fs_path = getattr(self.db_pool, "_sqlite_fs_path", None) or getattr(
                self.db_pool, "db_path", None
            )
            if db_fs_path:
                ensure_authnz_tables(Path(str(db_fs_path)))
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.debug(f"AuthnzDataSubjectRequestsRepo.ensure_schema skipped/failed: {exc}")

    @staticmethod
    def _parse_json_field(value: Any, *, fallback: Any) -> Any:
        if value is None:
            return fallback
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return fallback
        return fallback

    @classmethod
    def _normalize_record(cls, row: Any) -> dict[str, Any]:
        """Normalize backend row types into JSON-friendly dicts."""
        if row is None:
            return {}

        try:
            record = dict(row) if hasattr(row, "keys") or isinstance(row, dict) else {}
        except Exception:
            record = {}

        for field in ("id", "resolved_user_id", "requested_by_user_id"):
            if field in record and record[field] is not None:
                with contextlib.suppress(Exception):
                    record[field] = int(record[field])

        record["selected_categories"] = cls._parse_json_field(
            record.get("selected_categories"),
            fallback=[],
        )
        record["preview_summary"] = cls._parse_json_field(
            record.get("preview_summary"),
            fallback=[],
        )
        record["coverage_metadata"] = cls._parse_json_field(
            record.get("coverage_metadata"),
            fallback={},
        )

        if "requested_at" in record and record["requested_at"] is not None:
            with contextlib.suppress(Exception):
                if hasattr(record["requested_at"], "isoformat"):
                    record["requested_at"] = record["requested_at"].isoformat()

        return record

    async def create_or_get_request(
        self,
        *,
        client_request_id: str,
        requester_identifier: str,
        resolved_user_id: int | None,
        request_type: str,
        status: str,
        selected_categories: list[str],
        preview_summary: list[dict[str, Any]],
        coverage_metadata: dict[str, Any] | None,
        requested_by_user_id: int | None,
        notes: str | None,
    ) -> dict[str, Any]:
        """Persist a request unless the client idempotency key already exists."""
        now = datetime.now(timezone.utc)
        selected_categories_json = json.dumps(selected_categories or [])
        preview_summary_json = json.dumps(preview_summary or [])
        coverage_metadata_json = json.dumps(coverage_metadata or {})

        try:
            async with self.db_pool.transaction() as conn:
                if self._is_postgres_backend():
                    row = await conn.fetchrow(
                        """
                        INSERT INTO data_subject_requests (
                            client_request_id,
                            requester_identifier,
                            resolved_user_id,
                            request_type,
                            status,
                            selected_categories,
                            preview_summary,
                            coverage_metadata,
                            requested_by_user_id,
                            requested_at,
                            notes
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8::jsonb, $9, $10, $11
                        )
                        ON CONFLICT (client_request_id) DO NOTHING
                        RETURNING *
                        """,
                        client_request_id,
                        requester_identifier,
                        resolved_user_id,
                        request_type,
                        status,
                        selected_categories_json,
                        preview_summary_json,
                        coverage_metadata_json,
                        requested_by_user_id,
                        now,
                        notes,
                    )
                    if row is None:
                        row = await conn.fetchrow(
                            "SELECT * FROM data_subject_requests WHERE client_request_id = $1",
                            client_request_id,
                        )
                    return self._normalize_record(row)

                await conn.execute(
                    """
                    INSERT OR IGNORE INTO data_subject_requests (
                        client_request_id,
                        requester_identifier,
                        resolved_user_id,
                        request_type,
                        status,
                        selected_categories,
                        preview_summary,
                        coverage_metadata,
                        requested_by_user_id,
                        requested_at,
                        notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        client_request_id,
                        requester_identifier,
                        resolved_user_id,
                        request_type,
                        status,
                        selected_categories_json,
                        preview_summary_json,
                        coverage_metadata_json,
                        requested_by_user_id,
                        now.isoformat(),
                        notes,
                    ),
                )
                cursor = await conn.execute(
                    "SELECT * FROM data_subject_requests WHERE client_request_id = ?",
                    (client_request_id,),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise RuntimeError("Failed to fetch persisted data subject request")
                return self._normalize_record(row)
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzDataSubjectRequestsRepo.create_or_get_request failed: {exc}")
            raise

    async def list_requests(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return paged request rows ordered newest-first."""
        try:
            async with self.db_pool.acquire() as conn:
                if self._is_postgres_backend():
                    rows = await conn.fetch(
                        """
                        SELECT *
                        FROM data_subject_requests
                        ORDER BY requested_at DESC, id DESC
                        LIMIT $1 OFFSET $2
                        """,
                        limit,
                        offset,
                    )
                    total = await conn.fetchval("SELECT COUNT(*) FROM data_subject_requests")
                    return [self._normalize_record(row) for row in rows], int(total or 0)

                cursor = await conn.execute(
                    """
                    SELECT *
                    FROM data_subject_requests
                    ORDER BY requested_at DESC, id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )
                rows = await cursor.fetchall()
                total_cursor = await conn.execute("SELECT COUNT(*) FROM data_subject_requests")
                total_row = await total_cursor.fetchone()
                total = int(total_row[0]) if total_row else 0
                return [self._normalize_record(row) for row in rows], total
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzDataSubjectRequestsRepo.list_requests failed: {exc}")
            raise
