# evaluations_unified.py - Unified evaluation API endpoints
"""
Unified evaluation API combining OpenAI-compatible and tldw-specific endpoints.

This module provides a single, cohesive API for all evaluation functionality.
"""

import os
import json
import asyncio
import time
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status, Query, Request, Response, Header, BackgroundTasks, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from loguru import logger

# Import unified schemas
from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import (
    # OpenAI-compatible schemas
    CreateEvaluationRequest, UpdateEvaluationRequest, EvaluationResponse,
    CreateRunRequest, RunResponse, RunResultsResponse,
    CreateDatasetRequest, DatasetResponse,
    EvaluationListResponse, RunListResponse, DatasetListResponse,
    
    # tldw-specific schemas
    GEvalRequest, GEvalResponse,
    RAGEvaluationRequest, RAGEvaluationResponse,
    PropositionEvaluationRequest, PropositionEvaluationResponse,
    ResponseQualityRequest, ResponseQualityResponse,
    BatchEvaluationRequest, BatchEvaluationResponse,
    CustomMetricRequest, CustomMetricResponse,
    EvaluationComparisonRequest, EvaluationComparisonResponse,
    EvaluationHistoryRequest, EvaluationHistoryResponse,
    
    # Webhook schemas
    WebhookRegistrationRequest, WebhookRegistrationResponse,
    WebhookUpdateRequest, WebhookStatusResponse,
    WebhookTestRequest, WebhookTestResponse,
    RateLimitStatusResponse,
    
    # Common schemas
    ErrorResponse, ErrorDetail, HealthCheckResponse,
    EvaluationMetric,
    PipelinePresetCreate, PipelinePresetResponse, PipelinePresetListResponse, PipelineCleanupResponse
)

# Import unified service
from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import (
    get_unified_evaluation_service,
    UnifiedEvaluationService
)
from tldw_Server_API.app.core.RAG.rag_service.vector_stores import VectorStoreFactory

# Import auth and rate limiting
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.exceptions import InvalidTokenError, TokenExpiredError
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter, get_rate_limiter
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_rate_limiter_dep

# Import additional services
from tldw_Server_API.app.core.Evaluations.user_rate_limiter import user_rate_limiter
from tldw_Server_API.app.core.Evaluations.metrics_advanced import advanced_metrics
from tldw_Server_API.app.api.v1.schemas.embeddings_abtest_schemas import (
    EmbeddingsABTestCreateRequest,
    EmbeddingsABTestCreateResponse,
    EmbeddingsABTestStatusResponse,
    EmbeddingsABTestResultsResponse,
    EmbeddingsABTestResultSummary,
    ArmSummary,
)
from tldw_Server_API.app.core.Evaluations.embeddings_abtest_service import (
    build_collections_vector_only,
    run_vector_search_and_score,
    compute_significance,
    run_abtest_full,
)
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode

# Create router
router = APIRouter(prefix="/evaluations", tags=["evaluations"])

# Security
security = HTTPBearer(auto_error=False)

# Lazy evaluation service initialization 
_evaluation_service = None

def get_evaluation_service():
    """Get evaluation service with lazy initialization"""
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = get_unified_evaluation_service()
    return _evaluation_service

def get_db():
    svc = get_evaluation_service()
    # Unified service exposes EvaluationsDatabase at svc.db
    return getattr(svc, 'db', None)


# ============= Authentication =============

async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY")
) -> str:
    """
    Verify API key or JWT token based on authentication mode.
    
    Supports both single-user and multi-user modes with OpenAI compatibility.
    """
    settings = get_settings()

    # Testing bypass: allow requests without credentials when explicit test flags are set
    try:
        if os.getenv("TESTING", "").lower() in ("true", "1", "yes") and \
           os.getenv("EVALS_HEAVY_ADMIN_ONLY", "true").lower() not in ("true", "1", "yes"):
            # In tests where heavy admin gating is disabled, treat caller as a test user
            return "test_user"
    except Exception:
        pass
    
    # Determine token source
    token = None
    if settings.AUTH_MODE == "single_user" and x_api_key and isinstance(x_api_key, str):
        token = x_api_key
    elif credentials:
        token = credentials.credentials
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {
                "message": "Missing API key or token",
                "type": "authentication_error",
                "code": "missing_credentials"
            }}
        )
    
    # Remove Bearer prefix if present
    if isinstance(token, str) and token.startswith("Bearer "):
        token = token[7:]
    
    # Handle based on authentication mode
    if settings.AUTH_MODE == "single_user":
        expected_token = os.getenv("SINGLE_USER_API_KEY") or settings.SINGLE_USER_API_KEY
        
        if not expected_token:
            logger.error("No API key configured for single-user mode")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": {
                    "message": "Server authentication not configured",
                    "type": "configuration_error",
                    "code": "auth_not_configured"
                }}
            )
        
        if token == expected_token:
            return "single_user"
            
    elif settings.AUTH_MODE == "multi_user":
        try:
            jwt_service = JWTService(settings)
            payload = jwt_service.decode_access_token(token)
            return f"user_{payload['sub']}"
        except TokenExpiredError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {
                    "message": "Token has expired",
                    "type": "authentication_error",
                    "code": "token_expired"
                }}
            )
        except InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {
                    "message": sanitize_error_message(e, "authentication"),
                    "type": "authentication_error",
                    "code": "invalid_token"
                }}
            )
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {
            "message": "Invalid API key or token",
            "type": "authentication_error",
            "code": "invalid_credentials"
        }}
    )


# ============= Rate Limiting =============

async def check_evaluation_rate_limit(
    request: Request,
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep)
):
    """Check rate limit for evaluation endpoints"""
    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path
    
    # Determine rate limit based on endpoint type
    if "batch" in path:
        limit = 5
        endpoint_type = "eval_batch"
    elif "/runs" in path:
        limit = 10
        endpoint_type = "eval_run"
    else:
        limit = 60
        endpoint_type = "eval_standard"

    
    allowed, metadata = await rate_limiter.check_rate_limit(
        client_ip,
        endpoint_type,
        limit=limit,
        window_minutes=1
    )
    
    if not allowed:
        retry_after = metadata.get("retry_after", 60)
        logger.warning(f"Rate limit exceeded for {client_ip} on {endpoint_type}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {retry_after} seconds",
            headers={"Retry-After": str(retry_after)}
    )


# ============= Error Handling =============

def sanitize_error_message(error: Exception, context: str = "") -> str:
    """Sanitize error messages to prevent information exposure.
    
    Args:
        error: The exception to sanitize
        context: Optional context about where the error occurred
        
    Returns:
        A safe error message that doesn't expose sensitive information
    """
    # Log the full error details for debugging
    logger.error(f"Error in {context}: {type(error).__name__}: {str(error)}")
    
    # Map specific exception types to safe messages
    error_type = type(error).__name__
    
    # Common safe error messages
    safe_messages = {
        "FileNotFoundError": "The requested resource was not found",
        "PermissionError": "Permission denied for this operation",
        "ValueError": "Invalid input provided",
        "KeyError": "Required data is missing",
        "ConnectionError": "Connection failed. Please try again later",
        "TimeoutError": "Operation timed out. Please try again",
        "DatabaseError": "Database operation failed",
        "IntegrityError": "Data integrity error occurred",
        "NotFoundError": "The requested resource was not found",
        "ValidationError": "Validation failed for the provided data",
    }
    
    # Return safe message based on error type
    if error_type in safe_messages:
        return safe_messages[error_type]
    
    # For unknown errors, return a generic message
    if context:
        return f"An error occurred during {context}"
    return "An internal error occurred. Please try again later"


