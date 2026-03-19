import re
from pathlib import Path

import pytest
import yaml


def _read_text(path: str) -> str:
    """Return a UTF-8 file body for assertions."""
    return Path(path).read_text(encoding="utf-8")


def _require(condition: bool, message: str) -> None:
    """Fail with a descriptive assertion message."""
    if not condition:
        pytest.fail(message)


def _target_block(makefile_text: str, target: str) -> str:
    """Return a Makefile target body or fail clearly."""
    pattern = rf"^{re.escape(target)}:.*?(?=^[A-Za-z0-9_.-]+:|\Z)"
    match = re.search(pattern, makefile_text, flags=re.MULTILINE | re.DOTALL)
    _require(match is not None, f"Make target {target} not found")
    return match.group(0)


def _load_yaml(path: str) -> dict:
    """Load a YAML file into a plain dictionary."""
    loaded = yaml.safe_load(_read_text(path))
    _require(isinstance(loaded, dict), f"Expected YAML document at {path} to be a mapping")
    return loaded


def test_root_dockerignore_exists_and_excludes_large_local_paths():
    """The Docker build context should exclude large local-only paths."""
    text = _read_text(".dockerignore")

    required_patterns = (
        ".venv/",
        ".git/",
        "Databases/",
        "docker-data/",
        "apps/tldw-frontend/.next/",
        "apps/extension/tmp-playwright-profile/",
        "**/node_modules/",
    )

    for pattern in required_patterns:
        _require(pattern in text, f"Expected .dockerignore to contain: {pattern}")


def test_root_gitignore_excludes_optional_host_storage_data():
    """Optional host-storage bind mounts should stay out of git."""
    text = _read_text(".gitignore")
    _require("docker-data/" in text, "Expected .gitignore to exclude docker-data/")


def test_makefile_quickstart_docker_targets_use_opt_in_build_flag():
    """Docker quickstart Make targets should keep build opt-in."""
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
    """The API Dockerfile should avoid heavyweight copy and chown steps."""
    text = _read_text("Dockerfiles/Dockerfile.prod")

    _require("COPY Databases /app/Databases" not in text, "Expected Dockerfile.prod to avoid copying Databases")
    _require("chown -R appuser:appuser /app" not in text, "Expected Dockerfile.prod to avoid recursive chown")
    _require(
        "COPY --chown=appuser:appuser tldw_Server_API /app/tldw_Server_API" in text,
        "Expected Dockerfile.prod API copy to use --chown",
    )
    _require("RUN mkdir -p /app/Databases" in text, "Expected Dockerfile.prod to create /app/Databases")


def test_webui_dockerfile_uses_copy_chown_instead_of_recursive_chown():
    """The WebUI Dockerfile should use targeted --chown copies."""
    text = _read_text("Dockerfiles/Dockerfile.webui")

    _require("chown -R webui:webui /app" not in text, "Expected Dockerfile.webui to avoid recursive chown")
    _require(
        "COPY --from=builder --chown=webui:webui /app/apps/tldw-frontend/.next/standalone /app" in text,
        "Expected Dockerfile.webui standalone copy to use --chown",
    )


def test_webui_dockerfile_installs_only_frontend_and_ui_workspaces():
    """The WebUI Docker build should avoid installing every workspace."""
    text = _read_text("Dockerfiles/Dockerfile.webui")

    _require(
        "npm install --workspace tldw-frontend --workspace packages/ui --include-workspace-root" in text,
        "Expected Dockerfile.webui to scope npm install to frontend and shared ui workspaces",
    )
    _require(
        "npm install --workspaces --include-workspace-root" not in text,
        "Expected Dockerfile.webui to avoid installing all workspaces",
    )


def test_base_docker_compose_keeps_backward_compatible_named_volumes():
    """The base compose file should preserve existing named volume identifiers."""
    compose = _load_yaml("Dockerfiles/docker-compose.yml")
    volumes = compose.get("volumes", {})
    _require(isinstance(volumes, dict), "Expected top-level volumes mapping in docker-compose.yml")

    for volume_name in ("app-data", "chroma-data", "postgres_data", "redis_data"):
        _require(volume_name in volumes, f"Expected docker-compose.yml to declare {volume_name}")


def test_app_service_keeps_split_databases_mounts():
    """The app service should keep the root and user-data mounts split."""
    compose = _load_yaml("Dockerfiles/docker-compose.yml")
    services = compose.get("services", {})
    _require(isinstance(services, dict), "Expected top-level services mapping in docker-compose.yml")
    app_service = services.get("app", {})
    _require(isinstance(app_service, dict), "Expected app service mapping in docker-compose.yml")
    app_volumes = app_service.get("volumes", [])
    _require(isinstance(app_volumes, list), "Expected app service volumes list in docker-compose.yml")

    _require(
        "app-data:/app/Databases" in app_volumes,
        "Expected app-data to back /app/Databases",
    )
    _require(
        "chroma-data:/app/Databases/user_databases" in app_volumes,
        "Expected chroma-data to back /app/Databases/user_databases",
    )


def test_docker_host_storage_overlay_uses_bind_mounts():
    """The optional host-storage overlay should bind-mount repo-visible paths."""
    overlay = _load_yaml("Dockerfiles/docker-compose.host-storage.yml")
    services = overlay.get("services", {})
    _require(isinstance(services, dict), "Expected services mapping in host-storage overlay")

    expected_mounts = {
        "app": "../docker-data/app:/app/Databases",
        "postgres": "../docker-data/postgres:/var/lib/postgresql/data",
        "redis": "../docker-data/redis:/data",
    }

    for service_name, expected_mount in expected_mounts.items():
        service = services.get(service_name, {})
        _require(isinstance(service, dict), f"Expected {service_name} service mapping in host-storage overlay")
        service_volumes = service.get("volumes", [])
        _require(
            isinstance(service_volumes, list),
            f"Expected {service_name} volumes list in host-storage overlay",
        )
        _require(
            expected_mount in service_volumes,
            f"Expected {service_name} to bind-mount {expected_mount}",
        )

    app_service = services.get("app", {})
    app_volumes = app_service.get("volumes", []) if isinstance(app_service, dict) else []
    _require(
        "../docker-data/user_data:/app/Databases/user_databases" in app_volumes,
        "Expected app service to bind-mount repo-visible user_data storage",
    )
