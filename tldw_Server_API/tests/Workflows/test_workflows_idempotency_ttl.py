from datetime import datetime, timedelta, timezone

import pytest

from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase


pytestmark = pytest.mark.unit


def test_workflow_idempotency_ttl_expiry(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKFLOWS_IDEMPOTENCY_TTL_HOURS", "24")
    db = WorkflowsDatabase(str(tmp_path / "wf.db"))

    run_id_old = "run-idem-old"
    db.create_run(
        run_id=run_id_old,
        tenant_id="default",
        user_id="user",
        inputs={},
        workflow_id=None,
        definition_version=1,
        definition_snapshot={"name": "idem", "version": 1, "steps": []},
        idempotency_key="idem-key",
    )
    found = db.get_run_by_idempotency("default", "user", "idem-key")
    assert found is not None
    assert found.run_id == run_id_old

    old_ts = (datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(hours=25)).isoformat()
    db._conn.execute(
        "UPDATE workflow_runs SET created_at = ? WHERE run_id = ?",
        (old_ts, run_id_old),
    )
    db._conn.commit()

    expired = db.get_run_by_idempotency("default", "user", "idem-key")
    assert expired is None

    run_id_new = "run-idem-new"
    db.create_run(
        run_id=run_id_new,
        tenant_id="default",
        user_id="user",
        inputs={},
        workflow_id=None,
        definition_version=1,
        definition_snapshot={"name": "idem", "version": 1, "steps": []},
        idempotency_key="idem-key",
    )
    refreshed = db.get_run_by_idempotency("default", "user", "idem-key")
    assert refreshed is not None
    assert refreshed.run_id == run_id_new