def create_error_response(
    message: str,
    error_type: str = "invalid_request_error",
    param: Optional[str] = None,
    code: Optional[str] = None,
    status_code: int = status.HTTP_400_BAD_REQUEST
) -> HTTPException:
    """Create standardized error response"""
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "message": message,
                "type": error_type,
                "param": param,
                "code": code
            }
        }
    )


def require_admin(user: User) -> None:
    try:
        if is_single_user_mode():
            return
    except Exception:
        pass
    # Admin-only switch override by env
    import os as _os
    if _os.getenv("EVALS_HEAVY_ADMIN_ONLY", "true").lower() not in ("true", "1", "yes"):
        return
    if not user or not getattr(user, 'is_admin', False):
        raise HTTPException(status_code=403, detail="Admin privileges required for heavy evaluations")


# ================= Embeddings A/B Test (stubs) =================

@router.post("/embeddings/abtest", response_model=EmbeddingsABTestCreateResponse)
async def create_embeddings_abtest(
    payload: EmbeddingsABTestCreateRequest,
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
):
    """Create an embeddings A/B test (stub).

    Validates shape and returns a generated test_id. Persistence to DB and
    orchestration will be added in implementation phases per plan.
    """
    # Simple test_id generation
    svc = get_evaluation_service()
    db = svc.db
    # Persist test, arms, and queries
    test_id = db.create_abtest(name=payload.name, config=payload.config.model_dump(), created_by=user_ctx)
    # Insert arms
    for idx, arm in enumerate(payload.config.arms):
        db.upsert_abtest_arm(
            test_id=test_id,
            arm_index=idx,
            provider=arm.provider,
            model_id=arm.model,
            dimensions=arm.dimensions,
            status='pending',
        )
    # Insert queries
    db.insert_abtest_queries(test_id, [q.model_dump() for q in payload.config.queries])
    logger.info(f"A/B test created: {test_id} by {user_ctx}")
    return EmbeddingsABTestCreateResponse(test_id=test_id, status='created')


@router.post("/embeddings/abtest/{test_id}/run", response_model=EmbeddingsABTestStatusResponse)
async def run_embeddings_abtest(
    test_id: str,
    payload: EmbeddingsABTestCreateRequest,
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
    media_db = Depends(get_media_db_for_user),
    current_user: User = Depends(get_request_user),
):
    """Start an embeddings A/B test (stub runner).

    As a minimal integration path, embed queries for each arm using the
    arm's provider/model to avoid retriever refactors. Returns running status.
    """
    # Admin gating for heavy runs
    require_admin(current_user)
    svc = get_evaluation_service()
    db = svc.db
    # Launch background job
    asyncio.create_task(run_abtest_full(db, payload.config, test_id, str(current_user.id), media_db))
    logger.info(f"A/B test started in background: {test_id}")
    return EmbeddingsABTestStatusResponse(test_id=test_id, status='running', progress={"phase": 0.05})


@router.get("/embeddings/abtest/{test_id}", response_model=EmbeddingsABTestResultSummary)
async def get_embeddings_abtest_status(
    test_id: str,
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
):
    svc = get_evaluation_service()
    row = svc.db.get_abtest(test_id)
    if not row:
        raise HTTPException(status_code=404, detail="abtest not found")
    status = row.get('status', 'pending')
    aggregates = {}
    try:
        stats_json = json.loads(row.get('stats_json') or '{}')
        aggregates = stats_json.get('aggregates') or {}
    except Exception:
        aggregates = {}
    arms_rows = svc.db.get_abtest_arms(test_id)
    arms = []
    for ar in arms_rows:
        metrics = aggregates.get(ar['arm_id']) or {}
        # Extract doc/chunk counts if present
        doc_counts = {}
        try:
            s = ar.get('stats_json')
            if s:
                sj = json.loads(s)
                if isinstance(sj, dict):
                    if 'doc_count' in sj:
                        doc_counts['docs'] = int(sj.get('doc_count') or 0)
                    if 'chunk_count' in sj:
                        doc_counts['chunks'] = int(sj.get('chunk_count') or 0)
        except Exception:
            doc_counts = {}
        arms.append(ArmSummary(
            arm_id=ar['arm_id'],
            provider=ar['provider'],
            model=ar['model_id'],
            dimensions=ar.get('dimensions'),
            metrics=metrics,
            latency_ms={
                "p50": metrics.get('latency_ms_p50', 0.0),
                "p95": metrics.get('latency_ms_p95', 0.0),
                "mean": metrics.get('latency_ms_mean', 0.0),
            },
            doc_counts=doc_counts
        ))
    return EmbeddingsABTestResultSummary(test_id=test_id, status=status, arms=arms)


@router.get("/embeddings/abtest/{test_id}/results", response_model=EmbeddingsABTestResultsResponse)
async def get_embeddings_abtest_results(
    test_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
):
    svc = get_evaluation_service()
    rows, total = svc.db.list_abtest_results(test_id, limit=page_size, offset=(page-1)*page_size)
    # Build summary
    row = svc.db.get_abtest(test_id)
    if not row:
        raise HTTPException(status_code=404, detail="abtest not found")
    status = row.get('status', 'pending')
    aggregates = {}
    try:
        stats_json = json.loads(row.get('stats_json') or '{}')
        aggregates = stats_json.get('aggregates') or {}
    except Exception:
        aggregates = {}
    arms_rows = svc.db.get_abtest_arms(test_id)
    arms = []
    for ar in arms_rows:
        metrics = aggregates.get(ar['arm_id']) or {}
        arms.append(ArmSummary(
            arm_id=ar['arm_id'],
            provider=ar['provider'],
            model=ar['model_id'],
            dimensions=ar.get('dimensions'),
            metrics=metrics,
            latency_ms={
                "p50": metrics.get('latency_ms_p50', 0.0),
                "p95": metrics.get('latency_ms_p95', 0.0),
                "mean": metrics.get('latency_ms_mean', 0.0),
            },
            doc_counts={}
        ))
    summary = EmbeddingsABTestResultSummary(test_id=test_id, status=status, arms=arms)
    return EmbeddingsABTestResultsResponse(summary=summary, page=page, page_size=page_size, total=total)


@router.get("/embeddings/abtest/{test_id}/significance")
async def get_embeddings_abtest_significance(
    test_id: str,
    metric: str = Query("ndcg"),
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
):
    svc = get_evaluation_service()
    _ = svc.db.get_abtest(test_id) or (_ for _ in ()).throw(HTTPException(404, "abtest not found"))
    return compute_significance(svc.db, test_id, metric=metric)


@router.get("/embeddings/abtest/{test_id}/events")
async def stream_embeddings_abtest_events(
    test_id: str,
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
):
    """SSE stream of progress and updates for an A/B test."""
    from fastapi.responses import StreamingResponse
    import asyncio as _aio
    import json as _json
    svc = get_evaluation_service()

    async def event_generator():
        last_payload = None
        while True:
            row = svc.db.get_abtest(test_id)
            if not row:
                yield f"data: {_json.dumps({'type': 'error', 'message': 'not_found'})}\n\n"
                break
            status = row.get('status', 'pending')
            stats = row.get('stats_json')
            payload = {"type": "status", "status": status}
            try:
                payload["stats"] = _json.loads(stats) if stats else {}
            except Exception:
                payload["stats"] = {}
            if payload != last_payload:
                yield f"data: {_json.dumps(payload)}\n\n"
                last_payload = payload
            if status in ("completed", "failed", "canceled"):
                break
            await _aio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


