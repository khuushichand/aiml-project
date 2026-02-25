import pytest

from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.Workflows import engine as engine_mod
from tldw_Server_API.app.core.Workflows.engine import _is_retriable_error, _reason_code_from_error
from tldw_Server_API.app.core.exceptions import AdapterError


pytestmark = pytest.mark.unit


def test_retry_classifier_blocks_governance_errors():
    assert _is_retriable_error("acp_governance_blocked") is False


@pytest.mark.parametrize(
    "reason_code",
    [
        "validation_error",
        "authz_error",
        "session_access_denied",
        "invariant_violation",
    ],
)
def test_retry_classifier_blocks_non_retriable_reason_codes(reason_code: str):
    assert _is_retriable_error(reason_code) is False


def test_retry_classifier_allows_unknown_reason_codes():
    assert _is_retriable_error("transient_network_error") is True
    assert _is_retriable_error("acp_timeout") is True


def test_reason_code_extraction_normalizes_exception_messages():
    reason_code = _reason_code_from_error(AdapterError("ACP_GOVERNANCE_BLOCKED: policy violation"))
    assert reason_code == "acp_governance_blocked"
    assert _is_retriable_error(reason_code) is False


@pytest.mark.asyncio
async def test_non_retriable_reason_does_not_consume_retries(tmp_path, monkeypatch):
    db = WorkflowsDatabase(str(tmp_path / "wf.db"))
    run_id = "run-non-retry-governance"
    db.create_run(
        run_id=run_id,
        tenant_id="default",
        user_id="1",
        inputs={},
        workflow_id=None,
        definition_version=1,
        definition_snapshot={
            "name": "non-retry-governance",
            "version": 1,
            "steps": [{"id": "s1", "type": "prompt", "retry": 3, "config": {"template": "ok"}}],
        },
    )

    async def _blocked_adapter(_config, _context):
        raise AdapterError("acp_governance_blocked")

    monkeypatch.setattr(engine_mod, "get_adapter", lambda _step_type: _blocked_adapter)

    async def _fast_sleep(_duration: float):
        return None

    monkeypatch.setattr(engine_mod.asyncio, "sleep", _fast_sleep)

    engine = engine_mod.WorkflowEngine(db)
    await engine.start_run(run_id)

    run = db.get_run(run_id)
    assert run is not None
    assert run.status == "failed"
    assert run.status_reason == "acp_governance_blocked"

    row = db._conn.cursor().execute(
        "SELECT MAX(attempt) FROM workflow_step_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    assert row is not None
    assert int(row[0] or 0) == 1

    events = db.get_events(run_id)
    assert any(event.get("event_type") == "step_retry_suppressed" for event in events)


@pytest.mark.asyncio
async def test_retriable_reason_consumes_retry_attempts(tmp_path, monkeypatch):
    db = WorkflowsDatabase(str(tmp_path / "wf.db"))
    run_id = "run-retry-transient"
    db.create_run(
        run_id=run_id,
        tenant_id="default",
        user_id="1",
        inputs={},
        workflow_id=None,
        definition_version=1,
        definition_snapshot={
            "name": "retry-transient",
            "version": 1,
            "steps": [{"id": "s1", "type": "prompt", "retry": 2, "config": {"template": "ok"}}],
        },
    )

    async def _transient_adapter(_config, _context):
        raise RuntimeError("transient_network_error")

    monkeypatch.setattr(engine_mod, "get_adapter", lambda _step_type: _transient_adapter)

    async def _fast_sleep(_duration: float):
        return None

    monkeypatch.setattr(engine_mod.asyncio, "sleep", _fast_sleep)

    engine = engine_mod.WorkflowEngine(db)
    await engine.start_run(run_id)

    row = db._conn.cursor().execute(
        "SELECT MAX(attempt) FROM workflow_step_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    assert row is not None
    assert int(row[0] or 0) == 3
