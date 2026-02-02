import pytest

from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.Workflows.engine import WorkflowEngine, RunMode


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_tokens_cost_aggregated_across_steps(monkeypatch, tmp_path):
    async def _stub_llm_adapter(config, context):
        tag = config.get("tag")
        if tag == "a":
            return {"text": "A", "metadata": {"token_usage": {"prompt_tokens": 5, "completion_tokens": 2}, "cost_usd": 0.01}}
        return {"text": "B", "metadata": {"token_usage": {"input_tokens": 7, "output_tokens": 4}, "cost_usd": 0.02}}

    from tldw_Server_API.app.core.Workflows.adapters import registry
    spec = registry.get_spec("llm")
    assert spec is not None
    monkeypatch.setattr(spec, "func", _stub_llm_adapter)

    db = WorkflowsDatabase(str(tmp_path / "wf.db"))
    definition = {
        "name": "tokens-agg",
        "version": 1,
        "steps": [
            {"id": "s1", "type": "llm", "config": {"tag": "a"}},
            {"id": "s2", "type": "llm", "config": {"tag": "b"}},
        ],
    }
    run_id = "run-token-agg-int"
    db.create_run(
        run_id=run_id,
        tenant_id="default",
        user_id="user",
        inputs={},
        workflow_id=None,
        definition_version=1,
        definition_snapshot=definition,
    )

    engine = WorkflowEngine(db)
    await engine.start_run(run_id, RunMode.SYNC)

    run = db.get_run(run_id)
    assert run is not None
    assert run.status == "succeeded"
    assert run.tokens_input == 12
    assert run.tokens_output == 6
    assert float(run.cost_usd or 0.0) == pytest.approx(0.03)