@router.delete("/embeddings/abtest/{test_id}")
async def delete_embeddings_abtest(
    test_id: str,
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
):
    """Cancel/cleanup an embeddings A/B test (stub)."""
    logger.info(f"A/B test deleted: {test_id} by {user_ctx}")
    return {"status": "deleted", "test_id": test_id}


@router.get("/embeddings/abtest/{test_id}/export")
async def export_embeddings_abtest(
    test_id: str,
    format: str = Query("json", pattern="^(json|csv)$"),
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
    current_user: User = Depends(get_request_user),
):
    """Export AB test results (JSON or CSV). Admin-only."""
    require_admin(current_user)
    svc = get_evaluation_service()
    rows, total = svc.db.list_abtest_results(test_id, limit=100000, offset=0)
    if format == 'json':
        return {"test_id": test_id, "total": total, "results": rows}
    # CSV
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["result_id", "arm_id", "query_id", "ranked_ids", "latency_ms", "metrics_json"])
    for r in rows:
        writer.writerow([r.get('result_id'), r.get('arm_id'), r.get('query_id'), r.get('ranked_ids'), r.get('latency_ms'), r.get('metrics_json')])
    return Response(content=output.getvalue(), media_type='text/csv', headers={"Content-Disposition": f"attachment; filename=abtest_{test_id}.csv"})


# ============= OpenAI-Compatible Evaluation Endpoints =============

