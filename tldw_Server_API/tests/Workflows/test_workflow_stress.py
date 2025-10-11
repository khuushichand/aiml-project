"""Stress scenarios for the workflow persistence/engine across both backends.

These tests are disabled by default and require the environment variable
`TLDW_WORKFLOW_STRESS=1`. They are intended for soak/performance checks rather
than routine CI execution.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Dict

import pytest

from tldw_Server_API.app.core.Workflows.engine import WorkflowEngine


RUN_STRESS = os.getenv("TLDW_WORKFLOW_STRESS") == "1"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.stress,
    pytest.mark.skipif(not RUN_STRESS, reason="workflow stress tests disabled by default"),
]


async def _start_run(engine: WorkflowEngine, db, run_id: str, definition: Dict[str, object]) -> None:
    db.create_run(
        run_id=run_id,
        tenant_id="stress-tenant",
        user_id="stress-user",
        inputs={"payload": run_id},
        workflow_id=definition["workflow_id"],
        definition_version=definition["version"],
        definition_snapshot=definition["snapshot"],
        idempotency_key=f"idem-{run_id}",
        session_id="stress-session",
    )
    await engine.start_run(run_id)


def _create_definition(db, name: str, steps: list[Dict[str, object]]) -> Dict[str, object]:
    definition_payload = {"name": name, "version": 1, "steps": steps}
    workflow_id = db.create_definition(
        tenant_id="stress-tenant",
        name=name,
        version=1,
        owner_id="stress-owner",
        visibility="private",
        description=f"Stress definition {name}",
        tags=["stress"],
        definition=definition_payload,
    )
    return {
        "workflow_id": workflow_id,
        "version": 1,
        "snapshot": definition_payload,
    }


@pytest.mark.asyncio
async def test_stress_run_creation_burst(workflows_dual_backend_db):
    backend_label, db = workflows_dual_backend_db

    definition = _create_definition(
        db,
        name=f"burst-{backend_label}",
        steps=[
            {"id": "prompt", "type": "prompt", "config": {"template": "hello {{ inputs.payload }}"}},
        ],
    )

    engine = WorkflowEngine(db)

    concurrency = 20
    total_runs = 60

    async def worker(offset: int) -> None:
        for idx in range(offset, total_runs, concurrency):
            run_id = f"burst-{backend_label}-{idx}-{uuid.uuid4().hex[:8]}"
            await _start_run(engine, db, run_id, definition)
            run = db.get_run(run_id)
            assert run is not None
            assert run.status in {"succeeded", "cancelled"} | {"failed"}

    await asyncio.gather(*(worker(n) for n in range(concurrency)))


def test_stress_step_heartbeat(workflows_dual_backend_db):
    backend_label, db = workflows_dual_backend_db
    definition = _create_definition(
        db,
        name=f"heartbeat-{backend_label}",
        steps=[{"id": "noop", "type": "prompt", "config": {"template": "noop"}}],
    )

    run_id = f"heartbeat-{backend_label}-{uuid.uuid4().hex[:8]}"
    db.create_run(
        run_id=run_id,
        tenant_id="stress-tenant",
        user_id="stress-user",
        inputs={},
        workflow_id=definition["workflow_id"],
        definition_version=definition["version"],
        definition_snapshot=definition["snapshot"],
        idempotency_key=f"hb-{run_id}",
        session_id="stress-session",
    )

    step_run_id = f"step-{uuid.uuid4().hex[:8]}"
    db.create_step_run(
        step_run_id=step_run_id,
        run_id=run_id,
        step_id="noop",
        name="Heartbeat",
        step_type="prompt",
        inputs={"config": {"prompt": "noop"}},
    )

    iterations = 400
    for attempt in range(iterations):
        db.update_step_attempt(step_run_id=step_run_id, attempt=attempt)
        db.update_step_lock_and_heartbeat(
            step_run_id=step_run_id,
            locked_by="stress",
            lock_ttl_seconds=5,
        )
        db.update_step_subprocess(
            step_run_id=step_run_id,
            pid=attempt,
            workdir=f"/tmp/{backend_label}/{attempt}",
        )
    db.complete_step_run(step_run_id=step_run_id, status="succeeded", outputs={"ok": True})

    run = db.get_run(run_id)
    assert run is not None
    orphaned = db.find_orphan_step_runs(time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()))
    assert isinstance(orphaned, list)


def test_stress_events_and_artifacts(workflows_dual_backend_db):
    backend_label, db = workflows_dual_backend_db
    definition = _create_definition(
        db,
        name=f"events-{backend_label}",
        steps=[],
    )

    run_id = f"events-{backend_label}-{uuid.uuid4().hex[:8]}"
    db.create_run(
        run_id=run_id,
        tenant_id="stress-tenant",
        user_id="stress-user",
        inputs={},
        workflow_id=definition["workflow_id"],
        definition_version=definition["version"],
        definition_snapshot=definition["snapshot"],
        idempotency_key=f"events-{run_id}",
        session_id="stress-session",
    )

    event_batches = 40
    events_per_batch = 50
    for batch in range(event_batches):
        for idx in range(events_per_batch):
            db.append_event(
                tenant_id="stress-tenant",
                run_id=run_id,
                event_type="stress_event",
                payload={"batch": batch, "item": idx},
            )

    artifacts = 200
    for idx in range(artifacts):
        db.add_artifact(
            artifact_id=f"artifact-{run_id}-{idx}",
            tenant_id="stress-tenant",
            run_id=run_id,
            step_run_id=None,
            type="blob",
            uri=f"s3://bucket/{run_id}/{idx}",
            size_bytes=idx,
            metadata={"origin": backend_label, "index": idx},
        )

    stored_events = db.get_events(run_id)
    assert len(stored_events) >= event_batches * events_per_batch
    artifact_list = db.list_artifacts_for_run(run_id)
    assert len(artifact_list) == artifacts
