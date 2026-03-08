from __future__ import annotations

import asyncio
import contextlib
import os
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Ingestion_Sources.archive_snapshot import (
    build_archive_snapshot_from_bytes,
    load_archive_artifact_bytes,
)
from tldw_Server_API.app.core.Ingestion_Sources.diffing import diff_snapshots
from tldw_Server_API.app.core.Ingestion_Sources.jobs import DOMAIN, ingestion_sources_queue
from tldw_Server_API.app.core.Ingestion_Sources.local_directory import build_local_directory_snapshot
from tldw_Server_API.app.core.Ingestion_Sources.service import (
    create_source_snapshot,
    ensure_ingestion_sources_schema,
    finish_source_sync_job,
    get_source_artifact_by_id,
    get_source_by_id,
    get_latest_source_snapshot,
    list_source_items,
    record_ingestion_item_event,
    start_source_sync_job,
    update_source_artifact,
    update_source_snapshot,
    upsert_source_item,
)
from tldw_Server_API.app.core.Ingestion_Sources.sinks.media_sink import apply_media_change
from tldw_Server_API.app.core.Ingestion_Sources.sinks.notes_sink import apply_notes_change
from tldw_Server_API.app.core.testing import env_flag_enabled

try:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
except ImportError:  # pragma: no cover - optional
    get_db_pool = None  # type: ignore

try:
    from tldw_Server_API.app.core.Jobs.manager import JobManager
except ImportError:  # pragma: no cover - optional
    JobManager = None  # type: ignore

_NONCRITICAL_EXCEPTIONS = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
)


def _previous_snapshot_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, str | None]]:
    previous: dict[str, dict[str, str | None]] = {}
    for row in rows:
        relative_path = str(row.get("normalized_relative_path") or "").strip()
        if not relative_path:
            continue
        previous[relative_path] = {
            "relative_path": relative_path,
            "content_hash": row.get("content_hash"),
        }
    return previous


