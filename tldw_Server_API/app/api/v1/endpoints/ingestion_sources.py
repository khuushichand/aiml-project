from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from tldw_Server_API.app.api.v1.schemas.ingestion_sources import (
    IngestionSourceCreateRequest,
    IngestionSourceResponse,
    IngestionSourceSyncTriggerResponse,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.Ingestion_Sources.jobs import enqueue_ingestion_source_job
from tldw_Server_API.app.core.Ingestion_Sources.local_directory import validate_local_directory_source
from tldw_Server_API.app.core.Ingestion_Sources.service import (
    create_source,
    ensure_ingestion_sources_schema,
    get_source_by_id,
    list_sources_by_user,
)

router = APIRouter(prefix="/ingestion-sources", tags=["ingestion-sources"])


def _prepare_create_payload(payload: IngestionSourceCreateRequest) -> dict[str, Any]:
    result = payload.model_dump()
    config = dict(result.get("config") or {})
    if payload.source_type == "local_directory":
        config["path"] = str(validate_local_directory_source(config))
    result["config"] = config
    return result


@router.post(
    "/",
    response_model=IngestionSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ingestion_source(
    payload: IngestionSourceCreateRequest,
    current_user: User = Depends(get_request_user),
):
    db_pool = await get_db_pool()
    async with db_pool.transaction() as db:
        await ensure_ingestion_sources_schema(db)
        row = await create_source(db, user_id=int(current_user.id), payload=_prepare_create_payload(payload))
    return row


@router.get("/", response_model=list[IngestionSourceResponse])
async def list_ingestion_sources(current_user: User = Depends(get_request_user)):
    db_pool = await get_db_pool()
    async with db_pool.transaction() as db:
        await ensure_ingestion_sources_schema(db)
        rows = await list_sources_by_user(db, user_id=int(current_user.id))
    return rows


@router.get("/{source_id}", response_model=IngestionSourceResponse)
async def get_ingestion_source(source_id: int, current_user: User = Depends(get_request_user)):
    db_pool = await get_db_pool()
    async with db_pool.transaction() as db:
        await ensure_ingestion_sources_schema(db)
        row = await get_source_by_id(db, source_id=source_id, user_id=int(current_user.id))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion source not found")
    return row


@router.post(
    "/{source_id}/sync",
    response_model=IngestionSourceSyncTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_ingestion_source_sync(source_id: int, current_user: User = Depends(get_request_user)):
    db_pool = await get_db_pool()
    async with db_pool.transaction() as db:
        await ensure_ingestion_sources_schema(db)
        row = await get_source_by_id(db, source_id=source_id, user_id=int(current_user.id))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion source not found")

    job = await asyncio.to_thread(
        enqueue_ingestion_source_job,
        user_id=int(current_user.id),
        source_id=source_id,
    )
    return {
        "status": "queued",
        "source_id": source_id,
        "job_id": job.get("id"),
    }
