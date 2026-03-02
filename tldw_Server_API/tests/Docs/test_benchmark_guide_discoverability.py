from pathlib import Path


def test_benchmark_guide_exists_and_is_indexed() -> None:
    guide = Path("Docs/User_Guides/Server/Benchmark_Creation_API_WebUI_Extension_Guide.md")
    assert guide.exists()

    index_text = Path("Docs/User_Guides/index.md").read_text()
    assert "Benchmark_Creation_API_WebUI_Extension_Guide.md" in index_text


def test_benchmark_guide_mentions_api_and_webui_paths() -> None:
    text = Path(
        "Docs/User_Guides/Server/Benchmark_Creation_API_WebUI_Extension_Guide.md"
    ).read_text()
    assert "/api/v1/evaluations/benchmarks" in text
    assert "/api/v1/evaluations/benchmarks/{benchmark_name}/run" in text
    assert "benchmark-run" in text
