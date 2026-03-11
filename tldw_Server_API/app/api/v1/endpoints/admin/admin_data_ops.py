from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    BackupCreateRequest,
    BackupCreateResponse,
    BackupItem,
    BackupListResponse,
    BackupRestoreRequest,
    BackupRestoreResponse,
    DataSubjectRequestCreateRequest,
    DataSubjectRequestCreateResponse,
    DataSubjectRequestItem,
    DataSubjectRequestListResponse,
    DataSubjectRequestPreviewRequest,
    DataSubjectRequestPreviewResponse,
    RetentionPoliciesResponse,
    RetentionPolicy,
    RetentionPolicyUpdateRequest,
)
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos.data_subject_requests_repo import (
    AuthnzDataSubjectRequestsRepo,
)
from tldw_Server_API.app.core.AuthNZ.repos.users_repo import AuthnzUsersRepo
from tldw_Server_API.app.services.admin_data_ops_service import (
    create_backup_snapshot as svc_create_backup_snapshot,
    list_backup_items as svc_list_backup_items,
    list_retention_policies as svc_list_retention_policies,
    restore_backup_snapshot as svc_restore_backup_snapshot,
    update_retention_policy as svc_update_retention_policy,
)
from tldw_Server_API.app.services.admin_data_subject_requests_service import (
    list_data_subject_requests as svc_list_data_subject_requests,
    preview_data_subject_request as svc_preview_data_subject_request,
    record_data_subject_request as svc_record_data_subject_request,
)

router = APIRouter()


_DATA_OPS_NONCRITICAL_EXCEPTIONS = (
    asyncio.CancelledError,
    asyncio.TimeoutError,
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
    UnicodeDecodeError,
    HTTPException,
)


async def _build_dsr_repos() -> tuple[AuthnzUsersRepo, AuthnzDataSubjectRequestsRepo]:
    db_pool = await get_db_pool()
    return (
        AuthnzUsersRepo(db_pool=db_pool),
        AuthnzDataSubjectRequestsRepo(db_pool=db_pool),
    )


async def _enforce_admin_user_scope(
    principal: AuthPrincipal,
    target_user_id: int,
    *,
    require_hierarchy: bool,
) -> None:
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod

    await admin_mod._enforce_admin_user_scope(
        principal,
        target_user_id,
        require_hierarchy=require_hierarchy,
    )


async def _emit_admin_audit_event(
    request: Request,
    principal: AuthPrincipal,
    *,
    event_type: str,
    category: str,
    resource_type: str,
    resource_id: str | None,
    action: str,
    metadata: dict[str, Any],
) -> None:
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod

    await admin_mod._emit_admin_audit_event(
        request,
        principal,
        event_type=event_type,
        category=category,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        metadata=metadata,
    )

_BACKUP_DATASETS = {"media", "chacha", "prompts", "evaluations", "audit", "authnz"}
_PER_USER_BACKUP_DATASETS = _BACKUP_DATASETS - {"authnz"}


def _require_user_id_for_dataset(dataset: str, user_id: int | None) -> None:
    if dataset in _PER_USER_BACKUP_DATASETS and user_id is None:
        raise HTTPException(status_code=400, detail="user_id_required")


def _dsr_item_from_record(record: dict[str, Any]) -> DataSubjectRequestItem:
    return DataSubjectRequestItem(**record)


