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


def test_unified_service_uses_backend_adapter_for_postgres_webhooks(monkeypatch, tmp_path):
    from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
    from tldw_Server_API.app.core.Evaluations import db_adapter as db_adapter_mod
    from tldw_Server_API.app.core.Evaluations import eval_runner as eval_runner_mod
    from tldw_Server_API.app.core.Evaluations import unified_evaluation_service as svc_mod
    from tldw_Server_API.app.core.Evaluations import webhook_manager as webhook_manager_mod

    class _FakeBackend:
        backend_type = BackendType.POSTGRESQL

    class _FakeDB:
        backend_type = BackendType.POSTGRESQL
        backend = _FakeBackend()

    class _DummyRunner:
        def __init__(self, _db_path):
            self.running_tasks = {}

    captured = {}
    sentinel_adapter = object()

    class _DummyWebhookManager:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs

    monkeypatch.setattr(eval_runner_mod, "EvaluationRunner", _DummyRunner)
    monkeypatch.setattr(svc_mod, "_create_evals_db", lambda db_path: _FakeDB())
    monkeypatch.setattr(
        db_adapter_mod,
        "create_adapter_from_backend",
        lambda backend: sentinel_adapter,
    )
    monkeypatch.setattr(webhook_manager_mod, "WebhookManager", _DummyWebhookManager)

    UnifiedEvaluationService(db_path=str(tmp_path / "evals.db"), enable_webhooks=True)

    kwargs = captured["kwargs"]
    assert kwargs.get("adapter") is sentinel_adapter
    assert "db_path" not in kwargs
