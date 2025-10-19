"""
Datasets endpoints extracted from evaluations_unified.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
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


def _normalize_dataset_payload(dataset: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure required dataset response fields are populated."""
    # Work on a shallow copy to avoid mutating upstream caches
    normalized = dict(dataset)
    normalized.setdefault("object", "dataset")

    created = normalized.get("created")
    created_at = normalized.get("created_at")

    timestamp: Optional[int] = None
    if isinstance(created, (int, float)):
        timestamp = int(created)
    elif isinstance(created_at, (int, float)):
        timestamp = int(created_at)
    elif isinstance(created_at, str):
        try:
            # Support both ISO-8601 and SQLite timestamp formats
            ts = created_at.replace("Z", "+00:00")
            timestamp = int(datetime.fromisoformat(ts).timestamp())
        except Exception:
            timestamp = None

    if timestamp is None:
        timestamp = int(datetime.now(timezone.utc).timestamp())

    normalized["created"] = timestamp
    normalized["created_at"] = timestamp
    return normalized


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
        normalized = _normalize_dataset_payload(row)
        return DatasetResponse(**normalized)
    except Exception as e:
        logger.exception(f"Failed to create dataset: {e}")
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
        resp = [DatasetResponse(**_normalize_dataset_payload(r)) for r in items]
        return DatasetListResponse(data=resp, total=total)
    except Exception as e:
        logger.exception(f"Failed to list datasets: {e}")
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
        return DatasetResponse(**_normalize_dataset_payload(row))
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
