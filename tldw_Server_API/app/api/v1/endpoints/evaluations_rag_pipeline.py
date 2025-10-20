"""
RAG pipeline preset and cleanup endpoints extracted from evaluations_unified.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
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
    PipelinePresetCreate, PipelinePresetResponse, PipelinePresetListResponse, PipelineCleanupResponse,
)
from tldw_Server_API.app.core.RAG.rag_service.vector_stores import (
    VectorStoreFactory,
    create_from_settings_for_user,
)
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope


pipeline_router = APIRouter()


@pipeline_router.post(
    "/rag/pipeline/presets",
    response_model=PipelinePresetResponse,
    dependencies=[Depends(require_token_scope("workflows", require_if_present=True, endpoint_id="evals.rag_pipeline.preset.create"))],
)
async def create_or_update_pipeline_preset(
    preset: PipelinePresetCreate,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        db = svc.db
        if db is None:
            raise ValueError("Database not available")
        db.upsert_pipeline_preset(preset.name, preset.config, user_id=user_id)
        row = db.get_pipeline_preset(preset.name)

        def to_ts(x: str) -> Optional[int]:
            try:
                if not x:
                    return None
                if "T" in x:
                    return int(datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp())
                return int(datetime.strptime(x, "%Y-%m-%d %H:%M:%S").timestamp())
            except Exception:
                return None

        return PipelinePresetResponse(
            name=row["name"],
            config=row["config"],
            created_at=to_ts(row.get("created_at")),
            updated_at=to_ts(row.get("updated_at")),
        )
    except Exception as e:
        logger.error(f"Failed to save preset: {e}")
        raise create_error_response(
            message=f"Failed to save preset: {sanitize_error_message(e, 'save_preset')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@pipeline_router.get(
    "/rag/pipeline/presets",
    response_model=PipelinePresetListResponse,
    dependencies=[Depends(require_token_scope("workflows", require_if_present=True, endpoint_id="evals.rag_pipeline.preset.list"))],
)
async def list_pipeline_presets(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        db = svc.db
        if db is None:
            raise ValueError("Database not available")
        items, total = db.list_pipeline_presets(limit=limit, offset=offset)
        resp_items = []

        def to_ts(x: str) -> Optional[int]:
            try:
                if not x:
                    return None
                if "T" in x:
                    return int(datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp())
                return int(datetime.strptime(x, "%Y-%m-%d %H:%M:%S").timestamp())
            except Exception:
                return None

        for r in items:
            resp_items.append(PipelinePresetResponse(
                name=r["name"],
                config=r["config"],
                created_at=to_ts(r.get("created_at")),
                updated_at=to_ts(r.get("updated_at")),
            ))
        return PipelinePresetListResponse(items=resp_items, total=total)
    except Exception as e:
        logger.error(f"Failed to list presets: {e}")
        raise create_error_response(
            message=f"Failed to list presets: {sanitize_error_message(e, 'list_presets')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@pipeline_router.get(
    "/rag/pipeline/presets/{name}",
    response_model=PipelinePresetResponse,
    dependencies=[Depends(require_token_scope("workflows", require_if_present=True, endpoint_id="evals.rag_pipeline.preset.get"))],
)
async def get_pipeline_preset(
    name: str,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        db = svc.db
        if db is None:
            raise ValueError("Database not available")
        row = db.get_pipeline_preset(name)
        if not row:
            raise create_error_response(
                message=f"Preset {name} not found",
                error_type="not_found_error",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        def to_ts(x: str) -> Optional[int]:
            try:
                if not x:
                    return None
                if "T" in x:
                    return int(datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp())
                return int(datetime.strptime(x, "%Y-%m-%d %H:%M:%S").timestamp())
            except Exception:
                return None

        return PipelinePresetResponse(
            name=row["name"],
            config=row["config"],
            created_at=to_ts(row.get("created_at")),
            updated_at=to_ts(row.get("updated_at")),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get preset: {e}")
        raise create_error_response(
            message=f"Failed to get preset: {sanitize_error_message(e, 'get_preset')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@pipeline_router.delete(
    "/rag/pipeline/presets/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_token_scope("workflows", require_if_present=True, endpoint_id="evals.rag_pipeline.preset.delete"))],
)
async def delete_pipeline_preset(
    name: str,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        db = svc.db
        if db is None:
            raise ValueError("Database not available")
        ok = db.delete_pipeline_preset(name)
        if not ok:
            raise create_error_response(
                message=f"Preset {name} not found",
                error_type="not_found_error",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete preset: {e}")
        raise create_error_response(
            message=f"Failed to delete preset: {sanitize_error_message(e, 'delete_preset')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@pipeline_router.post(
    "/rag/pipeline/cleanup",
    response_model=PipelineCleanupResponse,
    dependencies=[Depends(require_token_scope("workflows", require_if_present=True, endpoint_id="evals.rag_pipeline.cleanup"))],
)
async def cleanup_ephemeral_collections(
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """Delete expired ephemeral collections according to TTL registry."""
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        db = svc.db
        if db is None:
            raise ValueError("Database not available")
        expired = db.list_expired_ephemeral_collections()
        if not expired:
            return PipelineCleanupResponse(expired_count=0, deleted_count=0)
        from tldw_Server_API.app.core.config import settings as app_settings
        adapter = create_from_settings_for_user(app_settings, str(app_settings.get("SINGLE_USER_FIXED_ID", "1")))
        await adapter.initialize()
        deleted = 0
        errors: List[str] = []
        for name in expired:
            try:
                await adapter.delete_collection(name)
                db.mark_ephemeral_deleted(name)
                deleted += 1
            except Exception as e:
                logger.warning(f"Failed to delete expired collection {name}: {e}")
                errors.append(f"{name}: {str(e)}")
        return PipelineCleanupResponse(expired_count=len(expired), deleted_count=deleted, errors=errors or None)
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise create_error_response(
            message=f"Cleanup failed: {sanitize_error_message(e, 'cleanup')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
