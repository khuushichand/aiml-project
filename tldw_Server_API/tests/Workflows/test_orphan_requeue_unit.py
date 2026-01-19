import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.Workflows.engine import WorkflowEngine


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_orphan_requeue_marks_step_and_resumes(monkeypatch, tmp_path):
    db = WorkflowsDatabase(str(tmp_path / "wf.db"))
    definition = {
        "name": "orphan-unit",
        "version": 1,
        "steps": [
            {"id": "s1", "type": "prompt", "config": {"template": "Alpha"}},
            {"id": "s2", "type": "prompt", "config": {"template": "Beta"}},
        ],
    }
    run_id = "run-orphan-unit"
    db.create_run(
        run_id=run_id,
        tenant_id="default",
        user_id="user",
        inputs={},
        workflow_id=None,
        definition_version=1,
        definition_snapshot=definition,
    )

    step1_run_id = f"{run_id}:s1:1"
    db.create_step_run(
        step_run_id=step1_run_id,
        tenant_id="default",
        run_id=run_id,
        step_id="s1",
        name="s1",
        step_type="prompt",
    )
    db.complete_step_run(step_run_id=step1_run_id, status="succeeded", outputs={"text": "Alpha"})

    step2_run_id = f"{run_id}:s2:2"
    db.create_step_run(
        step_run_id=step2_run_id,
        tenant_id="default",
        run_id=run_id,
        step_id="s2",
        name="s2",
        step_type="prompt",
    )
    old = (datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(seconds=120)).isoformat()
    db._conn.execute(
        "UPDATE workflow_step_runs SET heartbeat_at = ?, status = 'running' WHERE step_run_id = ?",
        (old, step2_run_id),
    )
    db._conn.commit()
    db.update_step_subprocess(
        step_run_id=step2_run_id,
        pid=123,
        pgid=456,
        workdir=str(tmp_path),
        stdout_path=str(tmp_path / "stdout.log"),
        stderr_path=str(tmp_path / "stderr.log"),
    )

    engine = WorkflowEngine(db)

    calls = {}

    async def _fake_continue(run_id, after_step_id, last_outputs=None, next_step_id=None):
        calls["run_id"] = run_id
        calls["after_step_id"] = after_step_id
        calls["last_outputs"] = last_outputs
        calls["next_step_id"] = next_step_id

    monkeypatch.setattr(engine, "continue_run", _fake_continue)

    term_calls = {}

    def _fake_terminate(task, grace_ms=5000):
        term_calls["pid"] = task.pid
        term_calls["pgid"] = task.pgid
        term_calls["grace_ms"] = grace_ms
        return True, False

    monkeypatch.setattr("tldw_Server_API.app.core.Workflows.subprocess_utils.terminate_process", _fake_terminate)

    await engine._reap_orphans()
    await asyncio.sleep(0)

    row = db._conn.cursor().execute(
        "SELECT status, error FROM workflow_step_runs WHERE step_run_id = ?",
        (step2_run_id,),
    ).fetchone()
    assert row is not None
    assert row[0] == "failed"
    assert row[1] == "orphan_reaped"

    assert term_calls["pid"] == 123
    assert term_calls["pgid"] == 456

    assert calls["run_id"] == run_id
    assert calls["after_step_id"] == "s1"
    assert calls["next_step_id"] == "s2"
    assert calls["last_outputs"] == {"text": "Alpha"}
