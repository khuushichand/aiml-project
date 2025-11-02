from tldw_Server_API.app.core.Metrics.metrics_manager import observe_histogram, increment_counter, get_metrics_registry


def test_phase_metrics_recording():
    # Just ensure recording does not raise and metric is registered
    observe_histogram("rag_phase_duration_seconds", 0.123, labels={"phase": "retrieval", "difficulty": "easy"})
    observe_histogram("rag_reranking_duration_seconds", 0.05, labels={"strategy": "two_tier"})
    increment_counter("rag_phase_budget_exhausted_total", 1, labels={"phase": "rerank_llm"})
    # Registry should have these metrics
    reg = get_metrics_registry()
    assert "rag_phase_duration_seconds" in reg.metrics
    assert "rag_reranking_duration_seconds" in reg.metrics
