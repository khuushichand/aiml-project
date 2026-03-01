from tldw_Server_API.app.core.Evaluations.benchmark_registry import BenchmarkRegistry


def test_registry_includes_bullshit_benchmark_by_default():
    reg = BenchmarkRegistry()
    assert "bullshit_benchmark" in reg.list_benchmarks()


def test_registry_creates_bullshit_evaluator():
    reg = BenchmarkRegistry()
    evaluator = reg.create_evaluator("bullshit_benchmark")
    assert evaluator is not None
    assert evaluator.__class__.__name__ == "BullshitDetectionEvaluation"
