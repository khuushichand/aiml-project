"""
Embeddings A/B test endpoints extracted from evaluations_unified.
"""

import json
import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, BackgroundTasks, Response
from loguru import logger

from tldw_Server_API.app.api.v1.endpoints.evaluations_auth import (
    verify_api_key,
    check_evaluation_rate_limit,
    require_admin,
)
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import (
    get_unified_evaluation_service_for_user,
)
from tldw_Server_API.app.api.v1.schemas.embeddings_abtest_schemas import (
    EmbeddingsABTestCreateRequest,
    EmbeddingsABTestCreateResponse,
    EmbeddingsABTestStatusResponse,
    EmbeddingsABTestResultsResponse,
    EmbeddingsABTestResultSummary,
    ArmSummary,
)
from tldw_Server_API.app.core.Evaluations.embeddings_abtest_service import (
    run_abtest_full,
    compute_significance,
)


abtest_router = APIRouter()


from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope


@abtest_router.post(
    "/embeddings/abtest",
    response_model=EmbeddingsABTestCreateResponse,
    dependencies=[Depends(require_token_scope("workflows", require_if_present=True, endpoint_id="evals.embeddings_abtest.create"))],
)
async def create_embeddings_abtest(
    payload: EmbeddingsABTestCreateRequest,
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
    current_user: User = Depends(get_request_user),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    response: Response = None,
):
    svc = get_unified_evaluation_service_for_user(current_user.id)
    db = svc.db
    if idempotency_key:
        try:
            existing_id = db.lookup_idempotency("emb_abtest", idempotency_key, user_ctx)
            if existing_id:
                logger.info(f"A/B test idempotent hit: {existing_id}")
                if response is not None:
                    try:
                        response.headers["X-Idempotent-Replay"] = "true"
                        response.headers["Idempotency-Key"] = idempotency_key
                    except Exception:
                        pass
                return EmbeddingsABTestCreateResponse(test_id=existing_id, status='created')
        except Exception:
            pass
    cfg = payload.config
    if getattr(cfg, 'chunking', None) is None:
        try:
            from tldw_Server_API.app.api.v1.schemas.embeddings_abtest_schemas import ABTestChunking
            cfg.chunking = ABTestChunking(method='sentences', size=200, overlap=20, language=None)
        except Exception:
            pass
    test_id = db.create_abtest(name=payload.name, config=cfg.model_dump(), created_by=user_ctx)
    for idx, arm in enumerate(payload.config.arms):
        db.upsert_abtest_arm(
            test_id=test_id,
            arm_index=idx,
            provider=arm.provider,
            model_id=arm.model,
            dimensions=arm.dimensions,
            status='pending',
        )
    db.insert_abtest_queries(test_id, [q.model_dump() for q in payload.config.queries])
    logger.info(f"A/B test created: {test_id} by {user_ctx}")
    try:
        if idempotency_key:
            db.record_idempotency("emb_abtest", idempotency_key, test_id, user_ctx)
    except Exception:
        pass
    return EmbeddingsABTestCreateResponse(test_id=test_id, status='created')


