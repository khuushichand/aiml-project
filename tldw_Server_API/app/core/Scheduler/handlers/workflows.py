"""
Scheduler task handlers for Workflows integration.

Registers a `workflow_run` task that can be scheduled or enqueued to
start a workflow run from the internal Workflows engine.

Location: tldw_Server_API/app/core/Scheduler/handlers/workflows.py
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional
from loguru import logger

from tldw_Server_API.app.core.Scheduler.base.registry import task
from tldw_Server_API.app.core.Workflows.engine import WorkflowEngine, RunMode
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.DB_Management.DB_Manager import (
    create_workflows_database,
    get_content_backend_instance,
)


def _get_wf_db() -> WorkflowsDatabase:
    backend = get_content_backend_instance()
    return create_workflows_database(backend=backend)


@task(name="workflow_run", max_retries=0, timeout=3600, queue="workflows")
async def workflow_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Scheduler handler that enqueues/executes a Workflows run.

    Expected payload keys:
      - workflow_id: int (optional if definition_snapshot provided)
      - inputs: dict
      - user_id: str (owner of the run; used for RBAC/attribution)
      - tenant_id: str (optional; defaults to 'default')
      - mode: 'async'|'sync' (default 'async')
      - validation_mode: 'block'|'non-block' (default 'block')
      - definition_snapshot: dict (optional; ad-hoc run definition)
      - secrets: dict[str,str] (optional; injected ephemerally into engine context)

    Returns:
      { "run_id": str, "status": "queued"|terminal, "succeeded": bool | None }
    """
    db = _get_wf_db()

    # Validate payload minimal shape
    inputs = payload.get("inputs") or {}
    if not isinstance(inputs, dict):
        raise ValueError("workflow_run: inputs must be a dict")

    user_id = str(payload.get("user_id") or "1")
    tenant_id = str(payload.get("tenant_id") or "default")
    workflow_id = payload.get("workflow_id")
    definition_snapshot = payload.get("definition_snapshot")
    if workflow_id is None and not definition_snapshot:
        raise ValueError("workflow_run: must provide workflow_id or definition_snapshot")

    run_mode = str(payload.get("mode") or "async").lower()
    mode = RunMode.SYNC if run_mode == "sync" else RunMode.ASYNC
    validation_mode = str(payload.get("validation_mode") or "block")

    # Create run
    run_id = __import__("uuid").uuid4().hex
    try:
        db.create_run(
            run_id=run_id,
            tenant_id=tenant_id,
            user_id=user_id,
            inputs=inputs,
            workflow_id=int(workflow_id) if workflow_id is not None else None,
            definition_version=None,
            definition_snapshot=definition_snapshot,
            idempotency_key=None,
            session_id=None,
            validation_mode=validation_mode,
        )
    except Exception as e:
        logger.error(f"workflow_run: failed to create run: {e}")
        raise

    # Inject secrets ephemerally
    secrets = payload.get("secrets")
    try:
        if isinstance(secrets, dict):
            WorkflowEngine.set_run_secrets(run_id, secrets)  # ephemeral; cleared on terminal state
    except Exception:
        pass

    # Submit to engine (respect internal concurrency scheduler)
    engine = WorkflowEngine(db=db)
    engine.submit(run_id, mode=mode)

    # Optionally wait for terminal state when mode=sync
    if mode == RunMode.SYNC:
        # Poll for completion with backoff (bounded by task timeout)
        deadline = __import__("time").time() + 55 * 60  # 55m safety within 60m timeout
        status: Optional[str] = None
        while __import__("time").time() < deadline:
            r = db.get_run(run_id)
            status = r.status if r else None
            if status in {"succeeded", "failed", "cancelled"}:
                break
            await asyncio.sleep(0.5)
        succeeded = status == "succeeded"
        return {"run_id": run_id, "status": status or "unknown", "succeeded": succeeded}

    return {"run_id": run_id, "status": "queued"}
