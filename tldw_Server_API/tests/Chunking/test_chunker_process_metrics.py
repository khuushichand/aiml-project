from tldw_Server_API.app.core.Chunking.chunker import Chunker
from tldw_Server_API.app.core.Metrics import get_metrics_registry


def test_chunker_process_metrics_registered_and_recorded():
    registry = get_metrics_registry()
    metric_names = [
        "chunker_process_total",
        "chunker_frontmatter_duration_seconds",
        "chunker_header_extract_seconds",
        "chunker_chunking_duration_seconds",
        "chunker_normalization_seconds",
        "chunker_last_chunk_count",
        "chunker_output_bytes",
        "chunker_input_bytes",
        "chunker_process_total_seconds",
    ]

    for name in metric_names:
        assert name in registry.metrics
        registry.values[name].clear()

    chunker = Chunker()
    chunker.process_text("One sentence for metrics.")

    for name in metric_names:
        assert registry.values[name], f"Expected metric samples for {name}"
