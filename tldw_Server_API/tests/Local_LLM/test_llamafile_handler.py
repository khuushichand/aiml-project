import asyncio
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Local_LLM.Llamafile_Handler import LlamafileHandler
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Schemas import LlamafileConfig


class DummyProcess:
    def __init__(self):
        self.pid = 22222
        self.returncode = None
        self.stdout = None
        self.stderr = None

    async def wait(self):
        return 0

    def terminate(self):
        self.returncode = 0


@pytest.mark.asyncio
async def test_llamafile_start_server_redacts_api_key(monkeypatch, tmp_path: Path):
    # Prepare directories and files
    llama_dir = tmp_path / "llamafile"
    model_dir = tmp_path / "models"
    llama_dir.mkdir()
    model_dir.mkdir()

    exe = llama_dir / ("llamafile" if not hasattr(asyncio, "WINDOWS") else "llamafile.exe")
    exe.write_text("#!/bin/sh\n")
    model = model_dir / "toy.gguf"
    model.write_text("fake")

    cfg = LlamafileConfig(
        llamafile_dir=llama_dir,
        models_dir=model_dir,
        default_host="127.0.0.1",
        default_port=8077,
    )
    handler = LlamafileHandler(cfg, global_app_config={})

    # Monkeypatch binary downloader to return our dummy exe path
    monkeypatch.setattr(handler, "download_latest_llamafile_executable", lambda force_download=False: asyncio.sleep(0, result=exe))
    # Stub process creation and readiness
    monkeypatch.setattr(asyncio, "create_subprocess_exec", lambda *a, **k: DummyProcess())
    from tldw_Server_API.app.core.Local_LLM import http_utils
    monkeypatch.setattr(http_utils, "wait_for_http_ready", lambda *a, **k: asyncio.sleep(0, result=True))

    res = await handler.start_server(model_filename=model.name, server_args={"port": 8077, "api_key": "supersecret"})
    assert res["status"] == "started"
    assert "REDACTED" in res["command"]
    assert "supersecret" not in res["command"]

