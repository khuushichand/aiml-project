import os

os.environ.setdefault("LOGURU_LEVEL", "ERROR")
os.environ.setdefault("TLDW_TEST_MODE", "true")
os.environ.setdefault("SINGLE_USER_API_KEY", "test-key")

from loguru import logger

logger.remove()

import asyncio
import time
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Workflows.engine import WorkflowEngine, WorkflowScheduler, RunMode
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.api.v1.schemas.workflows import RunRequest
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.api.v1.endpoints.workflows import run_saved


TERMINAL_STATES = {"succeeded", "failed", "cancelled"}


@pytest.fixture(autouse=True)
def reset_engine_state(monkeypatch):
    WorkflowScheduler._inst = None
    WorkflowEngine._RUN_SECRETS.clear()
    yield
    WorkflowScheduler._inst = None
    WorkflowEngine._RUN_SECRETS.clear()


@pytest.fixture
def workflows_db(tmp_path: Path):
    db_path = tmp_path / "workflows.db"
    db = WorkflowsDatabase(db_path=str(db_path))
    try:
        yield db
    finally:
        try:
            db._conn.close()
        except Exception:
            pass


def _wait_for_status(db: WorkflowsDatabase, run_id: str, timeout: float = 3.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = db.get_run(run_id)
        if run and run.status in TERMINAL_STATES.union({"waiting_human", "waiting_approval"}):
            return run.status
        time.sleep(0.05)
    raise AssertionError("Run did not reach a terminal or waiting state within the timeout")


def test_scheduler_releases_slot_on_step_failure(workflows_db: WorkflowsDatabase):
    scheduler = WorkflowScheduler.instance()
    definition = {
        "name": "force-failure",
        "steps": [
            {
                "id": "step1",
                "type": "prompt",
                "config": {"template": "oops", "force_error": True},
            }
        ],
    }
    run_id = "fail-run"
    workflows_db.create_run(
        run_id=run_id,
        tenant_id="tenant",
        user_id="user",
        inputs={},
        workflow_id=None,
        definition_version=1,
        definition_snapshot=definition,
    )
    engine = WorkflowEngine(workflows_db)
    engine.submit(run_id, RunMode.ASYNC)

    status = _wait_for_status(workflows_db, run_id)
    assert status == "failed"

    stats = scheduler.stats()
    assert stats["active_tenants"] == 0
    assert stats["active_workflows"] == 0
    assert scheduler.queue_depth() == 0


def test_waiting_run_keeps_secrets_and_releases_slot(workflows_db: WorkflowsDatabase):
    scheduler = WorkflowScheduler.instance()
    definition = {
        "name": "await-approval",
        "steps": [
            {
                "id": "wait",
                "type": "wait_for_human",
                "config": {},
                "on_success": "next",
            },
            {"id": "next", "type": "log", "config": {"message": "done"}},
        ],
    }
    run_id = "wait-run"
    workflows_db.create_run(
        run_id=run_id,
        tenant_id="tenant",
        user_id="user",
        inputs={},
        workflow_id=None,
        definition_version=1,
        definition_snapshot=definition,
    )
    WorkflowEngine.set_run_secrets(run_id, {"token": "secret"})
    engine = WorkflowEngine(workflows_db)
    engine.submit(run_id, RunMode.ASYNC)

    status = _wait_for_status(workflows_db, run_id)
    assert status == "waiting_human"
    assert WorkflowEngine._RUN_SECRETS.get(run_id) is not None

    stats = scheduler.stats()
    assert stats["active_tenants"] == 0
    assert stats["active_workflows"] == 0


def test_continue_run_clears_secrets(workflows_db: WorkflowsDatabase):
    scheduler = WorkflowScheduler.instance()
    definition = {
        "name": "resume-flow",
        "steps": [
            {
                "id": "wait",
                "type": "wait_for_human",
                "config": {},
                "on_success": "next",
            },
            {"id": "next", "type": "log", "config": {"message": "finished"}},
        ],
    }
    run_id = "resume-run"
    workflows_db.create_run(
        run_id=run_id,
        tenant_id="tenant",
        user_id="user",
        inputs={},
        workflow_id=None,
        definition_version=1,
        definition_snapshot=definition,
    )
    WorkflowEngine.set_run_secrets(run_id, {"token": "secret"})
    engine = WorkflowEngine(workflows_db)
    engine.submit(run_id, RunMode.ASYNC)
    status = _wait_for_status(workflows_db, run_id)
    assert status == "waiting_human"

    asyncio.run(engine.continue_run(run_id, after_step_id="wait", last_outputs={"approved": True}))

    status = _wait_for_status(workflows_db, run_id)
    assert status == "succeeded"
    assert WorkflowEngine._RUN_SECRETS.get(run_id) is None
    stats = scheduler.stats()
    assert stats["active_tenants"] == 0
    assert stats["active_workflows"] == 0


def test_run_saved_sync_waits_for_completion(workflows_db: WorkflowsDatabase, monkeypatch):
    definition_doc = {
        "name": "sync-run",
        "steps": [{"id": "log", "type": "log", "config": {"message": "hi"}}],
    }
    workflow_id = workflows_db.create_definition(
        tenant_id="tenant",
        name="sync-run",
        version=1,
        owner_id="user",
        visibility="private",
        description=None,
        tags=None,
        definition=definition_doc,
    )
    user = User(id="user", username="tester", tenant_id="tenant")
    request_body = RunRequest(inputs={})
    response = asyncio.run(
        run_saved(
            workflow_id=workflow_id,
            mode="sync",
            request=None,
            body=request_body,
            current_user=user,
            db=workflows_db,
            audit_service=None,
        )
    )
    assert response.status == "succeeded"
    stats = WorkflowScheduler.instance().stats()
    assert stats["active_tenants"] == 0
    assert stats["active_workflows"] == 0
