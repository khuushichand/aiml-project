import asyncio
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Local_LLM.Llamafile_Handler import LlamafileHandler
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Schemas import LlamafileConfig
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions import ServerError


class DummyProc:
    def __init__(self):
        self.pid = 400
        self.returncode = None
        self.stdout = None
        self.stderr = None
    async def wait(self):
        return 0


@pytest.mark.asyncio
async def test_llamafile_denylist(monkeypatch, tmp_path: Path):
    models_dir = tmp_path / "models"; models_dir.mkdir(); (models_dir / "m.gguf").write_text("x")
    cfg = LlamafileConfig(models_dir=models_dir, llamafile_dir=tmp_path / "bin")
    handler = LlamafileHandler(cfg, global_app_config={})
    # Pretend llama executable exists
    exe = handler.llamafile_exe_path
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text("#!/bin/sh\n")
    # Denylist secret flags by default
    with pytest.raises(ServerError):
        await handler.start_server("m.gguf", server_args={"hf_token": "SECRET"})

    # Allow when configured
    cfg.allow_cli_secrets = True
    async def fake_cpe(*a, **k): return DummyProc()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_cpe)
    import tldw_Server_API.app.core.Local_LLM.Llamafile_Handler as lf_mod
    monkeypatch.setattr(lf_mod, "wait_for_http_ready", lambda *a, **k: asyncio.sleep(0, result=True))
    res = await handler.start_server("m.gguf", server_args={"hf_token": "SECRET"})
    assert res["status"] == "started"