def _iter_changes(diff_result: dict[str, list[dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
    ordered: list[tuple[str, dict[str, Any]]] = []
    for event_type in ("created", "changed", "deleted"):
        for item in diff_result.get(event_type, []):
            ordered.append((event_type, item))
    return ordered


def _build_media_binding(result: dict[str, Any], previous_binding: dict[str, Any]) -> dict[str, Any]:
    action = str(result.get("action") or "").strip().lower()
    if action in {"created", "version_created"} and result.get("media_id") is not None:
        return {"media_id": int(result["media_id"])}
    if action == "archived":
        return {}
    return dict(previous_binding)


def _build_notes_binding(notes_db, result: dict[str, Any], previous_binding: dict[str, Any]) -> dict[str, Any]:
    action = str(result.get("action") or "").strip().lower()
    if action in {"created", "updated"} and result.get("note_id"):
        note_id = str(result["note_id"])
        note = notes_db.get_note_by_id(note_id=note_id) or {}
        return {
            "note_id": note_id,
            "sync_status": str(result.get("sync_status") or "sync_managed"),
            "current_version": int(note.get("version") or previous_binding.get("current_version") or 1),
        }
    if action in {"skipped_detached", "detached_conflict"}:
        binding = dict(previous_binding)
        binding["sync_status"] = "conflict_detached"
        note_id = binding.get("note_id")
        if note_id:
            note = notes_db.get_note_by_id(note_id=str(note_id)) or {}
            if note:
                binding["current_version"] = int(note.get("version") or binding.get("current_version") or 1)
        return binding
    if action == "archived":
        return {}
    return dict(previous_binding)


def _sync_status_for_result(
    *,
    sink_type: str,
    event_type: str,
    result: dict[str, Any],
    previous_row: dict[str, Any] | None,
) -> str:
    action = str(result.get("action") or "").strip().lower()
    if sink_type == "notes":
        if action in {"created", "updated"}:
            return str(result.get("sync_status") or "sync_managed")
        if action in {"skipped_detached", "detached_conflict"}:
            return "conflict_detached"
    else:
        if action in {"created", "version_created"}:
            return "active"

    if action == "archived":
        return "archived_upstream_removed"
    if event_type == "deleted":
        return str((previous_row or {}).get("sync_status") or "missing_upstream")
    return str((previous_row or {}).get("sync_status") or "active")


def _create_sink_db(*, sink_type: str, user_id: int):
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

    if sink_type == "notes":
        from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB

        return CharactersRAGDB(
            db_path=str(DatabasePaths.get_chacha_db_path(user_id)),
            client_id=str(user_id),
        )

    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase

    return MediaDatabase(
        db_path=str(DatabasePaths.get_media_db_path(user_id)),
        client_id=str(user_id),
    )


def _apply_change_to_sink(
    *,
    sink_db,
    sink_type: str,
    binding: dict[str, Any],
    change: dict[str, Any],
    policy: str,
) -> dict[str, Any]:
    if sink_type == "notes":
        from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import ConflictError as NotesConflictError

        try:
            return apply_notes_change(
                sink_db,
                binding=binding or None,
                change=change,
                policy=policy,
            )
        except NotesConflictError:
            return {"action": "detached_conflict", "sync_status": "conflict_detached"}

    return apply_media_change(
        sink_db,
        binding=binding or None,
        change=change,
        policy=policy,
    )


async def _process_sync_job(
    jm,
    jid: int,
    lease_id: str | None,
    worker_id: str,
    source_id: int,
    user_id: int,
) -> None:
    if get_db_pool is None:
        raise RuntimeError("Database pool unavailable for ingestion sources worker.")

    pool = await get_db_pool()
    staged_snapshot: dict[str, Any] | None = None
    staged_artifact: dict[str, Any] | None = None

    async with pool.transaction() as db:
        await ensure_ingestion_sources_schema(db)
        source = await get_source_by_id(db, source_id=source_id, user_id=user_id)
        if not source:
            raise ValueError("Ingestion source not found or not owned by user.")
        state = await start_source_sync_job(db, source_id=source_id, job_id=str(jid))

    if str(state.get("active_job_id") or "") != str(jid):
        jm.fail_job(
            jid,
            error=f"Active sync job already exists for source {source_id}",
            retryable=True,
            backoff_seconds=30,
            worker_id=worker_id,
            lease_id=lease_id or None,
            completion_token=lease_id or None,
        )
        return

    try:
        if not source.get("enabled", True):
            raise ValueError(f"Ingestion source {source_id} is disabled.")
        source_type = str(source.get("source_type") or "").strip().lower()
        sink_type = str(source.get("sink_type") or "").strip().lower()
        policy = str(source.get("policy") or "canonical").strip().lower()
        if source_type == "local_directory":
            current_items = build_local_directory_snapshot(source.get("config") or {}, sink_type=sink_type)
        elif source_type == "archive_snapshot":
            async with pool.transaction() as db:
                staged_snapshot = await get_latest_source_snapshot(
                    db,
                    source_id=source_id,
                    status="staged",
                )
            if not staged_snapshot:
                raise ValueError(f"No staged archive snapshot is available for source {source_id}.")
            snapshot_summary = staged_snapshot.get("summary") or {}
            artifact_id = snapshot_summary.get("artifact_id")
            if artifact_id is not None:
                async with pool.transaction() as db:
                    staged_artifact = await get_source_artifact_by_id(
                        db,
                        artifact_id=int(artifact_id),
                    )
                if not staged_artifact:
                    raise ValueError(
                        f"Archive artifact {artifact_id} is not available for source {source_id}."
                    )
                archive_bytes = load_archive_artifact_bytes(staged_artifact)
                current_items = build_archive_snapshot_from_bytes(
                    archive_bytes=archive_bytes,
                    filename=str(
                        (staged_artifact.get("metadata") or {}).get("filename")
                        or snapshot_summary.get("filename")
                        or "archive.zip"
                    ),
                )
            else:
                current_items = {
                    str(path): dict(item)
                    for path, item in snapshot_summary.get("items", {}).items()
                }
        else:
            raise NotImplementedError(f"Sync execution not implemented for source type '{source_type}'.")
        sink_db = _create_sink_db(sink_type=sink_type, user_id=user_id)

        async with pool.transaction() as db:
            previous_rows = await list_source_items(db, source_id=source_id, include_absent=False)
            all_rows = await list_source_items(db, source_id=source_id, include_absent=True)
            previous_map = _previous_snapshot_map(previous_rows)
            all_rows_map = {
                str(row.get("normalized_relative_path") or ""): row
                for row in all_rows
                if row.get("normalized_relative_path")
            }

            diff_result = diff_snapshots(previous=previous_map, current=current_items)
            result_summary: dict[str, Any] = {
                "status": "completed",
                "source_id": source_id,
                "processed": 0,
                "created": len(diff_result.get("created", [])),
                "changed": len(diff_result.get("changed", [])),
                "deleted": len(diff_result.get("deleted", [])),
                "unchanged": len(diff_result.get("unchanged", [])),
                "detached_conflicts": 0,
                "current_item_count": len(current_items),
            }

            for event_type, raw_change in _iter_changes(diff_result):
                change = dict(raw_change)
                change["event_type"] = event_type
                relative_path = str(change.get("relative_path") or "").strip()
                existing_row = all_rows_map.get(relative_path)
                existing_binding = (
                    dict(existing_row.get("binding") or {})
                    if existing_row
                    else {}
                )
                result = _apply_change_to_sink(
                    sink_db=sink_db,
                    sink_type=sink_type,
                    binding=existing_binding,
                    change=change,
                    policy=policy,
                )
                action = str(result.get("action") or "").strip().lower()
                if sink_type == "notes":
                    binding = _build_notes_binding(sink_db, result, existing_binding)
                else:
                    binding = _build_media_binding(result, existing_binding)
                sync_status = _sync_status_for_result(
                    sink_type=sink_type,
                    event_type=event_type,
                    result=result,
                    previous_row=existing_row,
                )
                if sync_status == "conflict_detached":
                    result_summary["detached_conflicts"] += 1
                present_in_source = event_type != "deleted"
                content_hash = change.get("content_hash") if present_in_source else None

                updated_row = await upsert_source_item(
                    db,
                    source_id=source_id,
                    normalized_relative_path=relative_path,
                    content_hash=None if content_hash is None else str(content_hash),
                    sync_status=sync_status,
                    binding=binding,
                    present_in_source=present_in_source,
                )
                all_rows_map[relative_path] = updated_row
                await record_ingestion_item_event(
                    db,
                    source_id=source_id,
                    item_path=relative_path,
                    event_type=event_type,
                    payload={
                        "action": action,
                        "job_id": str(jid),
                        "sync_status": sync_status,
                    },
                )
                result_summary["processed"] += 1

            if staged_snapshot:
                snapshot = await update_source_snapshot(
                    db,
                    snapshot_id=int(staged_snapshot["id"]),
                    status="success",
                    summary=result_summary,
                )
                if staged_artifact:
                    await update_source_artifact(
                        db,
                        artifact_id=int(staged_artifact["id"]),
                        status="active",
                    )
            else:
                snapshot = await create_source_snapshot(
                    db,
                    source_id=source_id,
                    snapshot_kind="local_directory",
                    status="success",
                    summary=result_summary,
                )
            await finish_source_sync_job(
                db,
                source_id=source_id,
                job_id=str(jid),
                outcome="success",
                snapshot_id=int(snapshot["id"]),
            )

        jm.complete_job(
            jid,
            result=result_summary,
            worker_id=worker_id,
            lease_id=lease_id or None,
            completion_token=lease_id or None,
        )
    except _NONCRITICAL_EXCEPTIONS as exc:
        with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
            async with pool.transaction() as db:
                if staged_snapshot:
                    await update_source_snapshot(
                        db,
                        snapshot_id=int(staged_snapshot["id"]),
                        status="failed",
                        summary={
                            "status": "failed",
                            "error": str(exc),
                        },
                    )
                if staged_artifact:
                    await update_source_artifact(
                        db,
                        artifact_id=int(staged_artifact["id"]),
                        status="failed",
                        metadata={"error": str(exc)},
                    )
                await finish_source_sync_job(
                    db,
                    source_id=source_id,
                    job_id=str(jid),
                    outcome="failure",
                    error=str(exc),
                )
        jm.fail_job(
            jid,
            error=str(exc),
            retryable=False,
            worker_id=worker_id,
            lease_id=lease_id or None,
            completion_token=lease_id or None,
        )


async def run_ingestion_sources_worker(stop_event: asyncio.Event | None = None) -> None:
    if JobManager is None:
        logger.warning("Jobs manager unavailable; ingestion sources worker disabled")
        return

    jm = JobManager()
    worker_id = "ingestion-sources-worker"
    poll_sleep = float(os.getenv("INGESTION_SOURCES_POLL_INTERVAL_SECONDS", "1.0") or "1.0")
    queue_name = ingestion_sources_queue()

    logger.info("Starting ingestion sources worker")
    while True:
        if stop_event and stop_event.is_set():
            logger.info("Stopping ingestion sources worker on shutdown signal")
            return
        try:
            job = jm.acquire_next_job(
                domain=DOMAIN,
                queue=queue_name,
                lease_seconds=120,
                worker_id=worker_id,
            )
            if not job:
                await asyncio.sleep(poll_sleep)
                continue

            payload = job.get("payload") or {}
            await _process_sync_job(
                jm,
                jid=int(job["id"]),
                lease_id=str(job.get("lease_id") or ""),
                worker_id=worker_id,
                source_id=int(payload.get("source_id")),
                user_id=int(job.get("owner_user_id") or payload.get("user_id") or 0),
            )
        except _NONCRITICAL_EXCEPTIONS:
            await asyncio.sleep(poll_sleep)


async def start_ingestion_sources_worker() -> asyncio.Task | None:
    if not env_flag_enabled("INGESTION_SOURCES_WORKER_ENABLED"):
        return None
    stop = asyncio.Event()
    return asyncio.create_task(run_ingestion_sources_worker(stop), name="ingestion-sources-worker")
