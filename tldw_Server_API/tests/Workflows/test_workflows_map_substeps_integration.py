import json

import pytest

from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.Workflows.engine import WorkflowEngine, RunMode


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_map_adapter_supported_substep(tmp_path):
    db = WorkflowsDatabase(str(tmp_path / "wf.db"))
    definition = {
        "name": "map-substeps",
        "version": 1,
        "steps": [
            {
                "id": "map1",
                "type": "map",
                "config": {
                    "items": [1, 2],
                    "step": {"type": "prompt", "config": {"template": "Item {{ item }}"}},
                    "concurrency": 2,
                },
            }
        ],
    }
    run_id = "run-map-substeps"
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
    outputs = json.loads(run.outputs_json or "{}")
    assert outputs.get("count") == 2
    results = outputs.get("results") or []
    assert results and results[0].get("text") == "Item 1"