@router.get("/backups", response_model=BackupListResponse)
async def list_backups(
    dataset: str | None = Query(None, description="Dataset key to filter"),
    user_id: int | None = Query(None, description="User ID for per-user datasets"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> BackupListResponse:
    try:
        normalized_dataset = None
        if dataset:
            normalized_dataset = dataset.strip().lower()
            if normalized_dataset not in _BACKUP_DATASETS:
                raise HTTPException(status_code=400, detail="unknown_dataset")
            _require_user_id_for_dataset(normalized_dataset, user_id)
        if user_id is not None:
            await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        items, total = svc_list_backup_items(
            dataset=normalized_dataset,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        payload = [
            BackupItem(
                id=item.filename,
                dataset=item.dataset,
                user_id=item.user_id,
                status="ready",
                size_bytes=item.size_bytes,
                created_at=item.created_at,
            )
            for item in items
        ]
        return BackupListResponse(items=payload, total=total, limit=limit, offset=offset)
    except HTTPException:
        raise
    except _DATA_OPS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to list backups: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list backups") from exc


@router.post("/backups", response_model=BackupCreateResponse)
async def create_backup(
    payload: BackupCreateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> BackupCreateResponse:
    try:
        dataset = payload.dataset.strip().lower()
        if dataset not in _BACKUP_DATASETS:
            raise HTTPException(status_code=400, detail="unknown_dataset")
        _require_user_id_for_dataset(dataset, payload.user_id)
        if payload.user_id is not None:
            await _enforce_admin_user_scope(principal, payload.user_id, require_hierarchy=False)
        item = svc_create_backup_snapshot(
            dataset=dataset,
            user_id=payload.user_id,
            backup_type=payload.backup_type or "full",
            max_backups=payload.max_backups,
        )
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="data.write",
            category="system",
            resource_type="backup",
            resource_id=item.filename,
            action="backup.create",
            metadata={
                "dataset": dataset,
                "user_id": item.user_id,
                "size_bytes": item.size_bytes,
            },
        )
        return BackupCreateResponse(
            item=BackupItem(
                id=item.filename,
                dataset=item.dataset,
                user_id=item.user_id,
                status="ready",
                size_bytes=item.size_bytes,
                created_at=item.created_at,
            )
        )
    except ValueError as exc:
        if str(exc) == "unknown_dataset":
            raise HTTPException(status_code=400, detail="unknown_dataset") from exc
        raise HTTPException(status_code=400, detail="invalid_backup_request") from exc
    except HTTPException:
        raise
    except _DATA_OPS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to create backup: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create backup") from exc


@router.post("/backups/{backup_id}/restore", response_model=BackupRestoreResponse)
async def restore_backup(
    backup_id: str,
    payload: BackupRestoreRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> BackupRestoreResponse:
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm_required")
    try:
        dataset = payload.dataset.strip().lower()
        if dataset not in _BACKUP_DATASETS:
            raise HTTPException(status_code=400, detail="unknown_dataset")
        _require_user_id_for_dataset(dataset, payload.user_id)
        if payload.user_id is not None:
            await _enforce_admin_user_scope(principal, payload.user_id, require_hierarchy=False)
        result = svc_restore_backup_snapshot(
            dataset=dataset,
            user_id=payload.user_id,
            backup_id=backup_id,
        )
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="data.import",
            category="system",
            resource_type="backup",
            resource_id=backup_id,
            action="backup.restore",
            metadata={
                "dataset": dataset,
                "user_id": payload.user_id,
            },
        )
        return BackupRestoreResponse(status="restored", message=result)
    except ValueError as exc:
        if str(exc) == "unknown_dataset":
            raise HTTPException(status_code=400, detail="unknown_dataset") from exc
        raise HTTPException(status_code=400, detail="invalid_restore_request") from exc
    except HTTPException:
        raise
    except _DATA_OPS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to restore backup: {exc}")
        raise HTTPException(status_code=500, detail="Failed to restore backup") from exc


@router.post("/data-subject-requests/preview", response_model=DataSubjectRequestPreviewResponse)
async def preview_data_subject_request(
    payload: DataSubjectRequestPreviewRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> DataSubjectRequestPreviewResponse:
    try:
        users_repo, _ = await _build_dsr_repos()
        preview = await svc_preview_data_subject_request(
            requester_identifier=payload.requester_identifier,
            request_type=payload.request_type,
            categories=payload.categories,
            principal=principal,
            users_repo=users_repo,
        )
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="data.read",
            category="compliance",
            resource_type="data_subject_request",
            resource_id=str(preview["resolved_user_id"]),
            action="data_subject_request.preview",
            metadata={
                "requester_identifier": preview["requester_identifier"],
                "resolved_user_id": preview["resolved_user_id"],
                "selected_categories": preview["selected_categories"],
            },
        )
        return DataSubjectRequestPreviewResponse(**preview)
    except HTTPException:
        raise
    except _DATA_OPS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to preview data subject request: {exc}")
        raise HTTPException(status_code=500, detail="Failed to preview data subject request") from exc


@router.post("/data-subject-requests", response_model=DataSubjectRequestCreateResponse)
async def create_data_subject_request(
    payload: DataSubjectRequestCreateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> DataSubjectRequestCreateResponse:
    try:
        users_repo, requests_repo = await _build_dsr_repos()
        preview = await svc_preview_data_subject_request(
            requester_identifier=payload.requester_identifier,
            request_type=payload.request_type,
            categories=payload.categories,
            principal=principal,
            users_repo=users_repo,
        )
        record = await svc_record_data_subject_request(
            principal=principal,
            client_request_id=payload.client_request_id,
            requester_identifier=payload.requester_identifier,
            request_type=payload.request_type,
            categories=payload.categories,
            users_repo=users_repo,
            requests_repo=requests_repo,
            preview=preview,
            notes=payload.notes,
        )
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="data.write",
            category="compliance",
            resource_type="data_subject_request",
            resource_id=str(record.get("id") or payload.client_request_id),
            action="data_subject_request.record",
            metadata={
                "requester_identifier": record.get("requester_identifier"),
                "resolved_user_id": record.get("resolved_user_id"),
                "request_type": record.get("request_type"),
                "selected_categories": record.get("selected_categories"),
            },
        )
        return DataSubjectRequestCreateResponse(item=_dsr_item_from_record(record))
    except HTTPException:
        raise
    except _DATA_OPS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to record data subject request: {exc}")
        raise HTTPException(status_code=500, detail="Failed to record data subject request") from exc


@router.get("/data-subject-requests", response_model=DataSubjectRequestListResponse)
async def list_data_subject_requests(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> DataSubjectRequestListResponse:
    try:
        _, requests_repo = await _build_dsr_repos()
        items, total = await svc_list_data_subject_requests(
            principal,
            limit=limit,
            offset=offset,
            requests_repo=requests_repo,
        )
        return DataSubjectRequestListResponse(
            items=[_dsr_item_from_record(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except _DATA_OPS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to list data subject requests: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list data subject requests") from exc


@router.get("/retention-policies", response_model=RetentionPoliciesResponse)
async def list_retention_policies(
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> RetentionPoliciesResponse:
    try:
        del principal
        policies = [RetentionPolicy(**item) for item in await svc_list_retention_policies()]
        return RetentionPoliciesResponse(policies=policies)
    except _DATA_OPS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to list retention policies: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list retention policies") from exc


@router.put("/retention-policies/{policy_key}", response_model=RetentionPolicy)
async def update_retention_policy(
    policy_key: str,
    payload: RetentionPolicyUpdateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> RetentionPolicy:
    try:
        updated = await svc_update_retention_policy(policy_key, payload.days)
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="config.changed",
            category="system",
            resource_type="retention_policy",
            resource_id=policy_key,
            action="retention.update",
            metadata={"days": payload.days},
        )
        return RetentionPolicy(**updated)
    except ValueError as exc:
        detail = str(exc)
        if detail == "unknown_policy":
            raise HTTPException(status_code=404, detail="unknown_policy") from exc
        if detail == "invalid_range":
            raise HTTPException(status_code=400, detail="invalid_range") from exc
        raise HTTPException(status_code=400, detail="invalid_retention_update") from exc
    except _DATA_OPS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to update retention policy: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update retention policy") from exc
