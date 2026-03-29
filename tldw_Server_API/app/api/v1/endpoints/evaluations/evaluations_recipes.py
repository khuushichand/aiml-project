"""Recipe registry and parent recipe-run endpoints."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Response, status
from loguru import logger

from tldw_Server_API.app.api.v1.endpoints.evaluations.evaluations_auth import (
    get_eval_request_user,
    require_eval_permissions,
    sanitize_error_message,
    verify_api_key,
)
from tldw_Server_API.app.api.v1.schemas.evaluation_recipe_schemas import (
    RecipeManifest,
    RecipeRunRecord,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.AuthNZ.permissions import EVALS_MANAGE, EVALS_READ
from tldw_Server_API.app.core.Evaluations.recipe_runs_jobs import (
    enqueue_recipe_run,
    mark_recipe_run_enqueue_failure,
)
from tldw_Server_API.app.core.Evaluations.recipe_runs_service import (
    RecipeDefinitionNotFoundError,
    RecipeRunNotFoundError,
    get_recipe_runs_service_for_user,
)
from tldw_Server_API.app.core.Evaluations.recipes.reporting import RecipeRunReport

recipes_router = APIRouter()


def _service_for_user(current_user: User):
    stable_user_id = getattr(current_user, "id_str", None) or str(current_user.id)
    return get_recipe_runs_service_for_user(stable_user_id)


def get_recipe_run_job_enqueuer() -> Callable[..., str]:
    """Return the callable used to enqueue recipe-run Jobs."""
    return enqueue_recipe_run


@recipes_router.get(
    "/recipes",
    response_model=list[RecipeManifest],
    dependencies=[Depends(require_eval_permissions(EVALS_READ))],
)
async def list_recipe_manifests(
    user_ctx: str = Depends(verify_api_key),
    current_user: User = Depends(get_eval_request_user),
):
    del user_ctx
    return _service_for_user(current_user).list_manifests()


@recipes_router.get(
    "/recipes/{recipe_id}",
    response_model=RecipeManifest,
    dependencies=[Depends(require_eval_permissions(EVALS_READ))],
)
async def get_recipe_manifest(
    recipe_id: str,
    user_ctx: str = Depends(verify_api_key),
    current_user: User = Depends(get_eval_request_user),
):
    del user_ctx
    service = _service_for_user(current_user)
    try:
        return service.get_manifest(recipe_id)
    except RecipeDefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc


@recipes_router.post(
    "/recipes/{recipe_id}/validate-dataset",
    dependencies=[Depends(require_eval_permissions(EVALS_READ))],
)
async def validate_recipe_dataset(
    recipe_id: str,
    payload: dict[str, Any],
    user_ctx: str = Depends(verify_api_key),
    current_user: User = Depends(get_eval_request_user),
):
    del user_ctx
    service = _service_for_user(current_user)
    try:
        return service.validate_dataset(
            recipe_id,
            dataset_id=payload.get("dataset_id"),
            dataset=payload.get("dataset"),
        )
    except RecipeDefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=sanitize_error_message(exc, "validating recipe dataset"),
        ) from exc


@recipes_router.post(
    "/recipes/{recipe_id}/runs",
    response_model=RecipeRunRecord,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_eval_permissions(EVALS_MANAGE))],
)
async def create_recipe_run(
    recipe_id: str,
    payload: dict[str, Any],
    response: Response,
    user_ctx: str = Depends(verify_api_key),
    current_user: User = Depends(get_eval_request_user),
    enqueue_run: Callable[..., str] = Depends(get_recipe_run_job_enqueuer),
):
    del user_ctx
    stable_user_id = getattr(current_user, "id_str", None) or str(current_user.id)
    service = _service_for_user(current_user)
    try:
        record = service.create_run(
            recipe_id,
            dataset_id=payload.get("dataset_id"),
            dataset=payload.get("dataset"),
            run_config=payload.get("run_config") or {},
            force_rerun=bool(payload.get("force_rerun", False)),
        )
        if getattr(record.status, "value", record.status) == "pending":
            try:
                enqueue_run(record, owner_user_id=stable_user_id)
            except Exception as exc:
                mark_recipe_run_enqueue_failure(service, record, error=str(exc))
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="recipe_run_enqueue_failed",
                ) from exc
            if response is not None:
                response.status_code = status.HTTP_202_ACCEPTED
        elif response is not None:
            response.status_code = status.HTTP_200_OK
        if response is not None:
            response.headers["Location"] = f"/api/v1/evaluations/recipe-runs/{record.run_id}"
        return record
    except RecipeDefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    except ValueError as exc:
        logger.debug("Recipe run creation rejected: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=sanitize_error_message(exc, "creating recipe run"),
        ) from exc


@recipes_router.get(
    "/recipe-runs/{run_id}",
    response_model=RecipeRunRecord,
    dependencies=[Depends(require_eval_permissions(EVALS_READ))],
)
async def get_recipe_run(
    run_id: str,
    user_ctx: str = Depends(verify_api_key),
    current_user: User = Depends(get_eval_request_user),
):
    del user_ctx
    service = _service_for_user(current_user)
    try:
        return service.get_run(run_id)
    except RecipeRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe run not found") from exc


@recipes_router.get(
    "/recipe-runs/{run_id}/report",
    response_model=RecipeRunReport,
    dependencies=[Depends(require_eval_permissions(EVALS_READ))],
)
async def get_recipe_run_report(
    run_id: str,
    user_ctx: str = Depends(verify_api_key),
    current_user: User = Depends(get_eval_request_user),
):
    del user_ctx
    service = _service_for_user(current_user)
    try:
        return service.get_report(run_id)
    except RecipeRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe run not found") from exc
