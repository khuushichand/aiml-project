from __future__ import annotations

import inspect
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from loguru import logger

from tldw_Server_API.app.api.v1.endpoints.evaluations.evaluations_auth import (
    create_error_response,
    get_eval_request_user,
    sanitize_error_message,
    verify_api_key,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.Evaluations.recipe_runs_service import (
    RecipeDatasetValidationRequest,
    RecipeRunRequest,
    get_recipe_runs_service_for_user,
)


recipe_router = APIRouter()

_RECIPE_ENDPOINT_EXCEPTIONS = (
    AttributeError,
    ConnectionError,
    KeyError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _get_service(current_user: User):
    stable_user_id = getattr(current_user, "id_str", None) or str(current_user.id)
    return get_recipe_runs_service_for_user(stable_user_id), stable_user_id


@recipe_router.get("/recipes")
async def list_recipes(current_user: User = Depends(get_eval_request_user)):
    try:
        service, _ = _get_service(current_user)
        recipes = await _maybe_await(service.list_recipes())
        return {"object": "list", "data": recipes}
    except _RECIPE_ENDPOINT_EXCEPTIONS as exc:
        logger.error(f"Failed to list recipe manifests: {exc}")
        raise create_error_response(
            message=f"Failed to list recipe manifests: {sanitize_error_message(exc, 'listing recipes')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc


@recipe_router.get("/recipes/{recipe_id}")
async def get_recipe_manifest(recipe_id: str, current_user: User = Depends(get_eval_request_user)):
    try:
        service, _ = _get_service(current_user)
        manifest = await _maybe_await(service.get_recipe_manifest(recipe_id))
        return manifest
    except HTTPException:
        raise
    except _RECIPE_ENDPOINT_EXCEPTIONS as exc:
        logger.error(f"Failed to fetch recipe manifest: {exc}")
        raise create_error_response(
            message=f"Failed to fetch recipe manifest: {sanitize_error_message(exc, 'fetching recipe manifest')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc


@recipe_router.post("/recipes/{recipe_id}/validate-dataset")
async def validate_recipe_dataset(
    recipe_id: str,
    request: RecipeDatasetValidationRequest,
    current_user: User = Depends(get_eval_request_user),
):
    try:
        service, _ = _get_service(current_user)
        validation = await _maybe_await(service.validate_recipe_dataset(recipe_id, request.model_dump()))
        return validation
    except _RECIPE_ENDPOINT_EXCEPTIONS as exc:
        logger.error(f"Failed to validate recipe dataset: {exc}")
        raise create_error_response(
            message=f"Failed to validate recipe dataset: {sanitize_error_message(exc, 'validating recipe dataset')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc


@recipe_router.post("/recipes/{recipe_id}/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_recipe_run(
    recipe_id: str,
    request: RecipeRunRequest,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_eval_request_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    response: Response = None,
):
    try:
        service, stable_user_id = _get_service(current_user)
        if idempotency_key:
            try:
                existing_id = service.db.lookup_idempotency("recipe_run", idempotency_key, stable_user_id)
                if existing_id:
                    existing = await _maybe_await(service.get_recipe_run(existing_id, created_by=stable_user_id))
                    if existing:
                        if response is not None:
                            response.headers["X-Idempotent-Replay"] = "true"
                            response.headers["Idempotency-Key"] = idempotency_key
                        return existing
            except _RECIPE_ENDPOINT_EXCEPTIONS as exc:
                logger.debug(f"recipe_runs: idempotency lookup failed for key {idempotency_key}: {exc}")
        run = await _maybe_await(service.create_recipe_run(recipe_id, request.model_dump(), created_by=stable_user_id))
        if run is None:
            raise ValueError("Recipe run creation returned no result")
        if idempotency_key and run.get("id"):
            try:
                service.db.record_idempotency("recipe_run", idempotency_key, run["id"], stable_user_id)
            except _RECIPE_ENDPOINT_EXCEPTIONS as exc:
                logger.debug(f"recipe_runs: failed to record idempotency for run {run.get('id')}: {exc}")
        return run
    except HTTPException:
        raise
    except _RECIPE_ENDPOINT_EXCEPTIONS as exc:
        logger.error(f"Failed to create recipe run: {exc}")
        raise create_error_response(
            message=f"Failed to create recipe run: {sanitize_error_message(exc, 'creating recipe run')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc


@recipe_router.get("/recipe-runs/{run_id}")
async def get_recipe_run(run_id: str, current_user: User = Depends(get_eval_request_user)):
    try:
        service, stable_user_id = _get_service(current_user)
        run = await _maybe_await(service.get_recipe_run(run_id, created_by=stable_user_id))
        if not run:
            raise create_error_response(
                message="Recipe run not found",
                error_type="not_found_error",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return run
    except HTTPException:
        raise
    except _RECIPE_ENDPOINT_EXCEPTIONS as exc:
        logger.error(f"Failed to fetch recipe run: {exc}")
        raise create_error_response(
            message=f"Failed to fetch recipe run: {sanitize_error_message(exc, 'retrieving recipe run')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc


@recipe_router.get("/recipe-runs/{run_id}/report")
async def get_recipe_report(run_id: str, current_user: User = Depends(get_eval_request_user)):
    try:
        service, stable_user_id = _get_service(current_user)
        report = await _maybe_await(service.get_recipe_report(run_id, created_by=stable_user_id))
        if not report:
            raise create_error_response(
                message="Recipe report not found",
                error_type="not_found_error",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return report
    except HTTPException:
        raise
    except _RECIPE_ENDPOINT_EXCEPTIONS as exc:
        logger.error(f"Failed to fetch recipe report: {exc}")
        raise create_error_response(
            message=f"Failed to fetch recipe report: {sanitize_error_message(exc, 'retrieving recipe report')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc
