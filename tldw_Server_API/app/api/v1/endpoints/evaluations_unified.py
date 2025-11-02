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
from fastapi.routing import APIRoute
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
    get_unified_evaluation_service_for_user,
    UnifiedEvaluationService
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Evaluations.webhook_manager import WebhookManager, WebhookEvent
from tldw_Server_API.app.core.RAG.rag_service.vector_stores import VectorStoreFactory

# Import auth and rate limiting
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.exceptions import InvalidTokenError, TokenExpiredError
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter, get_rate_limiter
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_rate_limiter_dep

# Import additional services
from tldw_Server_API.app.core.Evaluations.user_rate_limiter import get_user_rate_limiter_for_user
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
from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode

# Create router
router = APIRouter(prefix="/evaluations", tags=["evaluations"])

# Security
security = HTTPBearer(auto_error=False)

_webhook_managers: dict = {}
_wm_lock = None

from .evaluations_auth import (
    verify_api_key,
    sanitize_error_message,
    create_error_response,
    check_evaluation_rate_limit,
    _apply_rate_limit_headers,
    require_admin,
)
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope

def _get_webhook_manager_for_user(user_id: int) -> WebhookManager:
    global _wm_lock
    if _wm_lock is None:
        import threading as _threading
        _wm_lock = _threading.Lock()
    with _wm_lock:
        mgr = _webhook_managers.get(user_id)
        import os as _os
        _override_db = _os.getenv("EVALUATIONS_TEST_DB_PATH")
        if mgr is not None and _override_db:
            try:
                cfg = getattr(getattr(mgr, "db_adapter", None), "config", None)
                current_conn = getattr(cfg, "connection_string", None)
                if current_conn and current_conn != _override_db:
                    mgr = WebhookManager(db_path=_override_db)
                    _webhook_managers[user_id] = mgr
            except Exception:
                pass
        if mgr is None:
            db_path = _override_db or str(DatabasePaths.get_evaluations_db_path(user_id))
            mgr = WebhookManager(db_path=db_path)
            _webhook_managers[user_id] = mgr
    return mgr

def get_db_for_user(user_id: int):
    svc = get_unified_evaluation_service_for_user(user_id)
    return getattr(svc, 'db', None)


# verify_api_key et al. imported from evaluations_auth


@router.post("/admin/idempotency/cleanup")
async def admin_cleanup_idempotency(
    ttl_hours: int = Query(72, ge=1, le=720, description="Delete idempotency keys older than this TTL (hours)"),
    target_user_id: Optional[int] = Query(None, description="If provided, only clean this user's evaluations DB"),
    user_ctx: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """Admin-only: purge stale idempotency keys in Evaluations DBs on-demand.

    Returns a summary of deleted rows per user and total.
    """
    # Admin gate
    require_admin(current_user)
    try:
        from pathlib import Path as _Path
        from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths as _DP
        from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase as _EDB

        deleted_total = 0
        details = []

        # Build candidate user ids
        candidate_ids = set()
        if target_user_id is not None:
            candidate_ids.add(int(target_user_id))
        else:
            try:
                candidate_ids.add(int(_DP.get_single_user_id()))
            except Exception:
                pass
            try:
                base = _Path(_DP.get_user_base_directory(_DP.get_single_user_id())).parent
                if base.exists():
                    for entry in base.iterdir():
                        if entry.is_dir():
                            try:
                                candidate_ids.add(int(entry.name))
                            except Exception:
                                continue
            except Exception:
                pass

        for uid in sorted(candidate_ids):
            try:
                db_path = _DP.get_evaluations_db_path(uid)
                if not db_path.exists():
                    continue
                db = _EDB(str(db_path))
                deleted = db.cleanup_idempotency_keys(ttl_hours=int(ttl_hours))
                deleted_total += int(deleted)
                details.append({"user_id": uid, "deleted": int(deleted)})
            except Exception:
                continue

        return {"deleted_total": deleted_total, "details": details}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin idempotency cleanup failed: {e}")
        raise HTTPException(status_code=500, detail="Idempotency cleanup failed")


def _estimate_tokens_from_texts(*texts: Optional[str], provider: Optional[str] = None, model: Optional[str] = None) -> int:
    """Estimate tokens with provider/model hints when available.

    Preference order when tiktoken is available:
    1) encoding_for_model(model) if model provided and recognized
    2) Heuristic by model name -> o200k_base for 4o/4.1/o1 families
    3) cl100k_base as a general default

    Falls back to chars/4 if tiktoken or encoding lookup is unavailable.
    """
    try:
        import tiktoken  # type: ignore
        enc = None

        # Try exact model mapping first (OpenAI models)
        if isinstance(model, str) and model:
            try:
                enc = tiktoken.encoding_for_model(model)
            except Exception:
                enc = None

        # Heuristic for modern OpenAI models when model hint exists
        if enc is None and isinstance(model, str):
            m = model.lower()
            try:
                if ("gpt-4o" in m) or ("gpt-4.1" in m) or m.startswith("o1"):
                    enc = tiktoken.get_encoding("o200k_base")
            except Exception:
                enc = None

        # Provider fallback (OpenAI -> cl100k_base)
        if enc is None and isinstance(provider, str) and provider.lower() == "openai":
            try:
                enc = tiktoken.get_encoding("cl100k_base")
            except Exception:
                enc = None

        # Final default
        if enc is None:
            try:
                enc = tiktoken.get_encoding("cl100k_base")
            except Exception:
                enc = None

        if enc is not None:
            total = 0
            for t in texts:
                if isinstance(t, str) and t:
                    total += len(enc.encode(t))
            return total
    except Exception:
        pass

    # Fallback: character-based approximation
    total_chars = 0
    for t in texts:
        if isinstance(t, str):
            total_chars += len(t)
    return max(0, total_chars // 4)


async def _apply_rate_limit_headers(limiter, user_id: str, response: Response, meta: Optional[Dict[str, Any]] = None) -> None:
    """Fetch usage summary and set standard X-RateLimit-* headers."""
    try:
        summary = await limiter.get_usage_summary(user_id)
        limits = summary.get("limits", {})
        usage = summary.get("usage", {})
        remaining = summary.get("remaining", {})
        # Tier
        response.headers["X-RateLimit-Tier"] = str(summary.get("tier", "free"))
        # Per-minute (evaluations)
        pm = limits.get("per_minute", {})
        per_min_limit = int(pm.get("evaluations", 0) or 0)
        response.headers["X-RateLimit-PerMinute-Limit"] = str(per_min_limit)
        # Per-minute remaining: prefer value from prior check; otherwise default to 0
        try:
            remaining_requests = None
            if meta and isinstance(meta, dict):
                remaining_requests = meta.get("requests_remaining")
            if remaining_requests is None:
                # If not provided by limiter, include header with a safe default
                remaining_requests = 0
            response.headers["X-RateLimit-PerMinute-Remaining"] = str(int(remaining_requests or 0))
        except Exception:
            response.headers["X-RateLimit-PerMinute-Remaining"] = "0"
        # Daily quotas
        daily = limits.get("daily", {})
        response.headers["X-RateLimit-Daily-Limit"] = str(daily.get("evaluations", 0))
        response.headers["X-RateLimit-Daily-Remaining"] = str(remaining.get("daily_evaluations", 0))
        response.headers["X-RateLimit-Tokens-Remaining"] = str(remaining.get("daily_tokens", 0))
        # Cost quotas (optional)
        response.headers["X-RateLimit-Daily-Cost-Remaining"] = f"{remaining.get('daily_cost', 0):.2f}"
        response.headers["X-RateLimit-Monthly-Cost-Remaining"] = f"{remaining.get('monthly_cost', 0):.2f}"
        # Baseline RateLimit-* headers (simple minute window approximation)
        try:
            response.headers["RateLimit-Limit"] = str(per_min_limit)
            if meta and isinstance(meta, dict) and "requests_remaining" in meta:
                response.headers["RateLimit-Remaining"] = str(int(meta.get("requests_remaining") or 0))
            reset_val = 60
            if meta and isinstance(meta, dict) and "reset_seconds" in meta:
                reset_val = int(meta.get("reset_seconds") or 60)
            response.headers["RateLimit-Reset"] = str(reset_val)
            # X- header parity for reset seconds
            response.headers["X-RateLimit-Reset"] = str(reset_val)
        except Exception:
            pass
    except Exception:
        # Non-fatal
        pass


# ============= Authentication =============

# (definition moved earlier to satisfy Depends references)
def _verify_api_key_placeholder():
    """
    Placeholder to maintain file structure; actual verify_api_key is defined above.
    """


# Note: verify_api_key is defined once above. Keep a single definition to avoid confusion.


@router.post("/admin/idempotency/cleanup")
async def admin_cleanup_idempotency(
    ttl_hours: int = Query(72, ge=1, le=720, description="Delete idempotency keys older than this TTL (hours)"),
    target_user_id: Optional[int] = Query(None, description="If provided, only clean this user's evaluations DB"),
    user_ctx: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """Admin-only: purge stale idempotency keys in Evaluations DBs on-demand.

    Returns a summary of deleted rows per user and total.
    """
    # Admin gate
    require_admin(current_user)
    try:
        from pathlib import Path as _Path
        from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths as _DP
        from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase as _EDB

        deleted_total = 0
        details = []

        # Build candidate user ids
        candidate_ids = set()
        if target_user_id is not None:
            candidate_ids.add(int(target_user_id))
        else:
            try:
                candidate_ids.add(int(_DP.get_single_user_id()))
            except Exception:
                pass
            try:
                base = _Path(_DP.get_user_base_directory(_DP.get_single_user_id())).parent
                if base.exists():
                    for entry in base.iterdir():
                        if entry.is_dir():
                            try:
                                candidate_ids.add(int(entry.name))
                            except Exception:
                                continue
            except Exception:
                pass

        for uid in sorted(candidate_ids):
            try:
                db_path = _DP.get_evaluations_db_path(uid)
                if not db_path.exists():
                    continue
                db = _EDB(str(db_path))
                deleted = db.cleanup_idempotency_keys(ttl_hours=int(ttl_hours))
                deleted_total += int(deleted)
                details.append({"user_id": uid, "deleted": int(deleted)})
            except Exception:
                continue

        return {"deleted_total": deleted_total, "details": details}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin idempotency cleanup failed: {e}")
        raise HTTPException(status_code=500, detail="Idempotency cleanup failed")


def _estimate_tokens_from_texts(*texts: Optional[str], provider: Optional[str] = None, model: Optional[str] = None) -> int:
    """Estimate tokens with provider/model hints when available.

    Preference order when tiktoken is available:
    1) encoding_for_model(model) if model provided and recognized
    2) Heuristic by model name -> o200k_base for 4o/4.1/o1 families
    3) cl100k_base as a general default

    Falls back to chars/4 if tiktoken or encoding lookup is unavailable.
    """
    try:
        import tiktoken  # type: ignore
        enc = None

        # Try exact model mapping first (OpenAI models)
        if isinstance(model, str) and model:
            try:
                enc = tiktoken.encoding_for_model(model)
            except Exception:
                enc = None

        # Heuristic for modern OpenAI models when model hint exists
        if enc is None and isinstance(model, str):
            m = model.lower()
            try:
                if ("gpt-4o" in m) or ("gpt-4.1" in m) or m.startswith("o1"):
                    enc = tiktoken.get_encoding("o200k_base")
            except Exception:
                enc = None

        # Provider fallback (OpenAI -> cl100k_base)
        if enc is None and isinstance(provider, str) and provider.lower() == "openai":
            try:
                enc = tiktoken.get_encoding("cl100k_base")
            except Exception:
                enc = None

        # Final default
        if enc is None:
            try:
                enc = tiktoken.get_encoding("cl100k_base")
            except Exception:
                enc = None

        if enc is not None:
            total = 0
            for t in texts:
                if isinstance(t, str) and t:
                    total += len(enc.encode(t))
            return total
    except Exception:
        pass

    # Fallback: character-based approximation
    total_chars = 0
    for t in texts:
        if isinstance(t, str):
            total_chars += len(t)
    return max(0, total_chars // 4)


async def _apply_rate_limit_headers(limiter, user_id: str, response: Response, meta: Optional[Dict[str, Any]] = None) -> None:
    """Fetch usage summary and set standard X-RateLimit-* headers."""
    try:
        summary = await limiter.get_usage_summary(user_id)
        limits = summary.get("limits", {})
        usage = summary.get("usage", {})
        remaining = summary.get("remaining", {})
        # Tier
        response.headers["X-RateLimit-Tier"] = str(summary.get("tier", "free"))
        # Per-minute (evaluations)
        pm = limits.get("per_minute", {})
        per_min_limit = int(pm.get("evaluations", 0) or 0)
        response.headers["X-RateLimit-PerMinute-Limit"] = str(per_min_limit)
        # Per-minute remaining: prefer value from prior check; otherwise default to 0
        try:
            remaining_requests = None
            if meta and isinstance(meta, dict):
                remaining_requests = meta.get("requests_remaining")
            if remaining_requests is None:
                # If not provided by limiter, include header with a safe default
                remaining_requests = 0
            response.headers["X-RateLimit-PerMinute-Remaining"] = str(int(remaining_requests or 0))
        except Exception:
            response.headers["X-RateLimit-PerMinute-Remaining"] = "0"
        # Daily quotas
        daily = limits.get("daily", {})
        response.headers["X-RateLimit-Daily-Limit"] = str(daily.get("evaluations", 0))
        response.headers["X-RateLimit-Daily-Remaining"] = str(remaining.get("daily_evaluations", 0))
        response.headers["X-RateLimit-Tokens-Remaining"] = str(remaining.get("daily_tokens", 0))
        # Cost quotas (optional)
        response.headers["X-RateLimit-Daily-Cost-Remaining"] = f"{remaining.get('daily_cost', 0):.2f}"
        response.headers["X-RateLimit-Monthly-Cost-Remaining"] = f"{remaining.get('monthly_cost', 0):.2f}"
        # Baseline RateLimit-* headers (simple minute window approximation)
        try:
            response.headers["RateLimit-Limit"] = str(per_min_limit)
            if meta and isinstance(meta, dict) and "requests_remaining" in meta:
                response.headers["RateLimit-Remaining"] = str(int(meta.get("requests_remaining") or 0))
            reset_val = 60
            if meta and isinstance(meta, dict) and "reset_seconds" in meta:
                reset_val = int(meta.get("reset_seconds") or 60)
            response.headers["RateLimit-Reset"] = str(reset_val)
            # X- header parity for reset seconds
            response.headers["X-RateLimit-Reset"] = str(reset_val)
        except Exception:
            pass
    except Exception:
        # Non-fatal
        pass


# ============= Authentication =============

# (definition moved earlier to satisfy Depends references)
def _verify_api_key_placeholder():
    """
    Placeholder to maintain file structure; actual verify_api_key is defined above.
    """


# ============= Rate Limiting =============

# check_evaluation_rate_limit imported


# ============= Error Handling =============

"""Auth and error helpers imported from evaluations_auth."""


# create_error_response imported


"""Admin checker imported"""


from .evaluations_embeddings_abtest import abtest_router
router.include_router(abtest_router)


@router.get("/embeddings/abtest/{test_id}/events")
async def stream_embeddings_abtest_events(
    test_id: str,
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
    current_user: User = Depends(get_request_user),
):
    """SSE stream of progress and updates for an A/B test."""
    from fastapi.responses import StreamingResponse
    import asyncio as _aio
    import json as _json
    svc = get_unified_evaluation_service_for_user(current_user.id)

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
    current_user: User = Depends(get_request_user),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Cancel/cleanup an embeddings A/B test (stub)."""
    # Idempotency: if prior mapping exists, return canonical response without side effects
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        if idempotency_key:
            prior = svc.db.lookup_idempotency("emb_abtest_delete", idempotency_key, user_ctx)
            if prior:
                logger.info(f"A/B test delete idempotent hit: {test_id}")
                return Response(content=json.dumps({"status": "deleted", "test_id": test_id}), media_type='application/json', headers={"X-Idempotent-Replay": "true", "Idempotency-Key": idempotency_key})
    except Exception:
        pass

    # Perform delete/cleanup (stubbed)
    logger.info(f"A/B test deleted: {test_id} by {user_ctx}")
    try:
        if idempotency_key:
            svc.db.record_idempotency("emb_abtest_delete", idempotency_key, test_id, user_ctx)
    except Exception:
        pass
    return {"status": "deleted", "test_id": test_id}


@router.get("/embeddings/abtest/{test_id}/export")
async def export_embeddings_abtest(
    test_id: str,
    format: str = Query("json", pattern="^(json|csv)$"),
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
    current_user: User = Depends(get_request_user),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Export AB test results (JSON or CSV). Admin-only."""
    require_admin(current_user)
    svc = get_unified_evaluation_service_for_user(current_user.id)
    rows, total = svc.db.list_abtest_results(test_id, limit=100000, offset=0)
    if format == 'json':
        # Idempotency: record export mapping (best-effort)
        try:
            if idempotency_key:
                svc.db.record_idempotency("emb_abtest_export_json", idempotency_key, f"{test_id}:json", user_ctx)
        except Exception:
            pass
        headers = {}
        if idempotency_key:
            headers = {"Idempotency-Key": idempotency_key}
        return Response(content=json.dumps({"test_id": test_id, "total": total, "results": rows}), media_type='application/json', headers=headers)
    # CSV
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["result_id", "arm_id", "query_id", "ranked_ids", "latency_ms", "metrics_json"])
    for r in rows:
        writer.writerow([r.get('result_id'), r.get('arm_id'), r.get('query_id'), r.get('ranked_ids'), r.get('latency_ms'), r.get('metrics_json')])
    try:
        if idempotency_key:
            svc.db.record_idempotency("emb_abtest_export_csv", idempotency_key, f"{test_id}:csv", user_ctx)
    except Exception:
        pass
    headers = {"Content-Disposition": f"attachment; filename=abtest_{test_id}.csv"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return Response(content=output.getvalue(), media_type='text/csv', headers=headers)


# ============= OpenAI-Compatible Evaluation Endpoints =============

# Moved: CRUD create/list to evaluations_crud.py


# ============= Rate Limit Management =============

@router.get("/rate-limits", response_model=RateLimitStatusResponse)
async def get_rate_limit_status(
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """Get current rate limit status for the authenticated user"""
    try:
        limiter = get_user_rate_limiter_for_user(current_user.id)
        summary = await limiter.get_usage_summary(user_id)

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


from .evaluations_rag_pipeline import pipeline_router
from .evaluations_datasets import datasets_router, _normalize_dataset_payload
from .evaluations_webhooks import webhooks_router
from .evaluations_crud import crud_router
router.include_router(pipeline_router)
router.include_router(datasets_router)
router.include_router(webhooks_router)
router.include_router(crud_router)

@router.post("/datasets", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    dataset_request: CreateDatasetRequest,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    response: Response = None,
):
    """Create a new dataset"""
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)

        # Idempotency: reuse if mapping exists
        if idempotency_key:
            try:
                existing_id = svc.db.lookup_idempotency("dataset", idempotency_key, user_id)
                if existing_id:
                    existing = await svc.get_dataset(existing_id)
                    if existing:
                        try:
                            if response is not None:
                                response.headers["X-Idempotent-Replay"] = "true"
                                response.headers["Idempotency-Key"] = idempotency_key
                        except Exception:
                            pass
                        return DatasetResponse(**_normalize_dataset_payload(existing))
            except Exception:
                pass
        dataset_id = await svc.create_dataset(
            name=dataset_request.name,
            description=dataset_request.description,
            samples=[model_dump_compat(s) for s in dataset_request.samples],
            metadata=model_dump_compat(dataset_request.metadata) if dataset_request.metadata else None,
            created_by=user_id
        )

        dataset = await svc.get_dataset(dataset_id)
        if not dataset:
            raise ValueError("Failed to retrieve created dataset")
        dataset = _normalize_dataset_payload(dataset)

        # Record idempotency mapping
        try:
            if idempotency_key:
                svc.db.record_idempotency("dataset", idempotency_key, dataset_id, user_id)
        except Exception:
            pass

        return DatasetResponse(**dataset)

    except Exception as e:
        logger.exception(f"Failed to create dataset: {e}")
        raise create_error_response(
            message=f"Failed to create dataset: {sanitize_error_message(e, 'creating dataset')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/datasets", response_model=DatasetListResponse)
async def list_datasets(
    limit: int = Query(20, ge=1, le=100),
    after: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """List datasets with pagination"""
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        datasets, has_more = await svc.list_datasets(
            limit=limit,
            after=after,
            offset=offset
        )

        first_id = datasets[0]["id"] if datasets else None
        last_id = datasets[-1]["id"] if datasets else None

        normalized = [_normalize_dataset_payload(ds) for ds in datasets]
        return DatasetListResponse(
            object="list",
            data=[DatasetResponse(**ds) for ds in normalized],
            has_more=has_more,
            first_id=first_id,
            last_id=last_id,
            total=len(normalized)
        )

    except Exception as e:
        logger.exception(f"Failed to list datasets: {e}")
        raise create_error_response(
            message=f"Failed to list datasets: {sanitize_error_message(e, 'listing datasets')}",
            error_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """Get dataset by ID"""
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        dataset = await svc.get_dataset(dataset_id)
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
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """Delete a dataset"""
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        success = await svc.delete_dataset(dataset_id, deleted_by=user_id)
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
    logger.warning("Evaluations health endpoint invoked")
    try:
        # Default to single-user instance for health when no auth context
        from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths as _DP
        uid = _DP.get_single_user_id()
        svc = get_unified_evaluation_service_for_user(uid)
        health = await svc.health_check()
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
        from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths as _DP
        uid = _DP.get_single_user_id()
        svc = get_unified_evaluation_service_for_user(uid)
        metrics_summary = await svc.get_metrics_summary()

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


"""Webhook endpoints moved to evaluations_webhooks module."""


@router.get("/{eval_id}", response_model=EvaluationResponse)
async def get_evaluation(
    eval_id: str,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """Get evaluation by ID"""
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        evaluation = await svc.get_evaluation(eval_id)
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
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """Update evaluation definition"""
    try:
        updates = model_dump_compat(update_request, exclude_unset=True)
        if not updates:
            raise create_error_response(
                message="No updates provided",
                error_type="invalid_request_error"
            )

        svc = get_unified_evaluation_service_for_user(current_user.id)
        success = await svc.update_evaluation(
            eval_id, updates, updated_by=user_id
        )

        if not success:
            raise create_error_response(
                message=f"Evaluation {eval_id} not found",
                error_type="not_found_error",
                param="eval_id",
                status_code=status.HTTP_404_NOT_FOUND
            )

        evaluation = await svc.get_evaluation(eval_id)
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
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """Delete an evaluation"""
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        success = await svc.delete_evaluation(eval_id, deleted_by=user_id)
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

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope


@router.post(
    "/{eval_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_run(
    eval_id: str,
    run_request: CreateRunRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
    __: None = Depends(require_token_scope("workflows", require_if_present=True, require_schedule_match=False, allow_admin_bypass=True, endpoint_id="evals.create_run", count_as="run")),
    current_user: User = Depends(get_request_user),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    response: Response = None,
):
    """Create and start an evaluation run"""
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        # Idempotency: return existing run if key provided
        if idempotency_key:
            try:
                existing_id = svc.db.lookup_idempotency("run", idempotency_key, user_id)
                if existing_id:
                    existing = await svc.get_run(existing_id)
                    if existing:
                        try:
                            if response is not None:
                                response.headers["X-Idempotent-Replay"] = "true"
                                response.headers["Idempotency-Key"] = idempotency_key
                        except Exception:
                            pass
                        return RunResponse(**existing)
            except Exception:
                pass
        run = await svc.create_run(
            eval_id=eval_id,
            target_model=run_request.target_model,
            config=model_dump_compat(run_request.config) if run_request.config else None,
            dataset_override=model_dump_compat(run_request.dataset_override) if run_request.dataset_override else None,
            webhook_url=str(run_request.webhook_url) if run_request.webhook_url else None,
            created_by=user_id
        )
        # Record idempotency mapping
        try:
            if idempotency_key and run.get("id"):
                svc.db.record_idempotency("run", idempotency_key, run["id"], user_id)
        except Exception:
            pass

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
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """List runs for an evaluation"""
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        runs, has_more = await svc.list_runs(
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
    response: Response,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """
    Evaluate a summary using G-Eval metrics.

    G-Eval evaluates summaries on fluency, consistency, relevance, and coherence.
    """
    try:
        # Per-user usage limits
        limiter = get_user_rate_limiter_for_user(current_user.id)
        tokens_est = _estimate_tokens_from_texts(
            request.source_text,
            request.summary,
            provider=getattr(request, "api_name", None),
            model=None,
        )
        allowed, meta = await limiter.check_rate_limit(user_id, endpoint="evals:geval", is_batch=False, tokens_requested=tokens_est, estimated_cost=0.0)
        if not allowed:
            retry_after = meta.get("retry_after", 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=meta.get("error", "Rate limit exceeded"),
                headers={"Retry-After": str(retry_after)}
            )
        # Normalize user id for single-user mode to match webhook registrations
        try:
            from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings
            _settings = _get_settings()
            # In single-user mode, always use the fixed ID so webhook registrations align
            if getattr(_settings, "AUTH_MODE", "single_user") == "single_user":
                effective_user_id = str(_settings.SINGLE_USER_FIXED_ID)
            else:
                effective_user_id = user_id
        except Exception:
            effective_user_id = user_id

        # Send webhook: evaluation started (await in TEST_MODE)
        import os as _os
        import asyncio as _asyncio
        import time as _time
        wm = _get_webhook_manager_for_user(current_user.id)
        start_event_id = f"geval_{int(_time.time())}_{effective_user_id[:8]}"
        if _os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes"):
            await wm.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_STARTED,
                evaluation_id=start_event_id,
                data={
                    "evaluation_type": "geval",
                    "api_name": request.api_name
                }
            )
        else:
            _asyncio.create_task(wm.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_STARTED,
                evaluation_id=start_event_id,
                data={
                    "evaluation_type": "geval",
                    "api_name": request.api_name
                }
            ))
        svc = get_unified_evaluation_service_for_user(current_user.id)
        result = await svc.evaluate_geval(
            source_text=request.source_text,
            summary=request.summary,
            metrics=request.metrics,
            api_name=request.api_name,
            api_key=request.api_key,
            user_id=effective_user_id
        )
        # If provider returned actual usage, record it
        try:
            usage = result.get("usage") if isinstance(result, dict) else None
            if usage and isinstance(usage, dict):
                await limiter.record_actual_usage(user_id, "evals:geval", int(usage.get("total_tokens", 0)), float(usage.get("cost", 0.0) or 0.0))
        except Exception:
            pass

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
            await wm.send_webhook(
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
            _asyncio.create_task(wm.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_COMPLETED,
                evaluation_id=result["evaluation_id"],
                data={
                    "evaluation_type": "geval",
                    "average_score": result["results"].get("average_score", 0.0),
                    "processing_time": result.get("evaluation_time", 0.0)
                }
            ))

        # Normalize average score to 0-1 if provided on 1-5 scale
        _avg_raw = result["results"].get("average_score", 0.0)
        try:
            _avg_val = float(_avg_raw)
        except (TypeError, ValueError):
            _avg_val = 0.0
        _avg_norm = (_avg_val / 5.0) if _avg_val > 1.0 else _avg_val

        resp_payload = GEvalResponse(
            metrics=formatted_metrics,
            average_score=_avg_norm,
            summary_assessment=result["results"].get("assessment", "Evaluation complete"),
            evaluation_time=result["evaluation_time"],
            metadata={"evaluation_id": result["evaluation_id"]}
        )
        try:
            if response is not None:
                await _apply_rate_limit_headers(limiter, user_id, response, meta)
        except Exception:
            pass
        return resp_payload

    except Exception as e:
        # Log with stack trace for diagnostics
        logger.exception(f"G-Eval evaluation failed: {e}")
        # In TEST_MODE, surface a slightly more verbose message to aid debugging
        _detail = f"Evaluation failed: {sanitize_error_message(e, 'G-Eval evaluation')}"
        try:
            import os as _os
            if _os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes"):
                _detail = _detail + f" (debug: {str(e)})"
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_detail
        )


@router.post("/rag", response_model=RAGEvaluationResponse, dependencies=[Depends(check_evaluation_rate_limit)])
async def evaluate_rag(
    request: RAGEvaluationRequest,
    response: Response,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """
    Evaluate RAG system performance.

    Evaluates relevance, faithfulness, answer similarity, and context precision.
    """
    try:
        # Per-user usage limits
        limiter = get_user_rate_limiter_for_user(current_user.id)
        tokens_est = _estimate_tokens_from_texts(
            request.query,
            "\n".join(request.retrieved_contexts or []),
            request.generated_response,
            request.ground_truth,
            provider=getattr(request, "api_name", None),
            model=None,
        )
        allowed, meta = await limiter.check_rate_limit(user_id, endpoint="evals:rag", is_batch=False, tokens_requested=tokens_est, estimated_cost=0.0)
        if not allowed:
            retry_after = meta.get("retry_after", 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=meta.get("error", "Rate limit exceeded"),
                headers={"Retry-After": str(retry_after)}
            )
        # Normalize user id for single-user mode to match webhook registrations
        try:
            from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings
            _settings = _get_settings()
            if getattr(_settings, "AUTH_MODE", "single_user") == "single_user":
                effective_user_id = str(_settings.SINGLE_USER_FIXED_ID)
            else:
                effective_user_id = user_id
        except Exception:
            effective_user_id = user_id

        # Send webhook: evaluation started (await in TEST_MODE)
        import os as _os
        import asyncio as _asyncio
        wm = _get_webhook_manager_for_user(current_user.id)
        import time as _time
        start_event_id = f"rag_{int(_time.time())}_{effective_user_id[:8]}"
        if _os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes"):
            await wm.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_STARTED,
                evaluation_id=start_event_id,
                data={
                    "evaluation_type": "rag",
                    "api_name": request.api_name
                }
            )
        else:
            _asyncio.create_task(wm.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_STARTED,
                evaluation_id=start_event_id,
                data={
                    "evaluation_type": "rag",
                    "api_name": request.api_name
                }
            ))
        svc = get_unified_evaluation_service_for_user(current_user.id)
        result = await svc.evaluate_rag(
            query=request.query,
            contexts=request.retrieved_contexts,
            response=request.generated_response,
            ground_truth=request.ground_truth,
            metrics=request.metrics,
            api_name=request.api_name,
            user_id=effective_user_id
        )
        try:
            usage = result.get("usage") if isinstance(result, dict) else None
            if usage and isinstance(usage, dict):
                await limiter.record_actual_usage(user_id, "evals:rag", int(usage.get("total_tokens", 0)), float(usage.get("cost", 0.0) or 0.0))
        except Exception:
            pass

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
            await wm.send_webhook(
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
            _asyncio.create_task(wm.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_COMPLETED,
                evaluation_id=result["evaluation_id"],
                data={
                    "evaluation_type": "rag",
                    "overall_score": result["results"].get("overall_score", 0.0),
                    "processing_time": result.get("evaluation_time", 0.0)
                }
            ))

        resp_payload = RAGEvaluationResponse(
            metrics=formatted_metrics,
            overall_score=result["results"].get("overall_score", 0.0),
            retrieval_quality=result["results"].get("retrieval_quality", 0.0),
            generation_quality=result["results"].get("generation_quality", 0.0),
            suggestions=result["results"].get("suggestions", []),
            metadata={"evaluation_id": result["evaluation_id"]}
        )
        try:
            if response is not None:
                await _apply_rate_limit_headers(limiter, user_id, response, meta)
        except Exception:
            pass
        return resp_payload

    except Exception as e:
        logger.error(f"RAG evaluation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG evaluation failed: {sanitize_error_message(e, 'RAG evaluation')}"
        )


@router.post("/response-quality", response_model=ResponseQualityResponse, dependencies=[Depends(check_evaluation_rate_limit)])
async def evaluate_response_quality(
    request: ResponseQualityRequest,
    response: Response,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """
    Evaluate the quality of a generated response.

    Checks relevance, completeness, accuracy, and format compliance.
    """
    try:
        # Per-user usage limits
        limiter = get_user_rate_limiter_for_user(current_user.id)
        tokens_est = _estimate_tokens_from_texts(
            request.prompt,
            request.response,
            request.expected_format,
            provider=getattr(request, "api_name", None),
            model=None,
        )
        allowed, meta = await limiter.check_rate_limit(user_id, endpoint="evals:response_quality", is_batch=False, tokens_requested=tokens_est, estimated_cost=0.0)
        if not allowed:
            retry_after = meta.get("retry_after", 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=meta.get("error", "Rate limit exceeded"),
                headers={"Retry-After": str(retry_after)}
            )
        # Normalize user id for single-user mode to match webhook registrations
        try:
            from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings
            _settings = _get_settings()
            if getattr(_settings, "AUTH_MODE", "single_user") == "single_user":
                effective_user_id = str(_settings.SINGLE_USER_FIXED_ID)
            else:
                effective_user_id = user_id
        except Exception:
            effective_user_id = user_id

        # Send webhook: evaluation started (await in TEST_MODE)
        import os as _os
        import asyncio as _asyncio
        wm = _get_webhook_manager_for_user(current_user.id)
        import time as _time
        start_event_id = f"response_quality_{int(_time.time())}_{effective_user_id[:8]}"
        if _os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes"):
            await wm.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_STARTED,
                evaluation_id=start_event_id,
                data={
                    "evaluation_type": "response_quality",
                    "api_name": request.api_name
                }
            )
        else:
            _asyncio.create_task(wm.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_STARTED,
                evaluation_id=start_event_id,
                data={
                    "evaluation_type": "response_quality",
                    "api_name": request.api_name
                }
            ))

        svc = get_unified_evaluation_service_for_user(current_user.id)
        result = await svc.evaluate_response_quality(
            prompt=request.prompt,
            response=request.response,
            expected_format=request.expected_format,
            custom_criteria=request.evaluation_criteria,
            api_name=request.api_name,
            user_id=effective_user_id
        )
        try:
            usage = result.get("usage") if isinstance(result, dict) else None
            if usage and isinstance(usage, dict):
                await limiter.record_actual_usage(user_id, "evals:response_quality", int(usage.get("total_tokens", 0)), float(usage.get("cost", 0.0) or 0.0))
        except Exception:
            pass

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
            await wm.send_webhook(
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
            _asyncio.create_task(wm.send_webhook(
                user_id=effective_user_id,
                event=WebhookEvent.EVALUATION_COMPLETED,
                evaluation_id=result["evaluation_id"],
                data={
                    "evaluation_type": "response_quality",
                    "overall_quality": result["results"].get("overall_quality", 0.0),
                    "processing_time": result.get("evaluation_time", 0.0)
                }
            ))

        resp_payload = ResponseQualityResponse(
            metrics=metrics,
            overall_quality=result["results"].get("overall_quality", 0.0),
            format_compliance=format_compliance,
            issues=result["results"].get("issues", []),
            improvements=result["results"].get("improvements", [])
        )
        try:
            if response is not None:
                await _apply_rate_limit_headers(limiter, user_id, response, meta)
        except Exception:
            pass
        return resp_payload

    except Exception as e:
        logger.error(f"Response quality evaluation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quality evaluation failed: {sanitize_error_message(e, 'quality evaluation')}"
        )


@router.post("/propositions", response_model=PropositionEvaluationResponse, dependencies=[Depends(check_evaluation_rate_limit)])
async def evaluate_propositions_endpoint(
    request: PropositionEvaluationRequest,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
    response: Response = None,
):
    """
    Evaluate proposition extraction quality.
    Computes precision/recall/F1 with semantic or Jaccard matching and density metrics.
    """
    try:
        # Per-user usage limits (approximate with total text tokens)
        limiter = get_user_rate_limiter_for_user(current_user.id)
        tokens_est = _estimate_tokens_from_texts(
            "\n".join(request.extracted or []),
            "\n".join(request.reference or []),
        )
        allowed, meta = await limiter.check_rate_limit(
            user_id,
            endpoint="evals:propositions",
            is_batch=False,
            tokens_requested=tokens_est,
            estimated_cost=0.0,
        )
        if not allowed:
            retry_after = meta.get("retry_after", 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=meta.get("error", "Rate limit exceeded"),
                headers={"Retry-After": str(retry_after)},
            )

        svc = get_unified_evaluation_service_for_user(current_user.id)
        result = await svc.evaluate_propositions(
            extracted=request.extracted,
            reference=request.reference,
            method=request.method or 'semantic',
            threshold=request.threshold or 0.7,
            user_id=user_id
        )

        metrics = result["results"].get("metrics", {})
        counts = result["results"].get("counts", {})

        resp_payload = PropositionEvaluationResponse(
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
        try:
            if response is not None:
                await _apply_rate_limit_headers(limiter, user_id, response, meta)
        except Exception:
            pass
        return resp_payload

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
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """Get run status and details"""
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        run = await svc.get_run(run_id)
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
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """Cancel a running evaluation"""
    try:
        svc = get_unified_evaluation_service_for_user(current_user.id)
        success = await svc.cancel_run(run_id, cancelled_by=user_id)

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
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
    response: Response = None,
):
    """
    Run multiple evaluations in batch.

    Supports running multiple evaluation types with configurable parallelism.
    """
    try:
        start_time = time.time()
        service = get_unified_evaluation_service_for_user(current_user.id)

        # Per-user usage limits (aggregate all items)
        limiter = get_user_rate_limiter_for_user(current_user.id)
        tokens_total = 0
        etype = (request.evaluation_type or "").lower()
        for item in request.items or []:
            provider_hint = item.get("api_name") if isinstance(item, dict) else None
            model_hint = None
            # Commonly used keys for model hints across clients
            if isinstance(item, dict):
                model_hint = item.get("model") or item.get("target_model")
            if etype == "geval":
                tokens_total += _estimate_tokens_from_texts(
                    (item.get("source_text") if isinstance(item, dict) else None),
                    (item.get("summary") if isinstance(item, dict) else None),
                    provider=provider_hint,
                    model=model_hint,
                )
            elif etype == "rag":
                ctx = []
                if isinstance(item, dict):
                    rc = item.get("retrieved_contexts")
                    if isinstance(rc, list):
                        ctx = rc
                tokens_total += _estimate_tokens_from_texts(
                    (item.get("query") if isinstance(item, dict) else None),
                    "\n".join(ctx),
                    (item.get("generated_response") if isinstance(item, dict) else None),
                    (item.get("ground_truth") if isinstance(item, dict) else None),
                    provider=provider_hint,
                    model=model_hint,
                )
            elif etype == "response_quality":
                tokens_total += _estimate_tokens_from_texts(
                    (item.get("prompt") if isinstance(item, dict) else None),
                    (item.get("response") if isinstance(item, dict) else None),
                    (item.get("expected_format") if isinstance(item, dict) else None),
                    provider=provider_hint,
                    model=model_hint,
                )
            elif etype == "propositions":
                extracted = []
                reference = []
                if isinstance(item, dict):
                    if isinstance(item.get("extracted"), list):
                        extracted = item.get("extracted")
                    if isinstance(item.get("reference"), list):
                        reference = item.get("reference")
                tokens_total += _estimate_tokens_from_texts(
                    "\n".join(extracted),
                    "\n".join(reference),
                )

        allowed, meta = await limiter.check_rate_limit(
            user_id,
            endpoint=f"evals:batch:{etype}",
            is_batch=True,
            tokens_requested=tokens_total,
            estimated_cost=0.0,
        )
        if not allowed:
            retry_after = meta.get("retry_after", 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=meta.get("error", "Rate limit exceeded"),
                headers={"Retry-After": str(retry_after)},
            )

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
                elif eval_type == "propositions":
                    task = service.evaluate_propositions(
                        extracted=eval_request.get("extracted", []),
                        reference=eval_request.get("reference", []),
                        method=eval_request.get("method", "semantic"),
                        threshold=eval_request.get("threshold", 0.7),
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
                    elif eval_type == "propositions":
                        result = await service.evaluate_propositions(
                            extracted=eval_request.get("extracted", []),
                            reference=eval_request.get("reference", []),
                            method=eval_request.get("method", "semantic"),
                            threshold=eval_request.get("threshold", 0.7),
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

        resp_payload = BatchEvaluationResponse(
            total_items=len(request.items),
            successful=len(results) - failed_count,
            failed=failed_count,
            results=results,
            aggregate_metrics={},  # TODO: Calculate aggregate metrics
            processing_time=processing_time
        )
        try:
            if response is not None:
                await _apply_rate_limit_headers(limiter, user_id, response, meta)
        except Exception:
            pass
        return resp_payload

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
    response: Response,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """Evaluate OCR effectiveness on provided items (text-to-text comparison).

    Note: This endpoint currently expects pre-extracted text per item.
    PDF-based OCR execution can be added in future if needed.
    """
    try:
        # Per-user usage limits (approximate by total text length)
        limiter = get_user_rate_limiter_for_user(current_user.id)
        texts = []
        try:
            for it in request.items or []:
                if getattr(it, "extracted_text", None):
                    texts.append(it.extracted_text)
                if getattr(it, "ground_truth_text", None):
                    texts.append(it.ground_truth_text)
        except Exception:
            pass
        tokens_est = _estimate_tokens_from_texts("\n".join(texts))
        allowed, meta = await limiter.check_rate_limit(user_id, endpoint="evals:ocr", is_batch=False, tokens_requested=tokens_est, estimated_cost=0.0)
        if not allowed:
            retry_after = meta.get("retry_after", 60)
            raise HTTPException(status_code=429, detail=meta.get("error", "Rate limit exceeded"), headers={"Retry-After": str(retry_after)})

        service = get_unified_evaluation_service_for_user(current_user.id)
        result = await service.evaluate_ocr(
            items=[i.model_dump() for i in request.items],
            metrics=request.metrics,
            ocr_options=request.ocr_options,
            thresholds=request.thresholds,
            user_id=user_id,
        )
        try:
            usage = result.get("usage") if isinstance(result, dict) else None
            if usage and isinstance(usage, dict):
                await limiter.record_actual_usage(user_id, "evals:ocr", int(usage.get("total_tokens", 0)), float(usage.get("cost", 0.0) or 0.0))
        except Exception:
            pass
        # Apply headers
        try:
            if response is not None:
                await _apply_rate_limit_headers(limiter, user_id, response, meta)
        except Exception:
            pass
        return OCREvaluationResponse(**result)
    except Exception as e:
        logger.error(f"OCR evaluation endpoint failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR evaluation failed: {sanitize_error_message(e, 'ocr evaluation')}"
        )


@router.post("/ocr-pdf", response_model=OCREvaluationResponse, dependencies=[Depends(check_evaluation_rate_limit)])
async def evaluate_ocr_pdf_endpoint(
    response: Response,
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
    current_user: User = Depends(get_request_user),
):
    """Evaluate OCR by running OCR on uploaded PDFs and comparing to provided ground-truths."""
    try:
        # Per-user usage limits (approximate by file sizes if available)
        limiter = get_user_rate_limiter_for_user(current_user.id)
        size_est = 0
        try:
            for f in files:
                s = getattr(f, "size", None)
                if isinstance(s, int):
                    size_est += s
        except Exception:
            pass
        tokens_est = max(0, size_est // 4)
        allowed, meta = await limiter.check_rate_limit(user_id, endpoint="evals:ocr_pdf", is_batch=False, tokens_requested=tokens_est, estimated_cost=0.0)
        if not allowed:
            retry_after = meta.get("retry_after", 60)
            raise HTTPException(status_code=429, detail=meta.get("error", "Rate limit exceeded"), headers={"Retry-After": str(retry_after)})
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

        service = get_unified_evaluation_service_for_user(current_user.id)
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
        try:
            usage = result.get("usage") if isinstance(result, dict) else None
            if usage and isinstance(usage, dict):
                await limiter.record_actual_usage(user_id, "evals:ocr", int(usage.get("total_tokens", 0)), float(usage.get("cost", 0.0) or 0.0))
        except Exception:
            pass
        try:
            if response is not None:
                await _apply_rate_limit_headers(limiter, user_id, response)
        except Exception:
            pass
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
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    """
    Retrieve evaluation history for a user.

    Supports filtering by date range, evaluation type, and pagination.
    """
    try:
        service = get_unified_evaluation_service_for_user(current_user.id)

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


def _promote_static_routes(_router: APIRouter) -> None:
    """Ensure static paths are registered before catch-all routes."""
    try:
        prioritized_suffixes = ("/health", "/metrics")
        # Move each target to the front, preserving relative order
        for suffix in reversed(prioritized_suffixes):
            prefixed = f"{_router.prefix}{suffix}" if _router.prefix else suffix
            for idx, route in enumerate(list(_router.routes)):
                path = getattr(route, "path", "")
                if path in {suffix, prefixed} and isinstance(route, APIRoute):
                    _router.routes.insert(0, _router.routes.pop(idx))
                    break
    except Exception as exc:  # Safety: never fail import due to ordering tweak
        try:
            logger.debug(f"Failed to promote evaluation routes: {exc}")
        except Exception:
            pass


_promote_static_routes(router)
