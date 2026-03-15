from pathlib import Path
import re

import pytest


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


def _target_block(makefile_text: str, target: str) -> str:
    pattern = rf"^{re.escape(target)}:.*?(?=^[A-Za-z0-9_.-]+:|\Z)"
    match = re.search(pattern, makefile_text, flags=re.MULTILINE | re.DOTALL)
    _require(match is not None, f"Make target {target} not found")
    return match.group(0)


def test_root_dockerignore_exists_and_excludes_large_local_paths():
    text = _read_text(".dockerignore")

    required_patterns = (
        ".venv/",
        ".git/",
        "Databases/",
        "apps/tldw-frontend/.next/",
        "apps/extension/tmp-playwright-profile/",
        "**/node_modules/",
    )

    for pattern in required_patterns:
        _require(pattern in text, f"Expected .dockerignore to contain: {pattern}")


def test_makefile_quickstart_docker_targets_use_opt_in_build_flag():
    text = _read_text("Makefile")

    _require("DOCKER_BUILD ?= false" in text, "Expected DOCKER_BUILD default to false")
    _require("DOCKER_BUILD_FLAG" in text, "Expected DOCKER_BUILD_FLAG helper definition")

    quickstart_docker = _target_block(text, "quickstart-docker")
    quickstart_webui = _target_block(text, "quickstart-docker-webui")

    _require("up -d $(DOCKER_BUILD_FLAG)" in quickstart_docker, "Expected opt-in build flag in quickstart-docker")
    _require(
        "up -d $(DOCKER_BUILD_FLAG)" in quickstart_webui,
        "Expected opt-in build flag in quickstart-docker-webui",
    )
    _require("--build" not in quickstart_docker, "Expected no hardcoded --build in quickstart-docker target")
    _require("--build" not in quickstart_webui, "Expected no hardcoded --build in quickstart-docker-webui target")


def test_api_dockerfile_avoids_expensive_copy_and_recursive_chown_layers():
    text = _read_text("Dockerfiles/Dockerfile.prod")

    _require("COPY Databases /app/Databases" not in text, "Expected Dockerfile.prod to avoid copying Databases")
    _require("chown -R appuser:appuser /app" not in text, "Expected Dockerfile.prod to avoid recursive chown")
    _require(
        "COPY --chown=appuser:appuser tldw_Server_API /app/tldw_Server_API" in text,
        "Expected Dockerfile.prod API copy to use --chown",
    )
    _require("RUN mkdir -p /app/Databases" in text, "Expected Dockerfile.prod to create /app/Databases")


def test_webui_dockerfile_uses_copy_chown_instead_of_recursive_chown():
    text = _read_text("Dockerfiles/Dockerfile.webui")

    _require("chown -R webui:webui /app" not in text, "Expected Dockerfile.webui to avoid recursive chown")
    _require(
        "COPY --from=builder --chown=webui:webui /app/apps/tldw-frontend/.next/standalone /app" in text,
        "Expected Dockerfile.webui standalone copy to use --chown",
    )


def test_webui_dockerfile_installs_only_frontend_and_ui_workspaces():
    text = _read_text("Dockerfiles/Dockerfile.webui")

    _require(
        "npm install --workspace tldw-frontend --workspace packages/ui --include-workspace-root" in text,
        "Expected Dockerfile.webui to scope npm install to frontend and shared ui workspaces",
    )
    _require(
        "npm install --workspaces --include-workspace-root" not in text,
        "Expected Dockerfile.webui to avoid installing all workspaces",
    )
