from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from loguru import logger

from tldw_Server_API.app.core.DB_Management.DB_Manager import create_workflows_database, get_content_backend_instance
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.Workflows.engine import WorkflowScheduler

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
