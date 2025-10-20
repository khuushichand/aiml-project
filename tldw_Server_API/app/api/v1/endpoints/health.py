from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from loguru import logger

from tldw_Server_API.app.core.DB_Management.DB_Manager import create_workflows_database, get_content_backend_instance
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.Workflows.engine import WorkflowScheduler

try:
    from tldw_Server_API.app.core.Audit.unified_audit_service import UnifiedAuditService as _UnifiedAuditService
except Exception:  # pragma: no cover - defensive import guard for optional dependencies
    _UnifiedAuditService = None  # type: ignore[assignment]

# Expose symbol for tests to monkeypatch (see test_security_health_thresholds.py)
UnifiedAuditService = _UnifiedAuditService  # type: ignore[assignment]

router = APIRouter()


def _utcnow_iso() -> str:
    import datetime as _dt
    return _dt.datetime.utcnow().isoformat()


def _check_workflows_db() -> dict:
    """Basic connectivity and schema readiness for workflows DB."""
    status = {"ok": False, "backend": None, "schema_version": None, "expected_version": None}
    try:
        backend = get_content_backend_instance()
        db: WorkflowsDatabase = create_workflows_database(backend=backend)
        status["backend"] = backend.backend_type.name if backend else "sqlite"
        # Connectivity probe
        if db._using_backend():
            with db.backend.transaction() as conn:  # type: ignore[union-attr]
                # Lightweight probe
                db._execute_backend("SELECT 1", None, connection=conn)
                # Migration version check (backend only)
                try:
                    status["schema_version"] = int(db._get_backend_schema_version(conn))  # type: ignore[attr-defined]
                    status["expected_version"] = int(db._CURRENT_SCHEMA_VERSION)  # type: ignore[attr-defined]
                except Exception:
                    pass
        else:
            # SQLite: best-effort probe
            _ = db._conn.cursor().execute("SELECT 1").fetchone()  # type: ignore[attr-defined]
            status["schema_version"] = None
            status["expected_version"] = None
        status["ok"] = True
    except Exception as e:
        logger.error(f"/readyz DB check failed: {e}")
        status["error"] = str(e)
    return status


@router.get("/healthz", include_in_schema=False)
async def healthz():
    """Basic liveness check with lightweight engine stats."""
    try:
        qd = WorkflowScheduler.instance().queue_depth()
    except Exception:
        qd = None
    return {
        "status": "ok",
        "queue_depth": qd,
        "time": _utcnow_iso(),
    }


@router.get("/readyz", include_in_schema=False)
async def readyz():
    """Readiness check: engine stats + DB connectivity and schema version (backend)."""
    try:
        stats = WorkflowScheduler.instance().stats()
    except Exception:
        stats = {"queue_depth": None, "active_tenants": None, "active_workflows": None}
    db = _check_workflows_db()
    ready = bool(db.get("ok")) and (db.get("schema_version") is None or db.get("schema_version") == db.get("expected_version"))
    body = {
        "ready": ready,
        "engine": stats,
        "db": db,
        "time": _utcnow_iso(),
    }
    # Fail readiness (HTTP 503) if schema version mismatch or DB not ok
    if not ready:
        return JSONResponse(body, status_code=503)
    return JSONResponse(body, status_code=200)


# Compatibility health endpoints expected by tests (/api/v1/health, /api/v1/health/live, /api/v1/health/ready, /api/v1/health/metrics)

@router.get("/health", tags=["health"], summary="Aggregate health status")
async def api_health():
    """Return aggregate health with a checks map and timestamp."""
    from datetime import datetime as _dt
    checks: dict[str, dict] = {}
    overall = "ok"

    # Database health (AuthNZ pool)
    try:
        from tldw_Server_API.app.core.AuthNZ.database import get_db_pool as _get_pool
        pool = await _get_pool()
        dbh = await pool.health_check()
        checks["database"] = dbh
        if dbh.get("status") != "healthy":
            overall = "degraded"
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall = "unhealthy"

    # Metrics registry presence
    try:
        from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry as _get_reg
        reg = _get_reg()
        metrics_ok = bool(reg)
        checks["metrics"] = {"status": "healthy" if metrics_ok else "unhealthy"}
        if not metrics_ok and overall == "ok":
            overall = "degraded"
    except Exception as e:
        checks["metrics"] = {"status": "unhealthy", "error": str(e)}
        overall = "unhealthy"

    body = {
        "status": overall,
        "checks": checks,
        "timestamp": _dt.utcnow().isoformat(),
    }
    code = status.HTTP_200_OK if overall == "ok" else (206 if overall == "degraded" else 503)
    return JSONResponse(body, status_code=code)


