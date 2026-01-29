"""
Embeddings A/B test endpoints extracted from evaluations_unified.
"""

import json
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Response
from loguru import logger

from tldw_Server_API.app.api.v1.endpoints.evaluations_auth import (
    verify_api_key,
    check_evaluation_rate_limit,
    enforce_heavy_evaluations_admin,
    get_eval_request_user,
)
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope, get_auth_principal
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
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
    EmbeddingsABTestResultRow,
    ArmSummary,
    EmbeddingsABTestRunRequest,
)
from tldw_Server_API.app.core.Evaluations.audit_adapter import (
    log_evaluation_created,
    log_run_started,
)
from tldw_Server_API.app.core.Evaluations.embeddings_abtest_service import (
    run_abtest_full,
    compute_significance,
    validate_abtest_policy,
    EmbeddingsABTestPolicyError,
)
from tldw_Server_API.app.core.Evaluations.embeddings_abtest_jobs import (
    ABTEST_JOBS_DOMAIN,
    ABTEST_JOBS_JOB_TYPE,
    abtest_jobs_idempotency_key,
    abtest_jobs_manager,
    abtest_jobs_queue,
)


abtest_router = APIRouter()


@abtest_router.post(
    "/embeddings/abtest",
    response_model=EmbeddingsABTestCreateResponse,
    dependencies=[Depends(require_token_scope("workflows", require_if_present=True, endpoint_id="evals.embeddings_abtest.create"))],
)
async def create_embeddings_abtest(
    payload: EmbeddingsABTestCreateRequest,
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
    current_user: User = Depends(get_eval_request_user),  # noqa: B008
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
    try:
        validate_abtest_policy(cfg, user=current_user)
    except EmbeddingsABTestPolicyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
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
    log_evaluation_created(
        user_id=str(current_user.id),
        eval_id=test_id,
        name=payload.name,
        eval_type="embeddings_abtest",
    )
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
    payload: EmbeddingsABTestRunRequest,
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
    __: None = Depends(require_token_scope("workflows", require_if_present=True, require_schedule_match=False, allow_admin_bypass=True, endpoint_id="evals.embeddings_abtest.run", count_as="run")),
    media_db = Depends(get_media_db_for_user),
    principal: AuthPrincipal = Depends(get_auth_principal),  # noqa: B008
    current_user: User = Depends(get_eval_request_user),  # noqa: B008
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    response: Response = None,
):
    enforce_heavy_evaluations_admin(principal)
    svc = get_unified_evaluation_service_for_user(current_user.id)
    db = svc.db
    if not db.get_abtest(test_id, created_by=user_ctx):
        raise HTTPException(status_code=404, detail="abtest not found")
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
    from tldw_Server_API.app.api.v1.schemas.embeddings_abtest_schemas import ABTestChunking
    cfg = payload.config
    if getattr(cfg, 'chunking', None) is None:
        try:
            cfg.chunking = ABTestChunking(method='sentences', size=200, overlap=20, language=None)
        except Exception:
            pass
    try:
        validate_abtest_policy(cfg, user=current_user)
    except EmbeddingsABTestPolicyError as exc:
        try:
            db.set_abtest_status(
                test_id,
                'failed',
                stats_json={"error": str(exc), "policy": exc.details, "status_code": exc.status_code},
                created_by=user_ctx,
            )
        except Exception:
            pass
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    # In testing mode, execute synchronously to make polling deterministic
    testing = False
    try:
        testing = os.getenv("TESTING", "").lower() in {"1", "true", "yes", "on"}
    except Exception:
        testing = False

    if testing:
        logger.info(f"A/B test running synchronously in TESTING mode: {test_id}")
        try:
            db.set_abtest_status(test_id, 'running', stats_json={"progress": {"phase": 0.01}}, created_by=user_ctx)
        except Exception:
            pass
        log_run_started(
            user_id=str(current_user.id),
            run_id=str(test_id),
            eval_id=test_id,
            target_model="embeddings_abtest",
        )
        run_error: Optional[Exception] = None
        try:
            await run_abtest_full(db, cfg, test_id, str(current_user.id), media_db)
        except Exception as _e:
            run_error = _e
            try:
                logger.warning(f"A/B test synchronous run failed: {_e}")
            except Exception:
                pass
        try:
            if idempotency_key:
                db.record_idempotency("emb_abtest_run", idempotency_key, test_id, user_ctx)
        except Exception:
            pass
        if run_error is not None:
            try:
                db.set_abtest_status(test_id, 'failed', stats_json={"error": str(run_error)}, created_by=user_ctx)
            except Exception:
                pass
            return EmbeddingsABTestStatusResponse(test_id=test_id, status='failed', progress={"phase": 0.0})
        return EmbeddingsABTestStatusResponse(test_id=test_id, status='completed', progress={"phase": 1.0})

    try:
        jm = abtest_jobs_manager()
        job_payload = {
            "test_id": test_id,
            "config": cfg.model_dump(),
            "user_id": str(current_user.id),
        }
        job_row = jm.create_job(
            domain=ABTEST_JOBS_DOMAIN,
            queue=abtest_jobs_queue(),
            job_type=ABTEST_JOBS_JOB_TYPE,
            payload=job_payload,
            owner_user_id=str(current_user.id),
            priority=5,
            max_retries=3,
            idempotency_key=abtest_jobs_idempotency_key(test_id, idempotency_key),
        )
        job_ref = job_row.get("uuid") or job_row.get("id")
        try:
            db.set_abtest_status(
                test_id,
                'running',
                stats_json={"progress": {"phase": 0.01}, "job_id": job_ref},
                created_by=user_ctx,
            )
        except Exception:
            pass
        log_run_started(
            user_id=str(current_user.id),
            run_id=str(job_ref or test_id),
            eval_id=test_id,
            target_model="embeddings_abtest",
        )
    except Exception as exc:
        logger.error(f"Failed to enqueue A/B test job {test_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to enqueue A/B test job")

    logger.info(f"A/B test enqueued via Jobs: {test_id}")
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
    current_user: User = Depends(get_eval_request_user),  # noqa: B008
):
    svc = get_unified_evaluation_service_for_user(current_user.id)
    row = svc.db.get_abtest(test_id, created_by=user_ctx)
    if not row:
        raise HTTPException(status_code=404, detail="abtest not found")
    status_val = row.get('status', 'pending')
    aggregates = {}
    try:
        stats_json = json.loads(row.get('stats_json') or '{}')
        aggregates = stats_json.get('aggregates') or {}
    except Exception:
        aggregates = {}
    arms_rows = svc.db.get_abtest_arms(test_id, created_by=user_ctx)
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
    current_user: User = Depends(get_eval_request_user),  # noqa: B008
):
    def _parse_json(value, default):
        if value is None:
            return default
        if isinstance(value, (list, dict)):
            return value
        try:
            parsed = json.loads(value)
        except Exception:
            return default
        return parsed if isinstance(parsed, (list, dict)) else default

    def _parse_float_list(value):
        parsed = _parse_json(value, None)
        if not isinstance(parsed, list):
            return None
        out = []
        for item in parsed:
            try:
                out.append(float(item))
            except (TypeError, ValueError):
                continue
        return out

    svc = get_unified_evaluation_service_for_user(current_user.id)
    rows, total = svc.db.list_abtest_results(test_id, limit=page_size, offset=(page-1)*page_size, created_by=user_ctx)
    row = svc.db.get_abtest(test_id, created_by=user_ctx)
    if not row:
        raise HTTPException(status_code=404, detail="abtest not found")
    status_val = row.get('status', 'pending')
    aggregates = {}
    try:
        stats_json = json.loads(row.get('stats_json') or '{}')
        aggregates = stats_json.get('aggregates') or {}
    except Exception:
        aggregates = {}
    arms_rows = svc.db.get_abtest_arms(test_id, created_by=user_ctx)
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
    results = []
    for r in rows:
        ranked_ids = _parse_json(r.get("ranked_ids"), [])
        scores = _parse_json(r.get("scores"), None)
        metrics = _parse_json(r.get("metrics_json"), {})
        results.append(
            EmbeddingsABTestResultRow(
                result_id=str(r.get("result_id")),
                test_id=str(r.get("test_id") or test_id),
                arm_id=str(r.get("arm_id")),
                query_id=str(r.get("query_id")),
                ranked_ids=ranked_ids if isinstance(ranked_ids, list) else [],
                scores=scores if isinstance(scores, list) else None,
                metrics=metrics if isinstance(metrics, dict) else {},
                latency_ms=float(r.get("latency_ms")) if r.get("latency_ms") is not None else None,
                ranked_distances=_parse_float_list(r.get("ranked_distances")),
                ranked_metadatas=_parse_json(r.get("ranked_metadatas"), None),
                ranked_documents=_parse_json(r.get("ranked_documents"), None),
                rerank_scores=_parse_float_list(r.get("rerank_scores")),
                created_at=r.get("created_at"),
            )
        )
    return EmbeddingsABTestResultsResponse(
        summary=summary,
        results=results,
        page=page,
        page_size=page_size,
        total=total,
    )


@abtest_router.get("/embeddings/abtest/{test_id}/significance")
async def get_embeddings_abtest_significance(
    test_id: str,
    metric: str = Query("ndcg"),
    user_ctx: str = Depends(verify_api_key),
    _: None = Depends(check_evaluation_rate_limit),
    current_user: User = Depends(get_eval_request_user),  # noqa: B008
):
    svc = get_unified_evaluation_service_for_user(current_user.id)
    _ = svc.db.get_abtest(test_id, created_by=user_ctx) or (_ for _ in ()).throw(HTTPException(404, "abtest not found"))
    return compute_significance(svc.db, test_id, metric=metric)
