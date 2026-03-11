import json
from pathlib import Path

from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase


def test_workflows_db_crud(tmp_path):


    db_path = tmp_path / "workflows.db"
    db = WorkflowsDatabase(str(db_path))

    # Create definition
    defn = {
        "name": "demo",
        "version": 1,
        "steps": [
            {"id": "s1", "type": "prompt", "config": {"template": "Hi {{ inputs.name }}"}},
        ],
    }
    wid = db.create_definition(
        tenant_id="t1",
        name="demo",
        version=1,
        owner_id="1",
        visibility="private",
        description="",
        tags=["x"],
        definition=defn,
    )
    assert wid > 0

    d = db.get_definition(wid)
    assert d and d.name == "demo"

    lst = db.list_definitions(owner_id="1")
    assert any(x.id == wid for x in lst)

    # Create run
    run_id = "run-1"
    db.create_run(
        run_id=run_id,
        tenant_id="t1",
        user_id="1",
        inputs={"name": "Alice"},
        workflow_id=wid,
        definition_version=1,
        definition_snapshot=defn,
    )
    run = db.get_run(run_id)
    assert run and run.status == "queued"

    # Update status and events
    db.update_run_status(run_id, status="running")
    seq1 = db.append_event("t1", run_id, "run_started", {"mode": "async"})
    assert seq1 == 1
    seq2 = db.append_event("t1", run_id, "step_completed", {"step_id": "s1"})
    assert seq2 == 2
    events = db.get_events(run_id)
    assert [e["event_type"] for e in events] == ["run_started", "step_completed"]
    events_since = db.get_events(run_id, since=1)
    assert len(events_since) == 1 and events_since[0]["event_seq"] == 2


def test_workflows_db_step_attempt_crud(tmp_path):
    db_path = tmp_path / "workflows.db"
    db = WorkflowsDatabase(str(db_path))

    definition = {
        "name": "attempt-demo",
        "version": 1,
        "steps": [{"id": "s1", "type": "prompt", "config": {"template": "Hi"}}],
    }

    workflow_id = db.create_definition(
        tenant_id="tenant-1",
        name="attempt-demo",
        version=1,
        owner_id="owner-1",
        visibility="private",
        description="",
        tags=[],
        definition=definition,
    )

    db.create_run(
        run_id="run-attempt",
        tenant_id="tenant-1",
        user_id="owner-1",
        inputs={},
        workflow_id=workflow_id,
        definition_version=1,
        definition_snapshot=definition,
    )
    db.create_step_run(
        step_run_id="run-attempt:s1",
        tenant_id="tenant-1",
        run_id="run-attempt",
        step_id="s1",
        name="Step 1",
        step_type="prompt",
        status="running",
        inputs={"config": {"template": "Hi"}},
    )

    attempt_id = db.create_step_attempt(
        tenant_id="tenant-1",
        run_id="run-attempt",
        step_run_id="run-attempt:s1",
        step_id="s1",
        attempt_number=1,
        status="running",
        metadata={"source": "test"},
    )
    db.complete_step_attempt(
        attempt_id=attempt_id,
        status="failed",
        error_summary="forced_error",
        metadata={"source": "test", "result": "failed"},
    )

    attempts = db.list_step_attempts(run_id="run-attempt", step_id="s1")
    assert len(attempts) == 1
    assert attempts[0]["attempt_id"] == attempt_id
    assert attempts[0]["attempt_number"] == 1
    assert attempts[0]["status"] == "failed"
    assert attempts[0]["metadata_json"]["result"] == "failed"
