from pathlib import Path
import re

import pytest


def _require(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


def _target_block(makefile_text: str, target: str) -> str:
    pattern = rf"^{re.escape(target)}:.*?(?=^[A-Za-z0-9_.-]+:|\Z)"
    match = re.search(pattern, makefile_text, flags=re.MULTILINE | re.DOTALL)
    _require(match is not None, f"Make target {target} should exist")
    return match.group(0)


def test_quickstart_target_delegates_to_webui_docker_path() -> None:
    text = Path("Makefile").read_text(encoding="utf-8")
    quickstart = _target_block(text, "quickstart")
    _require("quickstart-docker-webui" in quickstart, "quickstart should delegate to quickstart-docker-webui")


def test_quickstart_install_stays_on_local_dev_path() -> None:
    text = Path("Makefile").read_text(encoding="utf-8")
    quickstart_install = _target_block(text, "quickstart-install")
    quickstart_local = _target_block(text, "quickstart-local")
    _require("quickstart-local" in quickstart_install, "quickstart-install should still delegate to quickstart-local")
    _require("uvicorn" in quickstart_local, "quickstart-local should still start uvicorn")
