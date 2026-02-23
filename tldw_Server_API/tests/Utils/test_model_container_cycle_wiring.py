from pathlib import Path
import subprocess
import sys


def test_makefile_contains_model_cycle_target():
    text = Path("Makefile").read_text(encoding="utf-8")
    assert "model-cycle:" in text
    assert "Helper_Scripts/model_container_cycle.py" in text


def test_readme_mentions_model_cycle_usage():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "make model-cycle" in text


def test_model_container_cycle_script_help_runs():
    result = subprocess.run(
        [sys.executable, "Helper_Scripts/model_container_cycle.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--first-container" in result.stdout
