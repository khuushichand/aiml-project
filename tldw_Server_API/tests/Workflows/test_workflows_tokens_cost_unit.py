import json

import pytest

from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase


pytestmark = pytest.mark.unit


def test_aggregate_run_token_usage(tmp_path):
    db = WorkflowsDatabase(str(tmp_path / "wf.db"))
    run_id = "run-token-agg"
    db.create_run(
        run_id=run_id,
        tenant_id="default",
        user_id="user",
        inputs={},
        workflow_id=None,
        definition_version=1,
        definition_snapshot={"name": "agg", "version": 1, "steps": []},
    )

    step1 = f"{run_id}:s1:1"
    db.create_step_run(
        step_run_id=step1,
        tenant_id="default",
        run_id=run_id,
        step_id="s1",
        name="s1",
        step_type="llm",
    )
    db.complete_step_run(
        step_run_id=step1,
        status="succeeded",
        outputs={"metadata": {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}, "cost_usd": 0.02}},
    )

    step2 = f"{run_id}:s2:2"
    db.create_step_run(
        step_run_id=step2,
        tenant_id="default",
        run_id=run_id,
        step_id="s2",
        name="s2",
        step_type="llm",
    )
    db.complete_step_run(
        step_run_id=step2,
        status="failed",
        outputs={"metadata": {"token_usage": {"input_tokens": 3, "output_tokens": 7}, "cost_usd": "0.01"}},
    )

    tokens_in, tokens_out, cost_usd = db.aggregate_run_token_usage(run_id)
    assert tokens_in == 13
    assert tokens_out == 12
    assert cost_usd == pytest.approx(0.03)
