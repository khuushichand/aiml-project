"""
Evaluations CRUD and Runs endpoints extracted from evaluations_unified.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Response, status
from loguru import logger

from tldw_Server_API.app.api.v1.endpoints.evaluations_auth import (
    verify_api_key,
    create_error_response,
    sanitize_error_message,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit
from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import (
    get_unified_evaluation_service_for_user,
)
from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat
from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import (
    CreateEvaluationRequest, UpdateEvaluationRequest, EvaluationResponse,
    EvaluationListResponse, RunResponse, RunListResponse
)


crud_router = APIRouter()


@crud_router.post(
    "/",
    response_model=EvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rbac_rate_limit("evals.create"))]
)
async def create_evaluation(
    eval_request: CreateEvaluationRequest,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    response: Response = None,
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        if idempotency_key:
            try:
                existing_id = svc.db.lookup_idempotency("evaluation", idempotency_key, user_id)
                if existing_id:
                    existing = await svc.get_evaluation(existing_id)
                    if existing:
                        try:
                            if response is not None:
                                response.headers["X-Idempotent-Replay"] = "true"
                                response.headers["Idempotency-Key"] = idempotency_key
                        except Exception as e:
                            logger.debug(f"evaluations_crud: failed to load eval metadata for {row.get('id') if isinstance(row, dict) else 'row'}: {e}")
                        return EvaluationResponse(**existing)
            except Exception as e:
                logger.debug(f"evaluations_crud: error during pagination counting: {e}")
        evaluation = await svc.create_evaluation(
            name=eval_request.name,
            description=eval_request.description,
            eval_type=eval_request.eval_type,
            eval_spec=model_dump_compat(eval_request.eval_spec),
            dataset_id=eval_request.dataset_id,
            dataset=[model_dump_compat(s) for s in eval_request.dataset] if eval_request.dataset else None,
            metadata=model_dump_compat(eval_request.metadata) if eval_request.metadata else None,
            created_by=user_id,
        )
        try:
            if idempotency_key and evaluation.get("id"):
                svc.db.record_idempotency("evaluation", idempotency_key, evaluation["id"], user_id)
        except Exception as e:
            logger.debug(f"evaluations_crud: failed to compute totals: {e}")
        return EvaluationResponse(**evaluation)
    except Exception as e:
        logger.error(f"Failed to create evaluation: {e}")
        raise create_error_response(
            message=f"Failed to create evaluation: {sanitize_error_message(e, 'evaluation creation')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@crud_router.get("/", response_model=EvaluationListResponse)
async def list_evaluations(
    limit: int = Query(20, ge=1, le=100),
    after: Optional[str] = Query(None),
    eval_type: Optional[str] = Query(None),
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        evaluations, has_more = await svc.list_evaluations(
            limit=limit,
            after=after,
            eval_type=eval_type,
            created_by=current_user.id,
        )
        first_id = evaluations[0]["id"] if evaluations else None
        last_id = evaluations[-1]["id"] if evaluations else None
        return EvaluationListResponse(
            object="list",
            data=[EvaluationResponse(**eval) for eval in evaluations],
            has_more=has_more,
            first_id=first_id,
            last_id=last_id,
        )
    except Exception as e:
        logger.error(f"Failed to list evaluations: {e}")
        raise create_error_response(
            message=f"Failed to list evaluations: {sanitize_error_message(e, 'listing evaluations')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@crud_router.get("/{eval_id}", response_model=EvaluationResponse)
async def get_evaluation(
    eval_id: str,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        evaluation = await svc.get_evaluation(eval_id)
        if not evaluation:
            raise create_error_response(
                message="Evaluation not found",
                error_type="not_found_error",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return EvaluationResponse(**evaluation)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get evaluation: {e}")
        raise create_error_response(
            message=f"Failed to get evaluation: {sanitize_error_message(e, 'retrieving evaluation')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@crud_router.patch("/{eval_id}", response_model=EvaluationResponse)
async def update_evaluation(
    eval_id: str,
    update_request: UpdateEvaluationRequest,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        # Only include explicitly provided fields; avoid overwriting with None
        updates = model_dump_compat(update_request, exclude_none=True, exclude_unset=True)
        evaluation = await svc.update_evaluation(eval_id, updates)
        if not evaluation:
            raise create_error_response(
                message="Evaluation not found",
                error_type="not_found_error",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return EvaluationResponse(**evaluation)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update evaluation: {e}")
        raise create_error_response(
            message=f"Failed to update evaluation: {sanitize_error_message(e, 'updating evaluation')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@crud_router.delete("/{eval_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation(
    eval_id: str,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        success = await svc.delete_evaluation(eval_id)
        if not success:
            raise create_error_response(
                message="Evaluation not found",
                error_type="not_found_error",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete evaluation: {e}")
        raise create_error_response(
            message=f"Failed to delete evaluation: {sanitize_error_message(e, 'deleting evaluation')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@crud_router.post("/{eval_id}/runs", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    eval_id: str,
    request: Dict[str, Any],
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        target_model = request.get("target_model")
        config = request.get("config", {})
        webhook_url = request.get("webhook_url")
        run = await svc.create_run(
            eval_id=eval_id,
            target_model=target_model,
            config=config,
            webhook_url=webhook_url,
            created_by=user_id,
        )
        return RunResponse(**run)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create run: {e}")
        raise create_error_response(
            message=f"Failed to create run: {sanitize_error_message(e, 'creating run')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@crud_router.get("/{eval_id}/runs", response_model=RunListResponse)
async def list_runs(
    eval_id: str,
    limit: int = Query(20, ge=1, le=100),
    after: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        runs, has_more = await svc.list_runs(eval_id=eval_id, status=status, limit=limit, after=after)
        first_id = runs[0]["id"] if runs else None
        last_id = runs[-1]["id"] if runs else None
        return RunListResponse(object="list", data=[RunResponse(**run) for run in runs], has_more=has_more, first_id=first_id, last_id=last_id)
    except Exception as e:
        logger.error(f"Failed to list runs: {e}")
        raise create_error_response(
            message=f"Failed to list runs: {sanitize_error_message(e, 'listing runs')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@crud_router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        run = await svc.get_run(run_id)
        if not run:
            raise create_error_response(
                message="Run not found",
                error_type="not_found_error",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return RunResponse(**run)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get run: {e}")
        raise create_error_response(
            message=f"Failed to get run: {sanitize_error_message(e, 'retrieving run')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@crud_router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        await svc.cancel_run(run_id, cancelled_by=user_id)
        return {"status": "cancelled", "run_id": run_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel run: {e}")
        raise create_error_response(
            message=f"Failed to cancel run: {sanitize_error_message(e, 'cancelling run')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
