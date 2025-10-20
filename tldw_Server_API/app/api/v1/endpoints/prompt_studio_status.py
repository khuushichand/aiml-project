"""
Prompt Studio Status/Health API

Provides lightweight observability for the Prompt Studio job queue,
including queue depth, processing counts, and lease health.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.prompt_studio_base import StandardResponse
from tldw_Server_API.app.api.v1.API_Deps.prompt_studio_deps import (
    get_prompt_studio_db, PromptStudioDatabase
)
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.monitoring import prompt_studio_metrics


router = APIRouter(
    prefix="/api/v1/prompt-studio/status",
    tags=["prompt-studio"],
)


@router.get("", response_model=StandardResponse, openapi_extra={
    "responses": {
        "200": {
            "description": "Prompt Studio queue health and status",
            "content": {
                "application/json": {
                    "examples": {
                        "ok": {
                            "summary": "Queue health",
                            "value": {
                                "success": True,
                                "data": {
                                    "queue_depth": 0,
                                    "processing": 0,
                                    "leases": {"active": 0, "expiring_soon": 0, "stale_processing": 0},
                                    "by_status": {"queued": 0, "processing": 0},
                                    "by_type": {"optimization": 0},
                                    "avg_processing_time_seconds": 0,
                                    "success_rate": 100.0
                                }
                            }
                        }
                    }
                }
            }
        }
    }
})
async def get_prompt_studio_status(
    warn_seconds: int = Query(30, ge=1, le=3600, description="Threshold for expiring leases"),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
) -> StandardResponse:
    """Return queue depth, processing count, and lease health stats."""
    try:
        stats: Dict[str, Any] = db.get_job_stats()
        leases: Dict[str, int] = {}
        try:
            leases = db.get_lease_stats(warn_seconds)
        except Exception as e:
            # Don't fail the endpoint on lease-stats specifics; include a hint
            logger.debug(f"Lease stats unavailable: {e}")
            leases = {"active": 0, "expiring_soon": 0, "stale_processing": 0}

        by_status = stats.get("by_status", {})
        data = {
            "queue_depth": stats.get("queue_depth", by_status.get("queued", 0)),
            "processing": stats.get("processing", by_status.get("processing", 0)),
            "leases": leases,
            "by_status": by_status,
            "by_type": stats.get("by_type", {}),
            "avg_processing_time_seconds": stats.get("avg_processing_time_seconds", 0),
            "success_rate": stats.get("success_rate", 0.0),
        }
        # Prometheus hook: export gauges for queue/lease metrics
        try:
            backend_label = getattr(db, "backend_type", None)
            backend_label = getattr(backend_label, "name", str(backend_label)) if backend_label is not None else "unknown"
            reg = get_metrics_registry()
            reg.set_gauge("prompt_studio_queue_depth", float(data["queue_depth"]), labels={"backend": backend_label})
            reg.set_gauge("prompt_studio_processing", float(data["processing"]), labels={"backend": backend_label})
            reg.set_gauge("prompt_studio_leases_active", float(leases.get("active", 0)), labels={"backend": backend_label})
            reg.set_gauge("prompt_studio_leases_expiring_soon", float(leases.get("expiring_soon", 0)), labels={"backend": backend_label})
            reg.set_gauge("prompt_studio_leases_stale_processing", float(leases.get("stale_processing", 0)), labels={"backend": backend_label})
            # Periodic refresh of per-type gauges (queued/processing/backlog) based on current DB counts
            try:
                by_type = stats.get("by_type", {})
                for jt in by_type.keys():
                    q = db.count_jobs(status="queued", job_type=jt)
                    p = db.count_jobs(status="processing", job_type=jt)
                    # Update Prompt Studio gauges
                    prompt_studio_metrics.update_job_queue_size(jt, int(q))
                    prompt_studio_metrics.metrics_manager.set_gauge(
                        "jobs.processing", float(p), labels={"job_type": jt}
                    )
                    backlog = max(0, int(q) - int(p))
                    prompt_studio_metrics.metrics_manager.set_gauge(
                        "jobs.backlog", float(backlog), labels={"job_type": jt}
                    )
                # Aggregate stale processing value
                prompt_studio_metrics.metrics_manager.set_gauge(
                    "jobs.stale_processing",
                    float(leases.get("stale_processing", 0)),
                )
            except Exception as e:
                logger.debug(f"Failed to refresh per-type gauges: {e}")
        except Exception as e:
            logger.debug(f"Failed to set Prompt Studio gauges: {e}")

        return StandardResponse(success=True, data=data)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to compute Prompt Studio status: {exc}")
        return StandardResponse(success=False, error=str(exc))
