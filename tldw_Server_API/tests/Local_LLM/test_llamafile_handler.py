import asyncio
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Local_LLM.Llamafile_Handler import LlamafileHandler
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Schemas import LlamafileConfig
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions import ServerError, InferenceError
import httpx


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
    async def _fake_cpe(*a, **k):
        return DummyProcess()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_cpe)
    from tldw_Server_API.app.core.Local_LLM import http_utils
    monkeypatch.setattr(http_utils, "wait_for_http_ready", lambda *a, **k: asyncio.sleep(0, result=True))

    res = await handler.start_server(model_filename=model.name, server_args={"port": 8077, "api_key": "supersecret"})
    assert res["status"] == "started"
    assert "REDACTED" in res["command"]
    assert "supersecret" not in res["command"]


@pytest.mark.asyncio
async def test_llamafile_start_server_invalid_arg(monkeypatch, tmp_path: Path):
    llama_dir = tmp_path / "llamafile"
    model_dir = tmp_path / "models"
    llama_dir.mkdir(); model_dir.mkdir()
    exe = llama_dir / "llamafile"; exe.write_text("#!/bin/sh\n")
    (model_dir / "m.gguf").write_text("fake")

    cfg = LlamafileConfig(llamafile_dir=llama_dir, models_dir=model_dir)
    handler = LlamafileHandler(cfg, global_app_config={})

    monkeypatch.setattr(handler, "download_latest_llamafile_executable", lambda force_download=False: asyncio.sleep(0, result=exe))
    # readiness will succeed but we should fail earlier due to invalid arg
    from tldw_Server_API.app.core.Local_LLM import http_utils
    async def _fake_cpe2(*a, **k):
        return DummyProcess()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_cpe2)
    monkeypatch.setattr(http_utils, "wait_for_http_ready", lambda *a, **k: asyncio.sleep(0, result=True))

    with pytest.raises(ServerError):
        await handler.start_server("m.gguf", server_args={"bad_flag": True})


@pytest.mark.asyncio
async def test_llamafile_inference_http_error(monkeypatch, tmp_path: Path):
    # Prepare handler
    llama_dir = tmp_path / "llamafile"; llama_dir.mkdir()
    cfg = LlamafileConfig(llamafile_dir=llama_dir, models_dir=tmp_path)
    handler = LlamafileHandler(cfg, global_app_config={})

    # Fake running server map so it proceeds to HTTP request
    class RP: pid = 2; returncode = None
    handler._active_servers[8080] = RP()

    import tldw_Server_API.app.core.Local_LLM.Llamafile_Handler as lf_mod
    req = httpx.Request("POST", "http://127.0.0.1:8080/v1/chat/completions")
    resp = httpx.Response(500, request=req, text="err")
    err = httpx.HTTPStatusError("error", request=req, response=resp)
    monkeypatch.setattr(lf_mod, "request_json", lambda *a, **k: (_ for _ in ()).throw(err))

    with pytest.raises(InferenceError):
        await handler.inference(prompt="hi", port=8080)


@pytest.mark.asyncio
async def test_llamafile_stop_timeout(monkeypatch, tmp_path: Path):
    llama_dir = tmp_path / "llamafile"; llama_dir.mkdir()
    cfg = LlamafileConfig(llamafile_dir=llama_dir, models_dir=tmp_path)
    handler = LlamafileHandler(cfg, global_app_config={})

    class SlowProc:
        def __init__(self):
            self.pid = 99
            self.returncode = None
        async def wait(self):
            return 0
        def terminate(self):
            self.returncode = None

    handler._active_servers[5555] = SlowProc()

    async def fake_wait_for(coro, timeout):
        raise asyncio.TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
    # os.killpg will be called; stub it to avoid errors in tests
    import os as _os
    monkeypatch.setattr(_os, "killpg", lambda *a, **k: None, raising=False)

    msg = await handler.stop_server(port=5555)
    assert "stopped" in msg.lower() or "terminated" in msg.lower()
@pytest.mark.asyncio
async def test_llamafile_start_server_not_ready(monkeypatch, tmp_path: Path):
    llama_dir = tmp_path / "llamafile"; model_dir = tmp_path / "models"
    llama_dir.mkdir(); model_dir.mkdir()
    exe = llama_dir / "llamafile"; exe.write_text("#!/bin/sh\n")
    (model_dir / "toy.gguf").write_text("fake")

    cfg = LlamafileConfig(llamafile_dir=llama_dir, models_dir=model_dir, default_port=8077)
    handler = LlamafileHandler(cfg, global_app_config={})

    monkeypatch.setattr(handler, "download_latest_llamafile_executable", lambda force_download=False: asyncio.sleep(0, result=exe))
    class DP: pid=11; returncode=None; stdout=None; stderr=None
    async def _fake_cpe3(*a, **k):
        return DP()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_cpe3)
    from tldw_Server_API.app.core.Local_LLM import http_utils
    monkeypatch.setattr(http_utils, "wait_for_http_ready", lambda *a, **k: asyncio.sleep(0, result=False))

    with pytest.raises(ServerError):
        await handler.start_server("toy.gguf", server_args={"port": 8077})