@router.post(
    "",
    response_model=EvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rbac_rate_limit("evals.create"))]
)
async def create_evaluation(
    eval_request: CreateEvaluationRequest,
    user_id: str = Depends(verify_api_key)
):
    """
    Create a new evaluation definition (OpenAI-compatible).
    
    This endpoint creates an evaluation that can be run multiple times with different models.
    """
    try:
        evaluation = await get_evaluation_service().create_evaluation(
            name=eval_request.name,
            description=eval_request.description,
            eval_type=eval_request.eval_type,
            eval_spec=eval_request.eval_spec.dict(),
            dataset_id=eval_request.dataset_id,
            dataset=[sample.dict() for sample in eval_request.dataset] if eval_request.dataset else None,
            metadata=eval_request.metadata.dict() if eval_request.metadata else None,
            created_by=user_id
        )
        
        return EvaluationResponse(**evaluation)
        
    except Exception as e:
        logger.error(f"Failed to create evaluation: {e}")
        raise create_error_response(
            message=f"Failed to create evaluation: {sanitize_error_message(e, 'evaluation creation')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("", response_model=EvaluationListResponse)
async def list_evaluations(
    limit: int = Query(20, ge=1, le=100),
    after: Optional[str] = Query(None),
    eval_type: Optional[str] = Query(None),
    user_id: str = Depends(verify_api_key)
):
    """List evaluations with pagination"""
    try:
        evaluations, has_more = await get_evaluation_service().list_evaluations(
            limit=limit,
            after=after,
            eval_type=eval_type
        )
        
        first_id = evaluations[0]["id"] if evaluations else None
        last_id = evaluations[-1]["id"] if evaluations else None
        
        return EvaluationListResponse(
            object="list",
            data=[EvaluationResponse(**eval) for eval in evaluations],
            has_more=has_more,
            first_id=first_id,
            last_id=last_id
        )
        
    except Exception as e:
        logger.error(f"Failed to list evaluations: {e}")
        raise create_error_response(
            message=f"Failed to list evaluations: {sanitize_error_message(e, 'listing evaluations')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============= Rate Limit Management =============

@router.get("/rate-limits", response_model=RateLimitStatusResponse)
async def get_rate_limit_status(
    user_id: str = Depends(verify_api_key)
):
    """Get current rate limit status for the authenticated user"""
    try:
        summary = await user_rate_limiter.get_usage_summary(user_id)
        
        # Convert the nested structure to flat structure expected by RateLimitStatusResponse
        from datetime import datetime, timezone, timedelta
        return RateLimitStatusResponse(
            tier=summary.get("tier", "free"),
            limits={
                "evaluations_per_minute": summary.get("limits", {}).get("per_minute", {}).get("evaluations", 0),
                "evaluations_per_day": summary.get("limits", {}).get("daily", {}).get("evaluations", 0),
                "tokens_per_day": summary.get("limits", {}).get("daily", {}).get("tokens", 0),
                "cost_per_day": int(summary.get("limits", {}).get("daily", {}).get("cost", 0)),
                "cost_per_month": int(summary.get("limits", {}).get("monthly", {}).get("cost", 0))
            },
            usage={
                "evaluations_today": summary.get("usage", {}).get("today", {}).get("evaluations", 0),
                "tokens_today": summary.get("usage", {}).get("today", {}).get("tokens", 0),
                "cost_today": int(summary.get("usage", {}).get("today", {}).get("cost", 0)),
                "cost_month": int(summary.get("usage", {}).get("month", {}).get("cost", 0))
            },
            remaining={
                "daily_evaluations": summary.get("remaining", {}).get("daily_evaluations", 0),
                "daily_tokens": summary.get("remaining", {}).get("daily_tokens", 0),
                "daily_cost": int(summary.get("remaining", {}).get("daily_cost", 0)),
                "monthly_cost": int(summary.get("remaining", {}).get("monthly_cost", 0))
            },
            reset_at=datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        )
        
    except Exception as e:
        logger.error(f"Failed to get rate limit status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get rate limit status: {sanitize_error_message(e, 'rate limit check')}"
        )


# ============= Dataset Management Endpoints =============

# ============= Pipeline Presets & Cleanup Endpoints =============

@router.post("/rag/pipeline/presets", response_model=PipelinePresetResponse)
async def create_or_update_pipeline_preset(
    preset: PipelinePresetCreate,
    user_id: str = Depends(verify_api_key)
):
    try:
        db = get_db()
        if db is None:
            raise ValueError("Database not available")
        db.upsert_pipeline_preset(preset.name, preset.config, user_id=user_id)
        row = db.get_pipeline_preset(preset.name)
        # Convert timestamps to epoch seconds if present
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/rag/pipeline/presets", response_model=PipelinePresetListResponse)
async def list_pipeline_presets(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(verify_api_key)
):
    try:
        db = get_db()
        if db is None:
            raise ValueError("Database not available")
        items, total = db.list_pipeline_presets(limit=limit, offset=offset)
        # map to response
        resp_items = []
        for r in items:
            def to_ts(x: str) -> Optional[int]:
                try:
                    if not x:
                        return None
                    if "T" in x:
                        return int(datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp())
                    return int(datetime.strptime(x, "%Y-%m-%d %H:%M:%S").timestamp())
                except Exception:
                    return None
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/rag/pipeline/presets/{name}", response_model=PipelinePresetResponse)
async def get_pipeline_preset(name: str, user_id: str = Depends(verify_api_key)):
    try:
        db = get_db()
        if db is None:
            raise ValueError("Database not available")
        row = db.get_pipeline_preset(name)
        if not row:
            raise create_error_response(
                message=f"Preset {name} not found",
                error_type="not_found_error",
                status_code=status.HTTP_404_NOT_FOUND
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.delete("/rag/pipeline/presets/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline_preset(name: str, user_id: str = Depends(verify_api_key)):
    try:
        db = get_db()
        if db is None:
            raise ValueError("Database not available")
        ok = db.delete_pipeline_preset(name)
        if not ok:
            raise create_error_response(
                message=f"Preset {name} not found",
                error_type="not_found_error",
                status_code=status.HTTP_404_NOT_FOUND
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete preset: {e}")
        raise create_error_response(
            message=f"Failed to delete preset: {sanitize_error_message(e, 'delete_preset')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.post("/rag/pipeline/cleanup", response_model=PipelineCleanupResponse)
async def cleanup_ephemeral_collections(user_id: str = Depends(verify_api_key)):
    """Delete expired ephemeral collections according to TTL registry."""
    try:
        db = get_db()
        if db is None:
            raise ValueError("Database not available")
        expired = db.list_expired_ephemeral_collections()
        if not expired:
            return PipelineCleanupResponse(expired_count=0, deleted_count=0)
        from tldw_Server_API.app.core.config import settings as app_settings
        adapter = VectorStoreFactory.create_from_settings(app_settings, user_id=str(app_settings.get("SINGLE_USER_FIXED_ID", "1")))
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@router.post("/datasets", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    dataset_request: CreateDatasetRequest,
    user_id: str = Depends(verify_api_key)
):
    """Create a new dataset"""
    try:
        dataset_id = await get_evaluation_service().create_dataset(
            name=dataset_request.name,
            description=dataset_request.description,
            samples=[s.dict() for s in dataset_request.samples],
            metadata=dataset_request.metadata,
            created_by=user_id
        )
        
        dataset = await get_evaluation_service().get_dataset(dataset_id)
        if not dataset:
            raise ValueError("Failed to retrieve created dataset")
        
        return DatasetResponse(**dataset)
        
    except Exception as e:
        logger.error(f"Failed to create dataset: {e}")
        raise create_error_response(
            message=f"Failed to create dataset: {sanitize_error_message(e, 'creating dataset')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/datasets", response_model=DatasetListResponse)
async def list_datasets(
    limit: int = Query(20, ge=1, le=100),
    after: Optional[str] = Query(None),
    user_id: str = Depends(verify_api_key)
):
    """List datasets with pagination"""
    try:
        datasets, has_more = await get_evaluation_service().list_datasets(
            limit=limit,
            after=after
        )
        
        first_id = datasets[0]["id"] if datasets else None
        last_id = datasets[-1]["id"] if datasets else None
        
        return DatasetListResponse(
            object="list",
            data=[DatasetResponse(**ds) for ds in datasets],
            has_more=has_more,
            first_id=first_id,
            last_id=last_id
        )
        
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        raise create_error_response(
            message=f"Failed to list datasets: {sanitize_error_message(e, 'listing datasets')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    user_id: str = Depends(verify_api_key)
):
    """Get dataset by ID"""
    try:
        dataset = await get_evaluation_service().get_dataset(dataset_id)
        if not dataset:
            raise create_error_response(
                message=f"Dataset {dataset_id} not found",
                error_type="not_found_error",
                param="dataset_id",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        return DatasetResponse(**dataset)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dataset {dataset_id}: {e}")
        raise create_error_response(
            message=f"Failed to get dataset: {sanitize_error_message(e, 'retrieving dataset')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: str,
    user_id: str = Depends(verify_api_key)
):
    """Delete a dataset"""
    try:
        success = await get_evaluation_service().delete_dataset(dataset_id, deleted_by=user_id)
        if not success:
            raise create_error_response(
                message=f"Dataset {dataset_id} not found",
                error_type="not_found_error",
                param="dataset_id",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete dataset {dataset_id}: {e}")
        raise create_error_response(
            message=f"Failed to delete dataset: {sanitize_error_message(e, 'deleting dataset')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============= Health & Metrics Endpoints =============

@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Check evaluation service health"""
    try:
        health = await get_evaluation_service().health_check()
        return HealthCheckResponse(**health)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheckResponse(
            status="unhealthy",
            version="1.0.0",
            uptime=0,
            database="disconnected"
        )


@router.get("/metrics")
async def get_metrics(request: Request):
    """Get Prometheus metrics"""
    try:
        metrics_summary = await get_evaluation_service().get_metrics_summary()
        
        # Handle failure from service so error message is never exposed
        if "error" in metrics_summary:
            logger.error(f"Metrics endpoint service error: {metrics_summary['error']}")
            # Return a generic error message in both text/plain and JSON responses
            if "text/plain" in request.headers.get("accept", ""):
                # Prometheus format error response
                output = "# HELP evaluation_metrics_failed Metric collection failure\n"
                output += "# TYPE evaluation_metrics_failed counter\n"
                output += "evaluation_metrics_failed{} 1\n"
                return Response(
                    content=output,
                    media_type="text/plain; version=0.0.4; charset=utf-8"
                )
            # Return JSON error response
            return {"error": "Metrics are currently unavailable"}
        
        # Format as Prometheus text format if requested
        if "text/plain" in request.headers.get("accept", ""):
            # Convert to Prometheus format (simplified)
            output = "# HELP evaluation_requests_total Total evaluation requests\n"
            output += "# TYPE evaluation_requests_total counter\n"
            output += f"evaluation_requests_total {{}} {metrics_summary.get('total_requests', 0)}\n"
            
            return Response(
                content=output,
                media_type="text/plain; version=0.0.4; charset=utf-8"
            )
        
        # Return JSON format
        return metrics_summary
        
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        # Do not expose internal error, return generic error
        return {"error": "Metrics are currently unavailable"}


# ============= Webhook Management Endpoints =============

@router.post("/webhooks", response_model=WebhookRegistrationResponse)
async def register_webhook(
    request: WebhookRegistrationRequest,
    user_id: str = Depends(verify_api_key)
):
    """Register a webhook for evaluation notifications"""
    try:
        # Import webhook manager lazily to avoid heavy imports during OpenAPI generation
        from tldw_Server_API.app.core.Evaluations.webhook_manager import WebhookEvent, webhook_manager
        
        # Convert string event types to WebhookEvent enums
        events = []
        for event_str in request.events:
            # Handle both enum values and string values
            if hasattr(event_str, 'value'):
                # Already an enum
                event_value = event_str.value
            else:
                # String value
                event_value = event_str
                
            # Find matching enum
            for webhook_event in WebhookEvent:
                if webhook_event.value == event_value:
                    events.append(webhook_event)
                    break
        
        result = await webhook_manager.register_webhook(
            user_id=user_id,
            url=str(request.url),
            events=events,
            secret=request.secret
        )
        
        return WebhookRegistrationResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to register webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register webhook: {sanitize_error_message(e, 'webhook registration')}"
        )


@router.get("/webhooks", response_model=List[WebhookStatusResponse])
async def list_webhooks(
    user_id: str = Depends(verify_api_key)
):
    """List all registered webhooks for the authenticated user"""
    try:
        from tldw_Server_API.app.core.Evaluations.webhook_manager import webhook_manager
        webhooks = await webhook_manager.get_webhook_status(user_id)
        return [WebhookStatusResponse(**w) for w in webhooks]
        
    except Exception as e:
        logger.error(f"Failed to list webhooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list webhooks: {sanitize_error_message(e, 'listing webhooks')}"
        )


@router.delete("/webhooks")
async def unregister_webhook(
    url: str = Query(..., description="Webhook URL to unregister"),
    user_id: str = Depends(verify_api_key)
):
    """Unregister a webhook"""
    try:
        # Validate URL safety to avoid internal host targeting
        from tldw_Server_API.app.core.Security.url_validation import assert_url_safe
        from tldw_Server_API.app.core.Metrics import get_metrics_registry
        from tldw_Server_API.app.core.Evaluations.webhook_manager import webhook_manager
        try:
            assert_url_safe(url)
        except HTTPException as he:
            get_metrics_registry().increment("security_ssrf_block_total", 1)
            raise he
        success = await webhook_manager.unregister_webhook(user_id, url)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        return {"message": "Webhook unregistered successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unregister webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unregister webhook: {sanitize_error_message(e, 'webhook removal')}"
        )


@router.post("/webhooks/test", response_model=WebhookTestResponse)
async def test_webhook(
    request: WebhookTestRequest,
    user_id: str = Depends(verify_api_key)
):
    """Send a test webhook to verify endpoint configuration"""
    try:
        from tldw_Server_API.app.core.Evaluations.webhook_manager import webhook_manager
        result = await webhook_manager.test_webhook(user_id, str(request.url))
        return WebhookTestResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to test webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test webhook: {sanitize_error_message(e, 'webhook testing')}"
        )


@router.get("/{eval_id}", response_model=EvaluationResponse)
async def get_evaluation(
    eval_id: str,
    user_id: str = Depends(verify_api_key)
):
    """Get evaluation by ID"""
    try:
        evaluation = await get_evaluation_service().get_evaluation(eval_id)
        if not evaluation:
            raise create_error_response(
                message=f"Evaluation {eval_id} not found",
                error_type="not_found_error",
                param="eval_id",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        return EvaluationResponse(**evaluation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get evaluation {eval_id}: {e}")
        raise create_error_response(
            message=f"Failed to get evaluation: {sanitize_error_message(e, 'retrieving evaluation')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.patch("/{eval_id}", response_model=EvaluationResponse)
async def update_evaluation(
    eval_id: str,
    update_request: UpdateEvaluationRequest,
    user_id: str = Depends(verify_api_key)
):
    """Update evaluation definition"""
    try:
        updates = update_request.dict(exclude_unset=True)
        if not updates:
            raise create_error_response(
                message="No updates provided",
                error_type="invalid_request_error"
            )
        
        success = await get_evaluation_service().update_evaluation(
            eval_id, updates, updated_by=user_id
        )
        
        if not success:
            raise create_error_response(
                message=f"Evaluation {eval_id} not found",
                error_type="not_found_error",
                param="eval_id",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        evaluation = await get_evaluation_service().get_evaluation(eval_id)
        return EvaluationResponse(**evaluation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update evaluation {eval_id}: {e}")
        raise create_error_response(
            message=f"Failed to update evaluation: {sanitize_error_message(e, 'updating evaluation')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.delete("/{eval_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation(
    eval_id: str,
    user_id: str = Depends(verify_api_key)
):
    """Delete an evaluation"""
    try:
        success = await get_evaluation_service().delete_evaluation(eval_id, deleted_by=user_id)
        if not success:
            raise create_error_response(
                message=f"Evaluation {eval_id} not found",
                error_type="not_found_error",
                param="eval_id",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete evaluation {eval_id}: {e}")
        raise create_error_response(
            message=f"Failed to delete evaluation: {sanitize_error_message(e, 'deleting evaluation')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============= Run Management Endpoints =============

@router.post("/{eval_id}/runs", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    eval_id: str,
    run_request: CreateRunRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit)
):
    """Create and start an evaluation run"""
    try:
        run = await get_evaluation_service().create_run(
            eval_id=eval_id,
            target_model=run_request.target_model,
            config=run_request.config.dict() if run_request.config else None,
            dataset_override=run_request.dataset_override.dict() if run_request.dataset_override else None,
            webhook_url=str(run_request.webhook_url) if run_request.webhook_url else None,
            created_by=user_id
        )
        
        return RunResponse(**run)
        
    except ValueError as e:
        raise create_error_response(
            message=sanitize_error_message(e, "creating run"),
            error_type="not_found_error",
            param="eval_id",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to create run: {e}")
        raise create_error_response(
            message=f"Failed to create run: {sanitize_error_message(e, 'creating run')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/{eval_id}/runs", response_model=RunListResponse)
async def list_runs(
    eval_id: str,
    limit: int = Query(20, ge=1, le=100),
    after: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user_id: str = Depends(verify_api_key)
):
    """List runs for an evaluation"""
    try:
        runs, has_more = await get_evaluation_service().list_runs(
            eval_id=eval_id,
            status=status,
            limit=limit,
            after=after
        )
        
        first_id = runs[0]["id"] if runs else None
        last_id = runs[-1]["id"] if runs else None
        
        return RunListResponse(
            object="list",
            data=[RunResponse(**run) for run in runs],
            has_more=has_more,
            first_id=first_id,
            last_id=last_id
        )
        
    except Exception as e:
        logger.error(f"Failed to list runs: {e}")
        raise create_error_response(
            message=f"Failed to list runs: {sanitize_error_message(e, 'listing runs')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============= tldw-Specific Evaluation Endpoints =============

@router.post("/geval", response_model=GEvalResponse, dependencies=[Depends(check_evaluation_rate_limit)])
async def evaluate_geval(
    request: GEvalRequest,
    user_id: str = Depends(verify_api_key)
):
    """
    Evaluate a summary using G-Eval metrics.
    
    G-Eval evaluates summaries on fluency, consistency, relevance, and coherence.
    """
    # FIXME/TODO: Add per-user usage limits via user_rate_limiter to prevent abuse
    try:
        # Normalize user id for single-user mode to match webhook registrations
        try:
            from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings
            _settings = _get_settings()
            effective_user_id = str(_settings.SINGLE_USER_FIXED_ID) if user_id == "single_user" else user_id
        except Exception:
            effective_user_id = user_id

        # Send webhook: evaluation started (await in TEST_MODE)
        import os as _os
        import asyncio as _asyncio
        import time as _time
        from tldw_Server_API.app.core.Evaluations.webhook_manager import webhook_manager, WebhookEvent
        start_event_id = f"geval_{int(_time.time())}_{effective_user_id[:8]}"
        if _os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes"):
            await webhook_manager.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_STARTED,
                evaluation_id=start_event_id,
                data={
                    "evaluation_type": "geval",
                    "api_name": request.api_name
                }
            )
        else:
            _asyncio.create_task(webhook_manager.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_STARTED,
                evaluation_id=start_event_id,
                data={
                    "evaluation_type": "geval",
                    "api_name": request.api_name
                }
            ))

        result = await get_evaluation_service().evaluate_geval(
            source_text=request.source_text,
            summary=request.summary,
            metrics=request.metrics,
            api_name=request.api_name,
            api_key=request.api_key,
            user_id=effective_user_id
        )
        
        # Format response - accept either numeric or structured metric dicts
        raw_metrics = result["results"].get("metrics", {})
        formatted_metrics = {}
        explanations_fallback = result["results"].get("explanations", {})
        for metric_name, metric_value in raw_metrics.items():
            if isinstance(metric_value, dict):
                # Structured metric already provided
                name = metric_value.get("name", metric_name)
                score_val = metric_value.get("score", 0.0)
                try:
                    score_float = float(score_val) if score_val is not None else 0.0
                except (TypeError, ValueError):
                    score_float = 0.0
                raw_score_val = metric_value.get("raw_score", None)
                try:
                    raw_score_float = float(raw_score_val) if raw_score_val is not None else None
                except (TypeError, ValueError):
                    raw_score_float = None
                explanation = metric_value.get("explanation")
                metadata = metric_value.get("metadata", {})
                formatted_metrics[metric_name] = EvaluationMetric(
                    name=name,
                    score=score_float,
                    raw_score=raw_score_float,
                    explanation=explanation,
                    metadata=metadata,
                )
            else:
                # Backward-compat: simple numeric score; normalize if on 1-5 scale
                try:
                    score_num = float(metric_value)
                except (TypeError, ValueError):
                    score_num = 0.0
                normalized = score_num / 5.0 if score_num > 1.0 else score_num
                formatted_metrics[metric_name] = EvaluationMetric(
                    name=metric_name,
                    score=normalized,
                    raw_score=score_num,
                    explanation=explanations_fallback.get(metric_name, ""),
                )
        
        # Send webhook: evaluation completed (await in TEST_MODE)
        if _os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes"):
            await webhook_manager.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_COMPLETED,
                evaluation_id=result["evaluation_id"],
                data={
                    "evaluation_type": "geval",
                    "average_score": result["results"].get("average_score", 0.0),
                    "processing_time": result.get("evaluation_time", 0.0)
                }
            )
        else:
            _asyncio.create_task(webhook_manager.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_COMPLETED,
                evaluation_id=result["evaluation_id"],
                data={
                    "evaluation_type": "geval",
                    "average_score": result["results"].get("average_score", 0.0),
                    "processing_time": result.get("evaluation_time", 0.0)
                }
            ))

        return GEvalResponse(
            metrics=formatted_metrics,
            average_score=result["results"].get("average_score", 0.0),
            summary_assessment=result["results"].get("assessment", "Evaluation complete"),
            evaluation_time=result["evaluation_time"],
            metadata={"evaluation_id": result["evaluation_id"]}
        )
        
    except Exception as e:
        logger.error(f"G-Eval evaluation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation failed: {sanitize_error_message(e, 'G-Eval evaluation')}"
        )


@router.post("/rag", response_model=RAGEvaluationResponse, dependencies=[Depends(check_evaluation_rate_limit)])
async def evaluate_rag(
    request: RAGEvaluationRequest,
    user_id: str = Depends(verify_api_key)
):
    """
    Evaluate RAG system performance.
    
    Evaluates relevance, faithfulness, answer similarity, and context precision.
    """
    # FIXME/TODO: Add per-user usage limits via user_rate_limiter to prevent abuse
    try:
        # Normalize user id for single-user mode to match webhook registrations
        try:
            from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings
            _settings = _get_settings()
            effective_user_id = str(_settings.SINGLE_USER_FIXED_ID) if user_id == "single_user" else user_id
        except Exception:
            effective_user_id = user_id

        # Send webhook: evaluation started (await in TEST_MODE)
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.core.Evaluations.webhook_manager import webhook_manager, WebhookEvent
        import time as _time
        start_event_id = f"rag_{int(_time.time())}_{effective_user_id[:8]}"
        if _os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes"):
            await webhook_manager.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_STARTED,
                evaluation_id=start_event_id,
                data={
                    "evaluation_type": "rag",
                    "api_name": request.api_name
                }
            )
        else:
            _asyncio.create_task(webhook_manager.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_STARTED,
                evaluation_id=start_event_id,
                data={
                    "evaluation_type": "rag",
                    "api_name": request.api_name
                }
            ))

        result = await get_evaluation_service().evaluate_rag(
            query=request.query,
            contexts=request.retrieved_contexts,
            response=request.generated_response,
            ground_truth=request.ground_truth,
            metrics=request.metrics,
            api_name=request.api_name,
            user_id=effective_user_id
        )
        
        # Extract and format metrics from results
        raw_metrics = result["results"].get("metrics", {})
        formatted_metrics = {}
        for metric_name, score in raw_metrics.items():
            formatted_metrics[metric_name] = EvaluationMetric(
                name=metric_name,
                score=score if isinstance(score, (int, float)) else 0.0,
                raw_score=score if isinstance(score, (int, float)) else 0.0,
                explanation=""
            )
        
        # Send webhook: evaluation completed (await in TEST_MODE)
        if _os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes"):
            await webhook_manager.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_COMPLETED,
                evaluation_id=result["evaluation_id"],
                data={
                    "evaluation_type": "rag",
                    "overall_score": result["results"].get("overall_score", 0.0),
                    "processing_time": result.get("evaluation_time", 0.0)
                }
            )
        else:
            _asyncio.create_task(webhook_manager.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_COMPLETED,
                evaluation_id=result["evaluation_id"],
                data={
                    "evaluation_type": "rag",
                    "overall_score": result["results"].get("overall_score", 0.0),
                    "processing_time": result.get("evaluation_time", 0.0)
                }
            ))

        return RAGEvaluationResponse(
            metrics=formatted_metrics,
            overall_score=result["results"].get("overall_score", 0.0),
            retrieval_quality=result["results"].get("retrieval_quality", 0.0),
            generation_quality=result["results"].get("generation_quality", 0.0),
            suggestions=result["results"].get("suggestions", []),
            metadata={"evaluation_id": result["evaluation_id"]}
        )
        
    except Exception as e:
        logger.error(f"RAG evaluation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG evaluation failed: {sanitize_error_message(e, 'RAG evaluation')}"
        )


@router.post("/response-quality", response_model=ResponseQualityResponse, dependencies=[Depends(check_evaluation_rate_limit)])
async def evaluate_response_quality(
    request: ResponseQualityRequest,
    user_id: str = Depends(verify_api_key)
):
    """
    Evaluate the quality of a generated response.
    
    Checks relevance, completeness, accuracy, and format compliance.
    """
    # FIXME/TODO: Add per-user usage limits via user_rate_limiter to prevent abuse
    try:
        # Normalize user id for single-user mode to match webhook registrations
        try:
            from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings
            _settings = _get_settings()
            effective_user_id = str(_settings.SINGLE_USER_FIXED_ID) if user_id == "single_user" else user_id
        except Exception:
            effective_user_id = user_id

        # Send webhook: evaluation started (await in TEST_MODE)
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.core.Evaluations.webhook_manager import webhook_manager, WebhookEvent
        import time as _time
        start_event_id = f"response_quality_{int(_time.time())}_{effective_user_id[:8]}"
        if _os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes"):
            await webhook_manager.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_STARTED,
                evaluation_id=start_event_id,
                data={
                    "evaluation_type": "response_quality",
                    "api_name": request.api_name
                }
            )
        else:
            _asyncio.create_task(webhook_manager.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_STARTED,
                evaluation_id=start_event_id,
                data={
                    "evaluation_type": "response_quality",
                    "api_name": request.api_name
                }
            ))

        result = await get_evaluation_service().evaluate_response_quality(
            prompt=request.prompt,
            response=request.response,
            expected_format=request.expected_format,
            custom_criteria=request.evaluation_criteria,
            api_name=request.api_name,
            user_id=effective_user_id
        )

        # Convert metrics to proper EvaluationMetric structure
        metrics = {}
        for metric_name, metric_data in result["results"].get("metrics", {}).items():
            if isinstance(metric_data, dict):
                metrics[metric_name] = EvaluationMetric(
                    name=metric_data.get("name", metric_name),
                    score=metric_data.get("score", 0.0),
                    raw_score=metric_data.get("raw_score"),
                    explanation=metric_data.get("explanation"),
                    metadata=metric_data.get("metadata", {})
                )
            else:
                # Handle flat metric values (for backward compatibility)
                metrics[metric_name] = EvaluationMetric(
                    name=metric_name,
                    score=float(metric_data) if isinstance(metric_data, (int, float)) else 0.0,
                    explanation=f"{metric_name} score"
                )

        # Convert format_compliance to proper structure
        format_compliance = None
        if "format_compliance" in result["results"]:
            fc_value = result["results"]["format_compliance"]
            if isinstance(fc_value, bool):
                format_compliance = {"compliant": fc_value}
            elif isinstance(fc_value, dict):
                format_compliance = fc_value
            else:
                format_compliance = None

        # Send webhook: evaluation completed (await in TEST_MODE)
        if _os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes"):
            await webhook_manager.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_COMPLETED,
                evaluation_id=result["evaluation_id"],
                data={
                    "evaluation_type": "response_quality",
                    "overall_quality": result["results"].get("overall_quality", 0.0),
                    "processing_time": result.get("evaluation_time", 0.0)
                }
            )
        else:
            _asyncio.create_task(webhook_manager.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_COMPLETED,
                evaluation_id=result["evaluation_id"],
                data={
                    "evaluation_type": "response_quality",
                    "overall_quality": result["results"].get("overall_quality", 0.0),
                    "processing_time": result.get("evaluation_time", 0.0)
                }
            ))

        return ResponseQualityResponse(
            metrics=metrics,
            overall_quality=result["results"].get("overall_quality", 0.0),
            format_compliance=format_compliance,
            issues=result["results"].get("issues", []),
            improvements=result["results"].get("improvements", [])
        )

    except Exception as e:
        logger.error(f"Response quality evaluation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quality evaluation failed: {sanitize_error_message(e, 'quality evaluation')}"
        )


@router.post("/propositions", response_model=PropositionEvaluationResponse, dependencies=[Depends(check_evaluation_rate_limit)])
async def evaluate_propositions_endpoint(
    request: PropositionEvaluationRequest,
    user_id: str = Depends(verify_api_key)
):
    """
    Evaluate proposition extraction quality.
    Computes precision/recall/F1 with semantic or Jaccard matching and density metrics.
    """
    try:
        result = await get_evaluation_service().evaluate_propositions(
            extracted=request.extracted,
            reference=request.reference,
            method=request.method or 'semantic',
            threshold=request.threshold or 0.7,
            user_id=user_id
        )

        metrics = result["results"].get("metrics", {})
        counts = result["results"].get("counts", {})

        return PropositionEvaluationResponse(
            precision=metrics.get("precision", 0.0),
            recall=metrics.get("recall", 0.0),
            f1=metrics.get("f1", 0.0),
            matched=counts.get("matched", 0),
            total_extracted=counts.get("total_extracted", 0),
            total_reference=counts.get("total_reference", 0),
            claim_density_per_100_tokens=metrics.get("claim_density_per_100_tokens", 0.0),
            avg_prop_len_tokens=metrics.get("avg_prop_len_tokens", 0.0),
            dedup_rate=metrics.get("dedup_rate", 0.0),
            details=result["results"].get("details", {}),
            metadata={"evaluation_id": result["evaluation_id"], "evaluation_time": result.get("evaluation_time")}
        )
    
    except Exception as e:
        logger.error(f"Proposition evaluation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Proposition evaluation failed: {sanitize_error_message(e, 'proposition evaluation')}"
        )









# ============= Additional Run Endpoints =============

@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    user_id: str = Depends(verify_api_key)
):
    """Get run status and details"""
    try:
        run = await get_evaluation_service().get_run(run_id)
        if not run:
            raise create_error_response(
                message=f"Run {run_id} not found",
                error_type="not_found_error",
                param="run_id",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        return RunResponse(**run)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get run {run_id}: {e}")
        raise create_error_response(
            message=f"Failed to get run: {sanitize_error_message(e, 'retrieving run')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    user_id: str = Depends(verify_api_key)
):
    """Cancel a running evaluation"""
    try:
        success = await get_evaluation_service().cancel_run(run_id, cancelled_by=user_id)
        
        if success:
            return {"status": "cancelled", "id": run_id}
        else:
            raise create_error_response(
                message=f"Failed to cancel run {run_id}",
                error_type="server_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel run {run_id}: {e}")
        raise create_error_response(
            message=f"Failed to cancel run: {sanitize_error_message(e, 'cancelling run')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============= Batch Evaluation Endpoint =============

@router.post("/batch", response_model=BatchEvaluationResponse, dependencies=[Depends(check_evaluation_rate_limit)])
async def batch_evaluate(
    request: BatchEvaluationRequest,
    user_id: str = Depends(verify_api_key)
):
    """
    Run multiple evaluations in batch.
    
    Supports running multiple evaluation types with configurable parallelism.
    """
    # FIXME/TODO: Add per-user usage limits via user_rate_limiter to prevent abuse
    try:
        start_time = time.time()
        service = get_evaluation_service()
        
        results = []
        failed_count = 0
        
        # Process evaluations based on parallel setting (use parallel_workers > 1 as indicator)
        if request.parallel_workers > 1:
            # Run evaluations in parallel
            tasks = []
            for eval_request in request.items:
                eval_type = request.evaluation_type  # Type is at batch level
                
                if eval_type == "geval":
                    task = service.evaluate_geval(
                        source_text=eval_request.get("source_text", ""),
                        summary=eval_request.get("summary", ""),
                        metrics=eval_request.get("metrics", ["coherence"]),
                        api_name=eval_request.get("api_name", "openai"),
                        api_key=eval_request.get("api_key", "test_api_key"),
                        user_id=user_id
                    )
                elif eval_type == "rag":
                    task = service.evaluate_rag(
                        query=eval_request.get("query", ""),
                        contexts=eval_request.get("retrieved_contexts", []),
                        response=eval_request.get("generated_response", ""),
                        ground_truth=eval_request.get("ground_truth"),
                        metrics=eval_request.get("metrics", ["relevance", "faithfulness"]),
                        api_name=eval_request.get("api_name", "openai"),
                        user_id=user_id
                    )
                elif eval_type == "response_quality":
                    task = service.evaluate_response_quality(
                        prompt=eval_request.get("prompt", ""),
                        response=eval_request.get("response", ""),
                        expected_format=eval_request.get("expected_format"),
                        custom_criteria=eval_request.get("evaluation_criteria"),
                        api_name=eval_request.get("api_name", "openai"),
                        user_id=user_id
                    )
                elif eval_type == "ocr":
                    task = service.evaluate_ocr(
                        items=eval_request.get("items", []),
                        metrics=eval_request.get("metrics"),
                        ocr_options=eval_request.get("ocr_options"),
                        thresholds=eval_request.get("thresholds"),
                        user_id=user_id,
                    )
                else:
                    # Unknown type, create failed result
                    results.append({
                        "evaluation_id": None,
                        "status": "failed",
                        "error": f"Unknown evaluation type: {eval_type}"
                    })
                    failed_count += 1
                    continue
                
                if 'task' in locals():
                    tasks.append(task)
            
            # Wait for all tasks
            if tasks:
                task_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(task_results):
                    if isinstance(result, Exception):
                        results.append({
                            "evaluation_id": None,
                            "status": "failed",
                            "error": str(result)
                        })
                        failed_count += 1
                    else:
                        results.append({
                            "evaluation_id": result.get("evaluation_id"),
                            "status": "completed",
                            "results": result.get("results", {})
                        })
        else:
            # Run evaluations sequentially
            for eval_request in request.items:
                eval_type = request.evaluation_type  # Type is at batch level
                
                try:
                    if eval_type == "geval":
                        result = await service.evaluate_geval(
                            source_text=eval_request.get("source_text", ""),
                            summary=eval_request.get("summary", ""),
                            metrics=eval_request.get("metrics", ["coherence"]),
                            api_name=eval_request.get("api_name", "openai"),
                            api_key=eval_request.get("api_key", "test_api_key"),
                            user_id=user_id
                        )
                    elif eval_type == "rag":
                        result = await service.evaluate_rag(
                            query=eval_request.get("query", ""),
                            contexts=eval_request.get("retrieved_contexts", []),
                            response=eval_request.get("generated_response", ""),
                            ground_truth=eval_request.get("ground_truth"),
                            metrics=eval_request.get("metrics", ["relevance", "faithfulness"]),
                            api_name=eval_request.get("api_name", "openai"),
                            user_id=user_id
                        )
                    elif eval_type == "response_quality":
                        result = await service.evaluate_response_quality(
                            prompt=eval_request.get("prompt", ""),
                            response=eval_request.get("response", ""),
                            expected_format=eval_request.get("expected_format"),
                            custom_criteria=eval_request.get("evaluation_criteria"),
                            api_name=eval_request.get("api_name", "openai"),
                            user_id=user_id
                        )
                    elif eval_type == "ocr":
                        result = await service.evaluate_ocr(
                            items=eval_request.get("items", []),
                            metrics=eval_request.get("metrics"),
                            ocr_options=eval_request.get("ocr_options"),
                            thresholds=eval_request.get("thresholds"),
                            user_id=user_id,
                        )
                    else:
                        results.append({
                            "evaluation_id": None,
                            "status": "failed",
                            "error": f"Unknown evaluation type: {eval_type}"
                        })
                        failed_count += 1
                        continue
                    
                    results.append({
                        "evaluation_id": result.get("evaluation_id"),
                        "status": "completed",
                        "results": result.get("results", {})
                    })
                    
                except Exception as e:
                    results.append({
                        "evaluation_id": None,
                        "status": "failed",
                        "error": str(e)
                    })
                    failed_count += 1
                    
                    # Check continue_on_error setting (inverse logic)
                    if not request.continue_on_error:
                        break
        
        processing_time = time.time() - start_time
        
        return BatchEvaluationResponse(
            total_items=len(request.items),
            successful=len(results) - failed_count,
            failed=failed_count,
            results=results,
            aggregate_metrics={},  # TODO: Calculate aggregate metrics
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Batch evaluation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch evaluation failed: {sanitize_error_message(e, 'batch evaluation')}"
        )


# ============= OCR Evaluation Endpoint =============

from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import (
    OCREvaluationRequest,
    OCREvaluationResponse,
)


@router.post("/ocr", response_model=OCREvaluationResponse, dependencies=[Depends(check_evaluation_rate_limit)])
async def evaluate_ocr_endpoint(
    request: OCREvaluationRequest,
    user_id: str = Depends(verify_api_key)
):
    """Evaluate OCR effectiveness on provided items (text-to-text comparison).

    Note: This endpoint currently expects pre-extracted text per item.
    PDF-based OCR execution can be added in future if needed.
    """
    try:
        service = get_evaluation_service()
        result = await service.evaluate_ocr(
            items=[i.model_dump() for i in request.items],
            metrics=request.metrics,
            ocr_options=request.ocr_options,
            thresholds=request.thresholds,
            user_id=user_id,
        )
        return OCREvaluationResponse(**result)
    except Exception as e:
        logger.error(f"OCR evaluation endpoint failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR evaluation failed: {sanitize_error_message(e, 'ocr evaluation')}"
        )


@router.post("/ocr-pdf", response_model=OCREvaluationResponse, dependencies=[Depends(check_evaluation_rate_limit)])
async def evaluate_ocr_pdf_endpoint(
    files: List[UploadFile] = File(..., description="PDF files to OCR and evaluate"),
    ground_truths: Optional[List[str]] = Form(None, description="Ground-truth text per file (order aligned)"),
    ground_truths_json: Optional[str] = Form(None, description="JSON array of ground-truth texts aligned to files"),
    metrics: Optional[List[str]] = Form(None, description="Metrics to compute (cer, wer, coverage, page_coverage)"),
    ground_truths_pages_json: Optional[str] = Form(None, description="JSON array of per-file page arrays of ground truth text (e.g., [[...],[...]])"),
    thresholds_json: Optional[str] = Form(None, description="JSON dict of thresholds (max_cer, max_wer, min_coverage, min_page_coverage)"),
    enable_ocr: bool = Form(True, description="Enable OCR"),
    ocr_backend: Optional[str] = Form(None, description="OCR backend (e.g., 'tesseract' or 'auto')"),
    ocr_lang: str = Form("eng", description="OCR language"),
    ocr_dpi: int = Form(300, description="Render DPI (72-600)"),
    ocr_mode: str = Form("fallback", description="OCR mode: 'always' or 'fallback'"),
    ocr_min_page_text_chars: int = Form(40, description="Threshold for per-page OCR fallback"),
    user_id: str = Depends(verify_api_key),
):
    """Evaluate OCR by running OCR on uploaded PDFs and comparing to provided ground-truths."""
    try:
        if ground_truths is not None and len(ground_truths) not in (0, len(files)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ground_truths count must match files length or be omitted")

        items: List[Dict[str, Any]] = []
        gt_list = ground_truths or []
        if ground_truths_json:
            try:
                parsed = json.loads(ground_truths_json)
                if isinstance(parsed, list):
                    gt_list = parsed
            except Exception:
                pass

        gt_pages_list = None
        if ground_truths_pages_json:
            try:
                parsed_pages = json.loads(ground_truths_pages_json)
                if isinstance(parsed_pages, list):
                    gt_pages_list = parsed_pages
            except Exception:
                pass

        for idx, f in enumerate(files):
            content = await f.read()
            gt = gt_list[idx] if idx < len(gt_list) else None
            item = {
                "id": f.filename or f"file_{idx}",
                "pdf_bytes": content,
                "ground_truth_text": gt,
            }
            if gt_pages_list and idx < len(gt_pages_list) and isinstance(gt_pages_list[idx], list):
                item["ground_truth_pages"] = gt_pages_list[idx]
            items.append(item)

        ocr_options = {
            "enable_ocr": enable_ocr,
            "ocr_backend": ocr_backend,
            "ocr_lang": ocr_lang,
            "ocr_dpi": int(ocr_dpi),
            "ocr_mode": ocr_mode,
            "ocr_min_page_text_chars": int(ocr_min_page_text_chars),
        }

        service = get_evaluation_service()
        thresholds = None
        if thresholds_json:
            try:
                thresholds = json.loads(thresholds_json)
            except Exception:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid thresholds_json")
        result = await service.evaluate_ocr(
            items=items,
            metrics=metrics,
            ocr_options=ocr_options,
            thresholds=thresholds,
            user_id=user_id,
        )
        return OCREvaluationResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR PDF evaluation endpoint failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR PDF evaluation failed: {sanitize_error_message(e, 'ocr pdf evaluation')}"
        )


# ============= Evaluation History Endpoint =============

@router.post("/history", response_model=EvaluationHistoryResponse)
async def get_evaluation_history(
    request: EvaluationHistoryRequest,
    user_id: str = Depends(verify_api_key)
):
    """
    Retrieve evaluation history for a user.
    
    Supports filtering by date range, evaluation type, and pagination.
    """
    try:
        service = get_evaluation_service()
        
        # Get evaluations from database
        evaluations = await service.get_evaluation_history(
            user_id=request.user_id or user_id,
            evaluation_type=request.evaluation_type,
            start_date=request.start_date,
            end_date=request.end_date,
            limit=request.limit or 100,
            offset=request.offset or 0
        )
        
        # Get total count for pagination
        total_count = await service.count_evaluations(
            user_id=request.user_id or user_id,
            evaluation_type=request.evaluation_type,
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        return EvaluationHistoryResponse(
            items=evaluations,
            total_count=total_count,
            aggregations={
                "limit": request.limit or 100,
                "offset": request.offset or 0,
                "filtered_by": {
                    "user_id": request.user_id or user_id,
                    "evaluation_type": request.evaluation_type,
                    "date_range": {
                        "start": request.start_date.isoformat() if request.start_date else None,
                        "end": request.end_date.isoformat() if request.end_date else None
                    }
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to retrieve evaluation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve history: {sanitize_error_message(e, 'retrieving history')}"
        )
