# mlx.py
# MLX provider lifecycle endpoints (admin-only)
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit, require_roles
from tldw_Server_API.app.api.v1.schemas.mlx import MLXLoadRequest, MLXUnloadRequest
from tldw_Server_API.app.core.Chat.Chat_Deps import ChatBadRequestError, ChatProviderError
from tldw_Server_API.app.core.LLM_Calls.providers.mlx_provider import (
    _default_settings,
    get_mlx_registry,
)

router = APIRouter()


@router.post(
    "/llm/providers/mlx/load",
    summary="Load or swap the active MLX model",
    dependencies=[Depends(check_rate_limit), Depends(require_roles("admin"))],
)
async def load_mlx_model(
    payload: MLXLoadRequest,
):
    registry = get_mlx_registry()
    overrides = payload.model_dump(exclude_none=True)
    model_path = overrides.pop("model_path", None) or _default_settings().get("model_path")
    try:
        status = registry.load(model_path=model_path, overrides=overrides)
        return status
    except ChatBadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ChatProviderError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected MLX load failure: {e}")
        raise HTTPException(status_code=500, detail="MLX load failed unexpectedly") from e


@router.post(
    "/llm/providers/mlx/unload",
    summary="Unload the active MLX model",
    dependencies=[Depends(check_rate_limit), Depends(require_roles("admin"))],
)
async def unload_mlx_model(
    payload: MLXUnloadRequest,
):
    registry = get_mlx_registry()
    try:
        return registry.unload()
    except Exception as e:
        logger.error(f"Unexpected MLX unload failure: {e}")
        raise HTTPException(status_code=500, detail="MLX unload failed unexpectedly") from e


@router.get(
    "/llm/providers/mlx/status",
    summary="Get MLX provider status",
    dependencies=[Depends(check_rate_limit), Depends(require_roles("admin"))],
)
async def get_mlx_status():
    registry = get_mlx_registry()
    try:
        return registry.status()
    except Exception as e:
        logger.error(f"Unexpected MLX status failure: {e}")
        raise HTTPException(status_code=500, detail="Failed to get MLX status") from e
