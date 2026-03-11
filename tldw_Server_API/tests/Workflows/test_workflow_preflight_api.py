import importlib.machinery
import sys
import types

import pytest
from fastapi.testclient import TestClient

# Stub heavyweight audio deps before app import for local test stability.
if "torch" not in sys.modules:
    _fake_torch = types.ModuleType("torch")
    _fake_torch.__spec__ = importlib.machinery.ModuleSpec("torch", loader=None)
    _fake_torch.Tensor = object
    _fake_torch.nn = types.SimpleNamespace(Module=object)
    sys.modules["torch"] = _fake_torch

if "faster_whisper" not in sys.modules:
    _fake_fw = types.ModuleType("faster_whisper")
    _fake_fw.__spec__ = importlib.machinery.ModuleSpec("faster_whisper", loader=None)

    class _StubWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

    _fake_fw.WhisperModel = _StubWhisperModel
    _fake_fw.BatchedInferencePipeline = _StubWhisperModel
    sys.modules["faster_whisper"] = _fake_fw

if "transformers" not in sys.modules:
    _fake_tf = types.ModuleType("transformers")
    _fake_tf.__spec__ = importlib.machinery.ModuleSpec("transformers", loader=None)

    class _StubProcessor:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

    class _StubModel:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

    _fake_tf.AutoProcessor = _StubProcessor
    _fake_tf.Qwen2AudioForConditionalGeneration = _StubModel
    sys.modules["transformers"] = _fake_tf

from tldw_Server_API.app.main import app
from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_for_preflight(tmp_path, auth_headers):
    db = WorkflowsDatabase(str(tmp_path / "wf.db"))

    async def override_user():
        return User(
            id=1,
            username="tester",
            email="tester@example.com",
            is_active=True,
            is_admin=True,
            tenant_id="default",
            roles=["admin"],
        )

    def override_db():
        return db

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[wf_mod._get_db] = override_db

    with TestClient(app, headers=auth_headers) as client:
        yield client

    app.dependency_overrides.clear()


def test_preflight_reports_blocking_validation_errors(client_for_preflight: TestClient):
    resp = client_for_preflight.post(
        "/api/v1/workflows/preflight",
        json={
            "definition": {
                "name": "bad-preflight",
                "version": 1,
                "steps": [{"id": "s1", "type": "wait_for_human", "config": {}}],
            }
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["valid"] is False
    assert data["errors"][0]["code"] == "definition_invalid"
    assert "assigned_to_user_id" in data["errors"][0]["message"]


def test_preflight_demotes_validation_errors_in_non_block_mode(client_for_preflight: TestClient):
    resp = client_for_preflight.post(
        "/api/v1/workflows/preflight",
        json={
            "validation_mode": "non-block",
            "definition": {
                "name": "warn-preflight",
                "version": 1,
                "steps": [{"id": "s1", "type": "wait_for_human", "config": {}}],
            },
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["valid"] is True
    assert data["errors"] == []
    assert data["warnings"][0]["code"] == "definition_validation_warning"


def test_preflight_flags_unsafe_replay_steps(client_for_preflight: TestClient):
    resp = client_for_preflight.post(
        "/api/v1/workflows/preflight",
        json={
            "definition": {
                "name": "unsafe-replay",
                "version": 1,
                "steps": [{"id": "s1", "type": "webhook", "config": {"url": "https://example.invalid/hook"}}],
            }
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["valid"] is True
    assert any(warning["code"] == "unsafe_replay_step" for warning in data["warnings"])
