import asyncio
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Local_LLM.LlamaCpp_Handler import LlamaCppHandler
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Schemas import LlamaCppConfig
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions import ServerError, InferenceError
import httpx


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
    async def _fake_cpe(*a, **k):
        return DummyProcess()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_cpe)
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


@pytest.mark.asyncio
async def test_llamacpp_start_server_invalid_arg(monkeypatch, tmp_path: Path):
    exe = tmp_path / "llama_server"
    exe.write_text("#!/bin/sh\n")
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "toy.gguf").write_text("fake")

    cfg = LlamaCppConfig(executable_path=exe, models_dir=tmp_path / "models")
    handler = LlamaCppHandler(cfg, global_app_config={})

    with pytest.raises(ServerError):
        await handler.start_server("toy.gguf", server_args={"not_a_flag": True})


@pytest.mark.asyncio
async def test_llamacpp_inference_http_5xx(monkeypatch, tmp_path: Path):
    # Setup handler and running process state
    exe = tmp_path / "llama_server"
    exe.write_text("#!/bin/sh\n")
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    (model_dir / "toy.gguf").write_text("fake")
    cfg = LlamaCppConfig(executable_path=exe, models_dir=model_dir, default_port=8199)
    handler = LlamaCppHandler(cfg, global_app_config={})

    # Fake that server is running
    class RunningProc:
        pid = 1
        returncode = None
    handler._active_server_process = RunningProc()
    handler._active_server_host = "127.0.0.1"
    handler._active_server_port = 8199

    # Make request_json raise HTTPStatusError
    import tldw_Server_API.app.core.Local_LLM.LlamaCpp_Handler as llama_mod
    req = httpx.Request("POST", "http://127.0.0.1:8199/v1/chat/completions")
    resp = httpx.Response(500, request=req, text="server error")
    err = httpx.HTTPStatusError("error", request=req, response=resp)
    monkeypatch.setattr(llama_mod, "request_json", lambda *a, **k: (_ for _ in ()).throw(err))

    with pytest.raises(InferenceError):
        await handler.inference(prompt="hi")


@pytest.mark.asyncio
async def test_llamacpp_stop_timeout(monkeypatch, tmp_path: Path):
    exe = tmp_path / "llama_server"; exe.write_text("#!/bin/sh\n")
    model_dir = tmp_path / "models"; model_dir.mkdir(); (model_dir / "toy.gguf").write_text("fake")
    cfg = LlamaCppConfig(executable_path=exe, models_dir=model_dir)
    handler = LlamaCppHandler(cfg, global_app_config={})

    class SlowProc:
        def __init__(self):
            self.pid = 88
            self.returncode = None
        async def wait(self):
            return 0
        def terminate(self):
            self.returncode = None

    handler._active_server_process = SlowProc()
    handler._active_server_model = "toy.gguf"
    handler._active_server_host = "127.0.0.1"
    handler._active_server_port = 8081

    async def fake_wait_for(coro, timeout):
        raise asyncio.TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
    import os as _os
    monkeypatch.setattr(_os, "killpg", lambda *a, **k: None, raising=False)

    msg = await handler.stop_server()
    assert "stopped" in msg.lower() or "terminated" in msg.lower()
@pytest.mark.asyncio
async def test_llamacpp_start_server_not_ready(monkeypatch, tmp_path: Path):
    exe = tmp_path / "llama_server"; exe.write_text("#!/bin/sh\n")
    model_dir = tmp_path / "models"; model_dir.mkdir(); (model_dir / "toy.gguf").write_text("fake")
    cfg = LlamaCppConfig(executable_path=exe, models_dir=model_dir, default_port=8099)
    handler = LlamaCppHandler(cfg, global_app_config={})

    class DP:  # dummy process
        pid = 42
        returncode = None
        stdout = None
        stderr = None
        def terminate(self): pass
    async def _fake_cpe2(*a, **k):
        return DP()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_cpe2)
    from tldw_Server_API.app.core.Local_LLM import http_utils
    monkeypatch.setattr(http_utils, "wait_for_http_ready", lambda *a, **k: asyncio.sleep(0, result=False))

    with pytest.raises(ServerError):
        await handler.start_server("toy.gguf", server_args={"port": 8099})


@pytest.mark.asyncio
async def test_llamacpp_allow_unvalidated_args_unknown_flags_passthrough(monkeypatch, tmp_path: Path):
    # Prepare dummy executable and model
    exe = tmp_path / "llama_server"; exe.write_text("#!/bin/sh\n")
    model_dir = tmp_path / "models"; model_dir.mkdir(); (model_dir / "toy.gguf").write_text("fake")

    # Enable allow_unvalidated_args to allow passthrough of unknown flags
    cfg = LlamaCppConfig(
        executable_path=exe,
        models_dir=model_dir,
        default_host="127.0.0.1",
        default_port=8010,
        allow_unvalidated_args=True,
    )
    handler = LlamaCppHandler(cfg, global_app_config={})

    # Capture the command passed to subprocess
    captured_cmd = {"args": ()}

    class DP:
        pid = 99
        returncode = None
        stdout = None
        stderr = None
        async def wait(self):
            return 0

    async def fake_cpe(*args, **kwargs):
        captured_cmd["args"] = args
        return DP()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_cpe)

    # Patch the symbol imported into the module (not http_utils) to avoid 30s wait
    import tldw_Server_API.app.core.Local_LLM.LlamaCpp_Handler as llama_mod
    monkeypatch.setattr(llama_mod, "wait_for_http_ready", lambda *a, **k: asyncio.sleep(0, result=True))

    # Unknown flags should be converted to --unknown-flag and --bool-flag (no value)
    res = await handler.start_server(
        "toy.gguf",
        server_args={
            "port": 8010,
            "unknown_flag": 7,
            "another_unknown": "x",
            "bool_unknown": True,
            "none_unknown": None,
        },
    )

    assert res["status"] == "started"
    args = list(captured_cmd["args"])  # tuple of command components
    # Ensure the transformed flags are present
    assert "--unknown-flag" in args and "7" in args
    assert "--another-unknown" in args and "x" in args
    assert "--bool-unknown" in args  # boolean True => flag only
    # None/False should not append a value or flag
    assert "--none-unknown" not in args
