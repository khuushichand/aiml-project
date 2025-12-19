import pytest

from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import UnifiedEvaluationService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("eval_type", "expected_sub_type"),
    [
        ("geval", "summarization"),
        ("rag", "rag"),
        ("response_quality", "response_quality"),
    ],
)
async def test_create_evaluation_maps_to_model_graded(tmp_path, eval_type, expected_sub_type):
    svc = UnifiedEvaluationService(db_path=str(tmp_path / "evals.db"), enable_webhooks=False)

    evaluation = await svc.create_evaluation(
        name=f"test_{eval_type}",
        eval_type=eval_type,
        eval_spec={"metrics": ["relevance"]},
        created_by="tester",
    )

    assert evaluation["eval_type"] == "model_graded"
    assert evaluation["eval_spec"].get("sub_type") == expected_sub_type
