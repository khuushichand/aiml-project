from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from tldw_Server_API.app.core.DB_Management.media_db.api import get_media_repository
from tldw_Server_API.app.core.External_Sources import connectors_service as svc
from tldw_Server_API.app.core.External_Sources.sync_adapter import FileSyncChange


def _utc_now_text() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _modified_at_from_metadata(metadata: dict[str, Any]) -> str | None:
    for key in (
        "modified_at",
        "modifiedAt",
        "modified_time",
        "modifiedTime",
        "last_modified",
        "lastModified",
        "lastModifiedDateTime",
    ):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return None


@dataclass(slots=True)
class FileSyncContentPayload:
    text: str
    prompt: str | None = None
    analysis_content: str | None = None
    safe_metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class SyncReconcileResult:
    action: str
    media_id: int | None
    binding_id: int | None = None
    current_version_number: int | None = None
    sync_status: str | None = None


def _build_safe_metadata(
    *,
    source_id: int,
    provider: str,
    change: FileSyncChange,
    content: FileSyncContentPayload,
    job_id: str | None,
) -> str:
    safe_metadata = dict(content.safe_metadata or {})
    safe_metadata.update(
        {
            "provider": provider,
            "source_id": source_id,
            "remote_id": change.remote_id,
            "remote_revision": change.remote_revision,
            "remote_hash": change.remote_hash,
            "remote_path": change.remote_path,
            "sync_job_id": job_id,
            "sync_kind": change.event_type,
        },
    )
    filtered = {key: value for key, value in safe_metadata.items() if value is not None}
    return json.dumps(filtered, sort_keys=True)


async def _get_required_binding(
    connectors_db,
    *,
    source_id: int,
    provider: str,
    remote_id: str,
) -> dict[str, Any]:
    binding = await svc.get_external_item_binding(
        connectors_db,
        source_id=source_id,
        provider=provider,
        external_id=remote_id,
    )
    if not binding:
        raise ValueError(f"No external binding found for source={source_id} provider={provider} remote_id={remote_id}")  # noqa: TRY003
    return binding


