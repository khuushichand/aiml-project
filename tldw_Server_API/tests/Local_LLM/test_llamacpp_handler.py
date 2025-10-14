import asyncio
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Local_LLM.LlamaCpp_Handler import LlamaCppHandler
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Schemas import LlamaCppConfig
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions import ServerError


class DummyProcess:
    def __init__(self):
        self.pid = 12345
        self.returncode = None
        self.stdout = None
        self.stderr = None

    async def wait(self):
        return 0

    def terminate(self):
        self.returncode = 0


@pytest.mark.asyncio
async def test_llamacpp_start_server_with_readiness(monkeypatch, tmp_path: Path):
    # Setup dummy executable and model
    exe = tmp_path / "llama_server"
    exe.write_text("#!/bin/sh\n")
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    model = model_dir / "toy.gguf"
    model.write_text("fake")

    cfg = LlamaCppConfig(
        executable_path=exe,
        models_dir=model_dir,
        default_host="127.0.0.1",
        default_port=8099,
    )
    handler = LlamaCppHandler(cfg, global_app_config={})

    # Stub subprocess and readiness
    monkeypatch.setattr(asyncio, "create_subprocess_exec", lambda *a, **k: DummyProcess())
    from tldw_Server_API.app.core.Local_LLM import http_utils

    monkeypatch.setattr(http_utils, "wait_for_http_ready", lambda *a, **k: asyncio.sleep(0, result=True))

    res = await handler.start_server(model.name, server_args={"port": 8099})
    assert res["status"] == "started"
    assert res["port"] == 8099


@pytest.mark.asyncio
async def test_llamacpp_inference_requires_running_server(tmp_path: Path):
    exe = tmp_path / "llama_server"
    exe.write_text("#!/bin/sh\n")
    model_dir = tmp_path / "models"
    model_dir.mkdir()

    cfg = LlamaCppConfig(
        executable_path=exe,
        models_dir=model_dir,
        default_host="127.0.0.1",
        default_port=8099,
    )
    handler = LlamaCppHandler(cfg, global_app_config={})

    with pytest.raises(ServerError):
        await handler.inference(prompt="hi")

