"""
Datasets endpoints extracted from evaluations_unified.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from tldw_Server_API.app.api.v1.endpoints.evaluations_auth import (
    verify_api_key,
    create_error_response,
    sanitize_error_message,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import (
    get_unified_evaluation_service_for_user,
)
from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import (
    CreateDatasetRequest, DatasetResponse, DatasetListResponse,
)


datasets_router = APIRouter()


@datasets_router.post("/datasets", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    dataset_request: CreateDatasetRequest,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        dataset_id = svc.db.create_dataset(
            name=dataset_request.name,
            samples=[s.model_dump() for s in dataset_request.samples],
            description=dataset_request.description or "",
            created_by=user_id,
        )
        row = svc.db.get_dataset(dataset_id)
        return DatasetResponse(
            id=row["id"],
            name=row["name"],
            description=row.get("description"),
            samples=row.get("samples"),
            sample_count=row.get("sample_count") or 0,
            created_at=row.get("created_at"),
            created_by=row.get("created_by"),
            metadata=row.get("metadata"),
        )
    except Exception as e:
        logger.error(f"Failed to create dataset: {e}")
        raise create_error_response(
            message=f"Failed to create dataset: {sanitize_error_message(e, 'creating dataset')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@datasets_router.get("/datasets", response_model=DatasetListResponse)
async def list_datasets(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        items, total = svc.db.list_datasets(limit=limit, offset=offset)
        resp = []
        for r in items:
            resp.append(DatasetResponse(
                id=r["id"],
                name=r["name"],
                description=r.get("description"),
                samples=r.get("samples"),
                sample_count=r.get("sample_count") or 0,
                created_at=r.get("created_at"),
                created_by=r.get("created_by"),
                metadata=r.get("metadata"),
            ))
        return DatasetListResponse(items=resp, total=total)
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        raise create_error_response(
            message=f"Failed to list datasets: {sanitize_error_message(e, 'listing datasets')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@datasets_router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        row = svc.db.get_dataset(dataset_id)
        if not row:
            raise create_error_response(
                message="Dataset not found",
                error_type="not_found_error",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return DatasetResponse(
            id=row["id"],
            name=row["name"],
            description=row.get("description"),
            samples=row.get("samples"),
            sample_count=row.get("sample_count") or 0,
            created_at=row.get("created_at"),
            created_by=row.get("created_by"),
            metadata=row.get("metadata"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dataset: {e}")
        raise create_error_response(
            message=f"Failed to get dataset: {sanitize_error_message(e, 'retrieving dataset')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@datasets_router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: str,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        ok = svc.db.delete_dataset(dataset_id)
        if not ok:
            raise create_error_response(
                message="Dataset not found",
                error_type="not_found_error",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete dataset: {e}")
        raise create_error_response(
            message=f"Failed to delete dataset: {sanitize_error_message(e, 'deleting dataset')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