@router.get("/health/live", tags=["health"], summary="Liveness probe")
async def api_liveness():
    return {"status": "alive"}


@router.get("/health/ready", tags=["health"], summary="Readiness probe")
async def api_readiness():
    """Return readiness similar to /readyz with standardized shape."""
    r = await readyz()
    # readyz returns JSONResponse already; normalize body to include 'status'
    try:
        body = r.body  # bytes
        import json as _json
        data = _json.loads(body)
    except Exception:
        data = {"ready": False}
    status_txt = "ready" if data.get("ready") else "not_ready"
    return JSONResponse({"status": status_txt, **data}, status_code=(200 if data.get("ready") else 503))


@router.get("/health/metrics", tags=["health"], summary="System metrics (CPU/memory/disk)")
async def api_health_metrics():
    """Return basic system metrics for tests/diagnostics."""
    try:
        import psutil
        cpu = {
            "percent": float(psutil.cpu_percent(interval=0.1)),
        }
        vm = psutil.virtual_memory()
        du = psutil.disk_usage('/')
        mem = {
            "total": int(vm.total),
            "available": int(vm.available),
            "percent": float(vm.percent),
            "used": int(vm.used),
            "free": int(vm.free),
        }
        disk = {
            "total": int(du.total),
            "used": int(du.used),
            "free": int(du.free),
            "percent": float(du.percent),
        }
        return {"cpu": cpu, "memory": mem, "disk": disk}
    except Exception as e:
        logger.warning(f"health/metrics unavailable: {e}")
        return {"cpu": {"percent": 0.0}, "memory": {"total": 0, "available": 0, "percent": 0.0, "used": 0, "free": 0}, "disk": {"total": 0, "used": 0, "free": 0, "percent": 0.0}}


def _int_env(name: str, default: int) -> int:
    """Parse an environment variable into an int with a safe default."""
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning(f"Invalid integer for {name!r}: {value!r}. Using default {default}.")
        return default


def _calculate_security_status(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Derive human-readable security posture from the audit summary."""
    thresholds = {
        "critical_high_risk_min": _int_env("AUDIT_SEC_CRITICAL_HIGH_RISK_MIN", 1),
        "elevated_failure_min": _int_env("AUDIT_SEC_ELEVATED_FAILURE_MIN", 50),
    }
    high_risk = int(summary.get("high_risk_events") or 0)
    failures = int(summary.get("failure_events") or 0)

    risk_level = "low"
    status_text = "secure"

    if thresholds["critical_high_risk_min"] > 0 and high_risk >= thresholds["critical_high_risk_min"]:
        risk_level = "critical"
        status_text = "at_risk"
    elif thresholds["elevated_failure_min"] > 0 and failures >= thresholds["elevated_failure_min"]:
        risk_level = "high"
        status_text = "elevated"
    return {
        "risk_level": risk_level,
        "status": status_text,
        "thresholds": thresholds,
        "high_risk_events": high_risk,
        "failure_events": failures,
    }


@router.get("/health/security", tags=["health"], summary="Security posture overview")
async def api_security_health():
    """Summarize recent security audit activity and map to a risk posture."""
    response: Dict[str, Any] = {
        "timestamp": _utcnow_iso(),
        "risk_level": "unknown",
        "status": "unknown",
        "summary": {},
    }

    if UnifiedAuditService is None:
        response.update({
            "error": "UnifiedAuditService unavailable",
        })
        return JSONResponse(response, status_code=503)

    service_instance = None
    try:
        service_instance = UnifiedAuditService()  # type: ignore[operator]
        initialize = getattr(service_instance, "initialize", None)
        if callable(initialize):
            await initialize()
        summary = await service_instance.get_security_summary()  # type: ignore[assignment]
        response["summary"] = summary
        status_bits = _calculate_security_status(summary)
        response.update(status_bits)
    except Exception as exc:
        logger.error(f"health/security failed: {exc}")
        response.update({
            "error": str(exc),
        })
        return JSONResponse(response, status_code=503)
    finally:
        shutdown = getattr(service_instance, "stop", None)
        if callable(shutdown):
            try:
                await shutdown()
            except Exception as exc:
                logger.debug(f"UnifiedAuditService stop() ignored: {exc}")

    return JSONResponse(response, status_code=200)