async def reconcile_file_change(
    connectors_db,
    media_db: Any,
    *,
    source_id: int,
    provider: str,
    change: FileSyncChange,
    content: FileSyncContentPayload | None = None,
    job_id: str | None = None,
) -> SyncReconcileResult:
    sync_now = _utc_now_text()
    metadata = change.metadata or {}
    modified_at = _modified_at_from_metadata(metadata)
    binding = await svc.get_external_item_binding(
        connectors_db,
        source_id=source_id,
        provider=provider,
        external_id=change.remote_id,
    )

    if not binding and change.event_type == "created":
        if content is None or content.text is None:
            raise ValueError("Content payload is required for event_type=created")  # noqa: TRY003
        media_id, _, _ = get_media_repository(media_db).add_media_with_keywords(
            url=f"{provider}://{change.remote_id}",
            title=change.remote_name or change.remote_id,
            media_type="document",
            content=content.text,
            keywords=[],
            prompt=content.prompt,
            analysis_content=content.analysis_content,
            safe_metadata=_build_safe_metadata(
                source_id=source_id,
                provider=provider,
                change=change,
                content=content,
                job_id=job_id,
            ),
            overwrite=False,
        )
        if media_id is None:
            raise ValueError(f"Failed to create media for source={source_id} remote_id={change.remote_id}")  # noqa: TRY003
        binding = await svc.upsert_external_item_binding(
            connectors_db,
            source_id=source_id,
            provider=provider,
            external_id=change.remote_id,
            name=change.remote_name,
            mime=metadata.get("mime_type"),
            size=metadata.get("size"),
            version=change.remote_revision,
            modified_at=modified_at,
            content_hash=change.remote_hash,
            media_id=int(media_id),
            sync_status="active",
            current_version_number=1,
            remote_parent_id=change.remote_parent_id,
            remote_path=change.remote_path,
            last_seen_at=sync_now,
            last_content_sync_at=sync_now,
            last_metadata_sync_at=sync_now,
            provider_metadata=metadata if metadata else None,
        )
        await svc.record_item_event(
            connectors_db,
            external_item_id=int(binding["id"]),
            event_type="created",
            job_id=job_id,
            payload={
                "remote_revision": change.remote_revision,
                "remote_hash": change.remote_hash,
                "sync_status": "active",
            },
        )
        return SyncReconcileResult(
            action="created",
            media_id=int(media_id),
            binding_id=int(binding["id"]),
            current_version_number=1,
            sync_status="active",
        )

    if not binding:
        raise ValueError(f"No external binding found for source={source_id} provider={provider} remote_id={change.remote_id}")  # noqa: TRY003

    media_id = binding.get("media_id")
    if media_id is None:
        raise ValueError(f"External binding {binding.get('id')} is missing media_id")  # noqa: TRY003

    if change.event_type in {"created", "content_updated"}:
        if content is None or content.text is None:
            raise ValueError(f"Content payload is required for event_type={change.event_type}")  # noqa: TRY003

        update_result = media_db.apply_synced_document_content_update(
            media_id=int(media_id),
            content=content.text,
            prompt=content.prompt,
            analysis_content=content.analysis_content,
            safe_metadata=_build_safe_metadata(
                source_id=source_id,
                provider=provider,
                change=change,
                content=content,
                job_id=job_id,
            ),
        )
        binding = await svc.upsert_external_item_binding(
            connectors_db,
            source_id=source_id,
            provider=provider,
            external_id=change.remote_id,
            name=change.remote_name,
            mime=metadata.get("mime_type"),
            size=metadata.get("size"),
            version=change.remote_revision,
            modified_at=modified_at,
            content_hash=change.remote_hash,
            media_id=int(media_id),
            sync_status="active",
            current_version_number=update_result["document_version_number"],
            remote_parent_id=change.remote_parent_id,
            remote_path=change.remote_path,
            last_seen_at=sync_now,
            last_content_sync_at=sync_now,
            last_metadata_sync_at=sync_now,
            provider_metadata=metadata if metadata else None,
        )
        await svc.record_item_event(
            connectors_db,
            external_item_id=int(binding["id"]),
            event_type="content_updated",
            job_id=job_id,
            payload={
                "remote_revision": change.remote_revision,
                "remote_hash": change.remote_hash,
                "sync_status": "active",
            },
        )
        return SyncReconcileResult(
            action="version_created",
            media_id=int(media_id),
            binding_id=int(binding["id"]),
            current_version_number=update_result["document_version_number"],
            sync_status="active",
        )

    if change.event_type in {"deleted", "permission_lost"}:
        sync_status = "archived_upstream_removed" if change.event_type == "deleted" else "orphaned"
        media_db.mark_as_trash(int(media_id))
        binding = await svc.mark_external_item_archived(
            connectors_db,
            source_id=source_id,
            provider=provider,
            external_id=change.remote_id,
            sync_status=sync_status,
        )
        if not binding:
            raise ValueError(f"Failed to archive binding for remote_id={change.remote_id}")  # noqa: TRY003
        await svc.record_item_event(
            connectors_db,
            external_item_id=int(binding["id"]),
            event_type="deleted_upstream" if change.event_type == "deleted" else "access_revoked",
            job_id=job_id,
            payload={"sync_status": sync_status},
        )
        return SyncReconcileResult(
            action="archived",
            media_id=int(media_id),
            binding_id=int(binding["id"]),
            current_version_number=binding.get("current_version_number"),
            sync_status=sync_status,
        )

    if change.event_type == "restored":
        media_db.restore_from_trash(int(media_id))
        binding = await svc.restore_external_item_binding(
            connectors_db,
            source_id=source_id,
            provider=provider,
            external_id=change.remote_id,
            name=change.remote_name,
            version=change.remote_revision,
            modified_at=modified_at,
            remote_parent_id=change.remote_parent_id,
            remote_path=change.remote_path,
            content_hash=change.remote_hash,
            provider_metadata=metadata if metadata else None,
        )
        if not binding:
            raise ValueError(f"Failed to restore binding for remote_id={change.remote_id}")  # noqa: TRY003
        await svc.record_item_event(
            connectors_db,
            external_item_id=int(binding["id"]),
            event_type="restored_upstream",
            job_id=job_id,
            payload={"sync_status": "active"},
        )
        return SyncReconcileResult(
            action="restored",
            media_id=int(media_id),
            binding_id=int(binding["id"]),
            current_version_number=binding.get("current_version_number"),
            sync_status="active",
        )

    if change.event_type == "metadata_updated":
        binding = await svc.upsert_external_item_binding(
            connectors_db,
            source_id=source_id,
            provider=provider,
            external_id=change.remote_id,
            name=change.remote_name,
            mime=metadata.get("mime_type"),
            size=metadata.get("size"),
            version=change.remote_revision,
            modified_at=modified_at,
            content_hash=change.remote_hash,
            media_id=int(media_id),
            sync_status=str(binding.get("sync_status") or "active"),
            current_version_number=binding.get("current_version_number"),
            remote_parent_id=change.remote_parent_id,
            remote_path=change.remote_path,
            last_seen_at=sync_now,
            last_metadata_sync_at=sync_now,
            provider_metadata=metadata if metadata else None,
        )
        await svc.record_item_event(
            connectors_db,
            external_item_id=int(binding["id"]),
            event_type="metadata_updated",
            job_id=job_id,
            payload={"sync_status": binding.get("sync_status")},
        )
        return SyncReconcileResult(
            action="metadata_updated",
            media_id=int(media_id),
            binding_id=int(binding["id"]),
            current_version_number=binding.get("current_version_number"),
            sync_status=binding.get("sync_status"),
        )

    raise ValueError(f"Unsupported file sync change event_type={change.event_type}")  # noqa: TRY003
