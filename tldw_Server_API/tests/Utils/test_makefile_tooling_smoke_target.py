from pathlib import Path


def test_makefile_contains_tooling_smoke_target():
    text = Path("Makefile").read_text(encoding="utf-8")
    assert "tooling-smoke:" in text
