"""Dual-backend smoke test for the WorkflowEngine runtime."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict

import pytest

from tldw_Server_API.app.core.Workflows.engine import WorkflowEngine


pytestmark = pytest.mark.integration


def _now_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


@pytest.mark.asyncio
async def test_engine_run_completes_on_both_backends(workflows_dual_backend_db) -> None:
    backend_label, db = workflows_dual_backend_db

    definition_body: Dict[str, object] = {
        "name": f"engine-smoke-{backend_label}",
        "version": 1,
        "steps": [],  # empty definition to exercise success path
    }

    workflow_id = db.create_definition(
        tenant_id="tenant-engine",
        name=str(definition_body["name"]),
        version=1,
        owner_id="owner-engine",
        visibility="private",
        description=None,
        tags=None,
        definition=definition_body,
    )

    run_id = f"engine-run-{backend_label}"
    db.create_run(
        run_id=run_id,
        tenant_id="tenant-engine",
        user_id="runner",
        inputs={},
        workflow_id=workflow_id,
        definition_version=1,
        definition_snapshot=definition_body,
        idempotency_key=f"idem-{backend_label}",
        session_id="session-engine",
    )

    engine = WorkflowEngine(db)
    await engine.start_run(run_id)

    run = db.get_run(run_id)
    assert run is not None
    assert run.status == "succeeded"

    events = db.get_events(run_id)
    assert events, "engine should record events"
    assert any(evt["event_type"] == "run_completed" for evt in events)
