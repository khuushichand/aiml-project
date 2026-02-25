import uuid

import pytest

from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.Workflows import engine as engine_mod
from tldw_Server_API.app.core.Workflows.engine import _is_allowed_transition


def test_state_contract_rejects_invalid_transition() -> None:
    assert _is_allowed_transition("running", "queued") is False


@pytest.mark.asyncio
async def test_invalid_transition_sets_invariant_violation(tmp_path, monkeypatch) -> None:
    db = WorkflowsDatabase(str(tmp_path / "wf.db"))
    run_id = f"run-{uuid.uuid4().hex}"
    db.create_run(
        run_id=run_id,
        tenant_id="default",
        user_id="1",
        inputs={},
        workflow_id=None,
        definition_version=1,
        definition_snapshot={"name": "invalid-transition", "version": 1, "steps": []},
    )

    monkeypatch.setattr(engine_mod, "_is_allowed_transition", lambda *_: False)

    engine = engine_mod.WorkflowEngine(db)
    await engine.start_run(run_id)

    run = db.get_run(run_id)
    assert run is not None
    assert run.status == "failed"
    assert run.status_reason == "invariant_violation"

    events = db.get_events(run_id)
    rejected = [event for event in events if event["event_type"] == "transition_rejected"]
    assert rejected
