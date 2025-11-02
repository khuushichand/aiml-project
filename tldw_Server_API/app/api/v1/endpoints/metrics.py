# metrics.py
# Metrics endpoint for Prometheus and health monitoring

from fastapi import APIRouter, Response, HTTPException, status, Depends
from typing import Dict, Any, Optional

from loguru import logger

from tldw_Server_API.app.core.Chat.chat_metrics import get_chat_metrics
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin

router = APIRouter(tags=["metrics"])


# Note: Avoid path conflict with the JSON metrics in main.py (`/api/v1/metrics`).
# Expose text format under `/api/v1/metrics/text`.
@router.get("/metrics/text",
            summary="Get metrics in Prometheus text format",
            response_class=Response)
async def get_prometheus_metrics() -> Response:
    """
    Export all metrics in Prometheus text format.

    This endpoint provides metrics for monitoring the application's performance,
    including:
    - Request rates and latencies
    - LLM API usage and costs
    - Database operations
    - Chat-specific metrics
    - System resource usage

    The format is compatible with Prometheus scrapers.
    """
    try:
        registry = get_metrics_registry()
        # Ensure core embeddings histograms are registered in the default Prometheus REGISTRY
        try:
            # Importing the module defines histograms at import time and pre-creates label children
            from tldw_Server_API.app.core.Embeddings.workers import base_worker as _bw  # noqa: F401
            # Also ensure embeddings endpoint module (with gauges) is imported so collectors exist
            import tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced as _emb  # noqa: F401
            # Best-effort: refresh stage flag gauges from Redis so they appear in metrics
            try:
                client = await _emb._get_redis_client()
                for _st in ("chunking", "embedding", "storage"):
                    try:
                        p = await client.get(f"embeddings:stage:{_st}:paused")
                        d = await client.get(f"embeddings:stage:{_st}:drain")
                        _emb.embedding_stage_flag.labels(stage=_st, flag="paused").set(1.0 if str(p).lower() in ("1","true","yes") else 0.0)
                        _emb.embedding_stage_flag.labels(stage=_st, flag="drain").set(1.0 if str(d).lower() in ("1","true","yes") else 0.0)
                    except Exception:
                        logger.debug("metrics: failed to refresh stage gauge for %s", _st)
                try:
                    await client.close()
                except Exception:
                    logger.debug("metrics: failed to close redis client")
            except Exception:
                logger.debug("metrics: redis not available for stage flags")
        except Exception:
            logger.debug("metrics: embeddings modules not available for import")
        prometheus_text = registry.export_prometheus_format() or ""
        try:
            from prometheus_client import REGISTRY as PC_REGISTRY, generate_latest as pc_generate_latest
            prometheus_text = (prometheus_text + "\n" + pc_generate_latest(PC_REGISTRY).decode('utf-8')).strip() + "\n"
        except Exception:
            logger.debug("metrics: failed to augment with prometheus_client registry")
        # Append explicit stage flag gauge lines (best-effort) to satisfy text scrapers
        try:
            import tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced as _emb
            # Read current values via gauge collectors if present; otherwise fetch from Redis directly
            lines = ["# HELP embedding_stage_flag Per-stage control flags as gauges (1=true,0=false)",
                     "# TYPE embedding_stage_flag gauge"]
            try:
                # Prefer Redis source for authoritative values
                client = await _emb._get_redis_client()
                for _st in ("chunking", "embedding", "storage"):
                    p = await client.get(f"embeddings:stage:{_st}:paused")
                    d = await client.get(f"embeddings:stage:{_st}:drain")
                    pv = 1.0 if str(p).lower() in ("1","true","yes") else 0.0
                    dv = 1.0 if str(d).lower() in ("1","true","yes") else 0.0
                    lines.append(f"embedding_stage_flag{{stage=\"{_st}\",flag=\"paused\"}} {pv}")
                    lines.append(f"embedding_stage_flag{{stage=\"{_st}\",flag=\"drain\"}} {dv}")
                try:
                    await client.close()
                except Exception:
                    logger.debug("metrics: failed closing redis client (gauge lines)")
            except Exception:
                # Fallback: if Redis unavailable, skip explicit lines
                lines = []
            if lines:
                prometheus_text = (prometheus_text.rstrip("\n") + "\n" + "\n".join(lines) + "\n")
        except Exception:
            logger.debug("metrics: failed to append explicit gauge lines")
        return Response(
            content=prometheus_text,
            media_type="text/plain; version=0.0.4",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    except Exception as e:
        logger.error(f"Error exporting metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export metrics"
        )


@router.get("/metrics/json",
            summary="Get metrics in JSON format",
            response_model=Dict[str, Any])
async def get_json_metrics() -> Dict[str, Any]:
    """
    Get all metrics in JSON format.

    This provides a more detailed view of metrics with statistics,
    useful for debugging and custom monitoring solutions.
    """
    try:
        registry = get_metrics_registry()
        chat_metrics = get_chat_metrics()

        all_metrics = registry.get_all_metrics()
        active_operations = chat_metrics.get_active_metrics()

        return {
            "metrics": all_metrics,
            "active_operations": active_operations,
            "timestamp": None  # Will be set to current time by FastAPI
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics"
        )


@router.get("/metrics/health",
            summary="Health check with metrics",
            response_model=Dict[str, Any])
async def health_check_with_metrics() -> Dict[str, Any]:
    """
    Health check endpoint with basic metrics.

    Returns the health status of the application along with
    key operational metrics.
    """
    try:
        chat_metrics = get_chat_metrics()
        active = chat_metrics.get_active_metrics()

        # Determine health status based on active operations
        status = "healthy"
        # Check higher threshold first so we can actually reach "unhealthy"
        if active["active_requests"] > 200:
            status = "unhealthy"
        elif active["active_requests"] > 100:
            status = "degraded"

        return {
            "status": status,
            "active_requests": active["active_requests"],
            "active_streams": active["active_streams"],
            "active_transactions": active["active_transactions"],
            "message": "Service is operational"
        }
    except Exception as e:
        logger.error(f"Metrics Health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Metrics Health check failed: ERROR - SEE LOGS",
            "active_requests": -1,
            "active_streams": -1,
            "active_transactions": -1
        }


@router.get("/metrics/chat",
            summary="Get chat-specific metrics",
            response_model=Dict[str, Any])
async def get_chat_metrics_endpoint() -> Dict[str, Any]:
    """
    Get detailed chat-specific metrics.

    This endpoint provides metrics specifically related to the chat
    functionality, including:
    - Request counts by provider and model
    - Token usage and costs
    - Streaming statistics
    - Character and conversation metrics
    """
    try:
        chat_metrics = get_chat_metrics()
        registry = get_metrics_registry()

        # Extract chat-specific metrics
        chat_metric_names = [
            "chat_requests_total",
            "chat_request_duration_seconds",
            "chat_tokens_prompt",
            "chat_tokens_completion",
            "chat_llm_cost_estimate_usd",
            "chat_streaming_duration_seconds",
            "chat_conversations_created_total",
            "chat_messages_saved_total",
            "chat_errors_total"
        ]

        chat_stats = {}
        for metric_name in chat_metric_names:
            stats = registry.get_metric_stats(metric_name)
            if stats:
                chat_stats[metric_name] = stats

        active = chat_metrics.get_active_metrics()

        return {
            "active_operations": active,
            "metrics": chat_stats,
            "token_costs": chat_metrics.token_costs  # Model pricing info
        }
    except Exception as e:
        logger.error(f"Error getting chat metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat metrics"
        )


@router.post("/metrics/reset",
             summary="Reset metrics (admin only)",
             response_model=Dict[str, str])
async def reset_metrics(_: Any = Depends(require_admin)) -> Dict[str, str]:
    """
    Reset all metrics to their initial state.

    WARNING: This will clear all historical metrics data.
    This endpoint should be protected with admin authentication
    in production.
    """
    try:
        # Reinitialize metrics
        registry = get_metrics_registry()
        chat_metrics = get_chat_metrics()

        # Clear values
        registry.values.clear()

        # Reset active counters
        chat_metrics.active_requests = 0
        chat_metrics.active_streams = 0
        chat_metrics.active_transactions = 0

        logger.info("Metrics reset by admin")

        return {
            "status": "success",
            "message": "All metrics have been reset"
        }
    except Exception as e:
        logger.error(f"Error resetting metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset metrics"
        )
