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


def test_workflow_research_wait_db_tracks_links(tmp_path):
    db_path = tmp_path / "workflows.db"
    db = WorkflowsDatabase(str(db_path))

    db.create_run(
        run_id="wf-run-1",
        tenant_id="tenant",
        user_id="user",
        inputs={},
        workflow_id=None,
        definition_version=1,
        definition_snapshot={"name": "wait-link", "steps": []},
    )

    db.upsert_research_wait_link(
        wait_id="rw-1",
        tenant_id="tenant",
        workflow_run_id="wf-run-1",
        step_id="wait",
        research_run_id="research-session-10",
        checkpoint_id="checkpoint-4",
        checkpoint_type="sources_review",
        wait_status="waiting",
        wait_payload={
            "__status__": "waiting_human",
            "reason": "research_checkpoint",
            "run_id": "research-session-10",
        },
        active_poll_seconds=1.25,
    )

    link = db.get_research_wait_link(workflow_run_id="wf-run-1", step_id="wait")
    assert link is not None
    assert link["research_run_id"] == "research-session-10"
    assert link["checkpoint_id"] == "checkpoint-4"
    assert link["wait_status"] == "waiting"
    assert json.loads(link["wait_payload_json"])["reason"] == "research_checkpoint"


def test_workflow_research_wait_db_claims_links_for_resume_once(tmp_path):
    db_path = tmp_path / "workflows.db"
    db = WorkflowsDatabase(str(db_path))

    db.create_run(
        run_id="wf-run-2",
        tenant_id="tenant",
        user_id="user",
        inputs={},
        workflow_id=None,
        definition_version=1,
        definition_snapshot={"name": "wait-claim", "steps": []},
    )

    db.upsert_research_wait_link(
        wait_id="rw-2",
        tenant_id="tenant",
        workflow_run_id="wf-run-2",
        step_id="wait",
        research_run_id="research-session-11",
        checkpoint_id="checkpoint-5",
        checkpoint_type="outline_review",
        wait_status="waiting",
        wait_payload={
            "__status__": "waiting_human",
            "reason": "research_checkpoint",
            "run_id": "research-session-11",
        },
        active_poll_seconds=2.0,
    )

    claimed = db.claim_research_waits_for_resume(
        research_run_id="research-session-11",
        checkpoint_id="checkpoint-5",
    )
    assert len(claimed) == 1
    assert claimed[0]["workflow_run_id"] == "wf-run-2"
    assert claimed[0]["step_id"] == "wait"

    claimed_again = db.claim_research_waits_for_resume(
        research_run_id="research-session-11",
        checkpoint_id="checkpoint-5",
    )
    assert claimed_again == []
