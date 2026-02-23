from pathlib import Path


def test_makefile_contains_tooling_install_target():
    text = Path("Makefile").read_text(encoding="utf-8")
    assert "tooling-install:" in text
    assert ".[tooling]" in text


def test_readme_mentions_tooling_extra_install():
    text = Path("README.md").read_text(encoding="utf-8")
    assert 'pip install -e ".[tooling]"' in text