@abtest_router.post(
    "/embeddings/abtest/{test_id}/run",
    response_model=EmbeddingsABTestStatusResponse,
)
async def run_embeddings_abtest(
    test_id: str,
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
    __: None = Depends(require_token_scope("workflows", require_if_present=True, require_schedule_match=False, allow_admin_bypass=True, endpoint_id="evals.embeddings_abtest.run", count_as="run")),
    media_db = Depends(get_media_db_for_user),
    current_user: User = Depends(get_request_user),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    response: Response = None,
):
    require_admin(current_user)
    svc = get_unified_evaluation_service_for_user(current_user.id)
    db = svc.db
    if idempotency_key:
        try:
            prior = db.lookup_idempotency("emb_abtest_run", idempotency_key, user_ctx)
            if prior:
                logger.info(f"A/B test run idempotent hit: {test_id}")
                if response is not None:
                    try:
                        response.headers["X-Idempotent-Replay"] = "true"
                        response.headers["Idempotency-Key"] = idempotency_key
                    except Exception:
                        pass
                return EmbeddingsABTestStatusResponse(test_id=test_id, status='running', progress={"phase": 0.05})
        except Exception:
            pass
    from tldw_Server_API.app.api.v1.schemas.embeddings_abtest_schemas import (
        EmbeddingsABTestConfig, ABTestChunking,
    )
    raw_cfg = payload.get("config") if isinstance(payload, dict) else None
    cfg = EmbeddingsABTestConfig.model_validate(raw_cfg or {})
    if getattr(cfg, 'chunking', None) is None:
        try:
            cfg.chunking = ABTestChunking(method='sentences', size=200, overlap=20, language=None)
        except Exception:
            pass

    async def _abtest_job():
        try:
            await run_abtest_full(db, cfg, test_id, str(current_user.id), media_db)
        except Exception as _e:
            try:
                logger.warning(f"A/B test background run failed: {_e}")
            except Exception:
                pass

    # Mark as running before scheduling to avoid race where clients
    # observe previous 'completed' state before the job flips it.
    try:
        db.set_abtest_status(test_id, 'running', stats_json={"progress": {"phase": 0.01}})
    except Exception:
        pass

    # In testing mode, execute synchronously to make polling deterministic
    testing = False
    try:
        testing = os.getenv("TESTING", "").lower() in {"1", "true", "yes", "on"}
    except Exception:
        testing = False

    if testing:
        logger.info(f"A/B test running synchronously in TESTING mode: {test_id}")
        await _abtest_job()
        try:
            if idempotency_key:
                db.record_idempotency("emb_abtest_run", idempotency_key, test_id, user_ctx)
        except Exception:
            pass
        return EmbeddingsABTestStatusResponse(test_id=test_id, status='completed', progress={"phase": 1.0})

    # Schedule background task
    background_tasks.add_task(_abtest_job)
    logger.info(f"A/B test started in background: {test_id}")
    try:
        if idempotency_key:
            db.record_idempotency("emb_abtest_run", idempotency_key, test_id, user_ctx)
    except Exception:
        pass
    return EmbeddingsABTestStatusResponse(test_id=test_id, status='running', progress={"phase": 0.05})


@abtest_router.get("/embeddings/abtest/{test_id}", response_model=EmbeddingsABTestResultSummary)
async def get_embeddings_abtest_status(
    test_id: str,
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
    current_user: User = Depends(get_request_user),
):
    svc = get_unified_evaluation_service_for_user(current_user.id)
    row = svc.db.get_abtest(test_id)
    if not row:
        raise HTTPException(status_code=404, detail="abtest not found")
    status_val = row.get('status', 'pending')
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
    return EmbeddingsABTestResultSummary(test_id=test_id, status=status_val, arms=arms)


@abtest_router.get("/embeddings/abtest/{test_id}/results", response_model=EmbeddingsABTestResultsResponse)
async def get_embeddings_abtest_results(
    test_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
    current_user: User = Depends(get_request_user),
):
    svc = get_unified_evaluation_service_for_user(current_user.id)
    rows, total = svc.db.list_abtest_results(test_id, limit=page_size, offset=(page-1)*page_size)
    row = svc.db.get_abtest(test_id)
    if not row:
        raise HTTPException(status_code=404, detail="abtest not found")
    status_val = row.get('status', 'pending')
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
    summary = EmbeddingsABTestResultSummary(test_id=test_id, status=status_val, arms=arms)
    return EmbeddingsABTestResultsResponse(summary=summary, page=page, page_size=page_size, total=total)


@abtest_router.get("/embeddings/abtest/{test_id}/significance")
async def get_embeddings_abtest_significance(
    test_id: str,
    metric: str = Query("ndcg"),
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
    current_user: User = Depends(get_request_user),
):
    svc = get_unified_evaluation_service_for_user(current_user.id)
    _ = svc.db.get_abtest(test_id) or (_ for _ in ()).throw(HTTPException(404, "abtest not found"))
    return compute_significance(svc.db, test_id, metric=metric)
