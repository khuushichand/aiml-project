import base64
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.Image_Generation import adapter_registry as image_registry
from tldw_Server_API.app.core.Image_Generation.adapters.base import ImageGenResult


pytestmark = pytest.mark.integration

BASE_OPTIONS = {"persist": True}


class MockImageAdapter:
    name = "stable_diffusion_cpp"
    supported_formats = {"png", "jpg", "webp"}
    content: bytes = b"test-image"

    def generate(self, request):
        fmt = request.format
        content_type = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "webp": "image/webp",
        }[fmt]
        return ImageGenResult(content=self.content, content_type=content_type, bytes_len=len(self.content))


class MockSwarmUIImageAdapter:
    name = "swarmui"
    supported_formats = {"png", "jpg"}
    content: bytes = b"swarm-image"

    def generate(self, request):
        fmt = request.format
        content_type = {
            "png": "image/png",
            "jpg": "image/jpeg",
        }[fmt]
        return ImageGenResult(content=self.content, content_type=content_type, bytes_len=len(self.content))


@pytest.fixture()
def mock_image_registry(monkeypatch):
    registry = image_registry.ImageAdapterRegistry(
        config_override={
            "default_backend": "stable_diffusion_cpp",
            "enabled_backends": ["stable_diffusion_cpp"],
        }
    )
    registry.register_adapter("stable_diffusion_cpp", MockImageAdapter)
    monkeypatch.setattr(image_registry, "_registry", registry)
    yield registry
    image_registry.reset_registry()


@pytest.fixture()
def mock_swarmui_registry(monkeypatch):
    registry = image_registry.ImageAdapterRegistry(
        config_override={
            "default_backend": "swarmui",
            "enabled_backends": ["swarmui"],
        }
    )
    registry.register_adapter("swarmui", MockSwarmUIImageAdapter)
    monkeypatch.setattr(image_registry, "_registry", registry)
    yield registry
    image_registry.reset_registry()


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=321, username="tester", email=None, is_active=True)

    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_files_image"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    app = None
    try:
        from importlib import import_module, reload

        mod = import_module("tldw_Server_API.app.main")
        mod = reload(mod)
        app = mod.app
        app.dependency_overrides[get_request_user] = override_user
        with TestClient(app) as client:
            yield client
    finally:
        if app is not None:
            app.dependency_overrides.clear()
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_create_image_inline_export(client_with_user, mock_image_registry):
    MockImageAdapter.content = b"image-bytes"
    payload = {
        "file_type": "image",
        "title": "Mock",
        "payload": {
            "backend": "stable_diffusion_cpp",
            "prompt": "A test image",
        },
        "export": {"format": "png", "mode": "inline", "async_mode": "sync"},
        "options": BASE_OPTIONS,
    }
    response = client_with_user.post("/api/v1/files/create", json=payload)
    assert response.status_code == 200, response.text
    artifact = response.json()["artifact"]
    assert artifact["file_type"] == "image"
    export = artifact["export"]
    assert export["status"] == "none"
    assert export["format"] == "png"
    assert export["content_type"] == "image/png"
    assert export["content_b64"]
    assert base64.b64decode(export["content_b64"]) == MockImageAdapter.content


def test_create_image_inline_export_swarmui(client_with_user, mock_swarmui_registry):
    MockSwarmUIImageAdapter.content = b"swarm-bytes"
    payload = {
        "file_type": "image",
        "title": "Swarm",
        "payload": {
            "backend": "swarmui",
            "prompt": "A test image",
        },
        "export": {"format": "jpg", "mode": "inline", "async_mode": "sync"},
        "options": BASE_OPTIONS,
    }
    response = client_with_user.post("/api/v1/files/create", json=payload)
    assert response.status_code == 200, response.text
    artifact = response.json()["artifact"]
    assert artifact["file_type"] == "image"
    export = artifact["export"]
    assert export["status"] == "none"
    assert export["format"] == "jpg"
    assert export["content_type"] == "image/jpeg"
    assert export["content_b64"]
    assert base64.b64decode(export["content_b64"]) == MockSwarmUIImageAdapter.content


def test_image_export_mode_url_rejected(client_with_user, mock_image_registry):
    payload = {
        "file_type": "image",
        "payload": {
            "backend": "stable_diffusion_cpp",
            "prompt": "A test image",
        },
        "export": {"format": "png", "mode": "url", "async_mode": "sync"},
        "options": BASE_OPTIONS,
    }
    response = client_with_user.post("/api/v1/files/create", json=payload)
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "invalid_export_mode"


def test_image_inline_size_exceeded(client_with_user, mock_image_registry, monkeypatch):
    from tldw_Server_API.app.core.File_Artifacts import file_artifacts_service as fas

    original_get_config_value = fas.get_config_value

    def _fake_get_config_value(section, key, default=None, *, reload=False):
        if section == "Image-Generation" and key == "inline_max_bytes":
            return "4"
        return original_get_config_value(section, key, default, reload=reload)

    monkeypatch.setattr(fas, "get_config_value", _fake_get_config_value)

    MockImageAdapter.content = b"toolarge"
    payload = {
        "file_type": "image",
        "payload": {
            "backend": "stable_diffusion_cpp",
            "prompt": "A test image",
        },
        "export": {"format": "png", "mode": "inline", "async_mode": "sync"},
        "options": BASE_OPTIONS,
    }
    response = client_with_user.post("/api/v1/files/create", json=payload)
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "export_size_exceeded"


def test_image_extra_params_rejected_when_not_allowlisted(client_with_user, mock_image_registry, monkeypatch):
    from tldw_Server_API.app.core.File_Artifacts.adapters import image_adapter as image_adapter_module
    from tldw_Server_API.app.core.Image_Generation import config as image_config

    cfg = image_config.get_image_generation_config(reload=True)
    cfg = replace(cfg, sd_cpp_allowed_extra_params=[])
    monkeypatch.setattr(image_adapter_module, "get_image_generation_config", lambda: cfg)

    payload = {
        "file_type": "image",
        "payload": {
            "backend": "stable_diffusion_cpp",
            "prompt": "A test image",
            "extra_params": {"clip_skip": 2},
        },
        "export": {"format": "png", "mode": "inline", "async_mode": "sync"},
        "options": BASE_OPTIONS,
    }
    response = client_with_user.post("/api/v1/files/create", json=payload)
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    errors = detail.get("errors", [])
    assert any(error.get("code") == "image_params_invalid" for error in errors)
    assert any(error.get("path") == "extra_params.clip_skip" for error in errors)


def test_image_extra_params_allowed_when_allowlisted(client_with_user, mock_image_registry, monkeypatch):
    from tldw_Server_API.app.core.File_Artifacts.adapters import image_adapter as image_adapter_module
    from tldw_Server_API.app.core.Image_Generation import config as image_config

    cfg = image_config.get_image_generation_config(reload=True)
    cfg = replace(cfg, sd_cpp_allowed_extra_params=["clip_skip"])
    monkeypatch.setattr(image_adapter_module, "get_image_generation_config", lambda: cfg)

    payload = {
        "file_type": "image",
        "payload": {
            "backend": "stable_diffusion_cpp",
            "prompt": "A test image",
            "extra_params": {"clip_skip": 2},
        },
        "export": {"format": "png", "mode": "inline", "async_mode": "sync"},
        "options": BASE_OPTIONS,
    }
    response = client_with_user.post("/api/v1/files/create", json=payload)
    assert response.status_code == 200, response.text
