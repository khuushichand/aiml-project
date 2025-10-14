import asyncio
import platform
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Local_LLM.LlamaCpp_Handler import LlamaCppHandler
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Schemas import LlamaCppConfig
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions import ServerError


class DummyProc:
    def __init__(self, pid=777):
        self.pid = pid
        self.returncode = None
        self.stdout = None
        self.stderr = None
    async def wait(self):
        return 0


@pytest.mark.asyncio
async def test_windows_creationflags(monkeypatch, tmp_path: Path):
    exe = tmp_path / "llama_server"; exe.write_text("#!/bin/sh\n")
    model_dir = tmp_path / "models"; model_dir.mkdir(); (model_dir / "m.gguf").write_text("x")
    cfg = LlamaCppConfig(executable_path=exe, models_dir=model_dir)
    handler = LlamaCppHandler(cfg, global_app_config={})

    monkeypatch.setattr(platform, "system", lambda: "Windows")
    captured = {}
    async def fake_cpe(*args, **kwargs):
        captured.update(kwargs)
        return DummyProc()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_cpe)

    import tldw_Server_API.app.core.Local_LLM.LlamaCpp_Handler as llama_mod
    monkeypatch.setattr(llama_mod, "wait_for_http_ready", lambda *a, **k: asyncio.sleep(0, result=True))

    res = await handler.start_server("m.gguf")
    assert res["status"] == "started"
    assert "creationflags" in captured


@pytest.mark.asyncio
async def test_denylist_hf_token_rejected(monkeypatch, tmp_path: Path):
    exe = tmp_path / "llama_server"; exe.write_text("#!/bin/sh\n")
    model_dir = tmp_path / "models"; model_dir.mkdir(); (model_dir / "m.gguf").write_text("x")
    cfg = LlamaCppConfig(executable_path=exe, models_dir=model_dir, allow_unvalidated_args=True)
    handler = LlamaCppHandler(cfg, global_app_config={})
    with pytest.raises(ServerError):
        await handler.start_server("m.gguf", server_args={"hf_token": "ABC"})


@pytest.mark.asyncio
async def test_allow_cli_secrets_allows_hf_token(monkeypatch, tmp_path: Path):
    exe = tmp_path / "llama_server"; exe.write_text("#!/bin/sh\n")
    model_dir = tmp_path / "models"; model_dir.mkdir(); (model_dir / "m.gguf").write_text("x")
    cfg = LlamaCppConfig(executable_path=exe, models_dir=model_dir, allow_unvalidated_args=True, allow_cli_secrets=True)
    handler = LlamaCppHandler(cfg, global_app_config={})
    async def fake_cpe(*a, **k): return DummyProc()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_cpe)
    import tldw_Server_API.app.core.Local_LLM.LlamaCpp_Handler as llama_mod
    monkeypatch.setattr(llama_mod, "wait_for_http_ready", lambda *a, **k: asyncio.sleep(0, result=True))
    res = await handler.start_server("m.gguf", server_args={"hf_token": "ABC"})
    assert res["status"] == "started"


@pytest.mark.asyncio
async def test_path_safety(monkeypatch, tmp_path: Path):
    exe = tmp_path / "llama_server"; exe.write_text("#!/bin/sh\n")
    model_dir = tmp_path / "models"; model_dir.mkdir(); (model_dir / "m.gguf").write_text("x")
    cfg = LlamaCppConfig(executable_path=exe, models_dir=model_dir)
    handler = LlamaCppHandler(cfg, global_app_config={})

    # Outside models_dir should be rejected
    with pytest.raises(ServerError):
        await handler.start_server("m.gguf", server_args={"grammar_file": str(tmp_path / "outside.bnf")})

    # Inside models_dir should pass
    inside = model_dir / "g.bnf"; inside.write_text("rule := 'x'")
    import tldw_Server_API.app.core.Local_LLM.LlamaCpp_Handler as llama_mod
    async def fake_cpe(*a, **k): return DummyProc()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_cpe)
    monkeypatch.setattr(llama_mod, "wait_for_http_ready", lambda *a, **k: asyncio.sleep(0, result=True))
    res = await handler.start_server("m.gguf", server_args={"grammar_file": str(inside)})
    assert res["status"] == "started"


@pytest.mark.asyncio
async def test_port_autoselect(monkeypatch, tmp_path: Path):
    exe = tmp_path / "llama_server"; exe.write_text("#!/bin/sh\n")
    model_dir = tmp_path / "models"; model_dir.mkdir(); (model_dir / "m.gguf").write_text("x")
    cfg = LlamaCppConfig(executable_path=exe, models_dir=model_dir, default_port=9000, port_autoselect=True, port_probe_max=5)
    handler = LlamaCppHandler(cfg, global_app_config={})

    seq = {"i": 0}
    def fake_is_free(host, port):
        seq["i"] += 1
        return seq["i"] >= 2  # first port busy, second free
    monkeypatch.setattr(handler, "_is_port_free", fake_is_free)
    async def fake_cpe(*a, **k): return DummyProc()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_cpe)
    import tldw_Server_API.app.core.Local_LLM.LlamaCpp_Handler as llama_mod
    monkeypatch.setattr(llama_mod, "wait_for_http_ready", lambda *a, **k: asyncio.sleep(0, result=True))
    res = await handler.start_server("m.gguf")
    assert res["status"] == "started"
    # Expect port increased
    assert res["port"] == cfg.default_port + 1


@pytest.mark.asyncio
async def test_streaming_inference_yields_sse(monkeypatch, tmp_path: Path):
    exe = tmp_path / "llama_server"; exe.write_text("#!/bin/sh\n")
    model_dir = tmp_path / "models"; model_dir.mkdir(); (model_dir / "m.gguf").write_text("x")
    cfg = LlamaCppConfig(executable_path=exe, models_dir=model_dir)
    handler = LlamaCppHandler(cfg, global_app_config={})
    # Fake running process
    handler._active_server_process = DummyProc(pid=123)
    handler._active_server_host = "127.0.0.1"
    handler._active_server_port = 9999

    class FakeStream:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        def raise_for_status(self):
            return None
        async def aiter_lines(self):
            yield "data: {\"choices\":[{\"delta\":{\"content\":\"Hi\"}}]}"
            yield "data: [DONE]"

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        def stream(self, method, url, json=None, headers=None):
            return FakeStream()

    import tldw_Server_API.app.core.Local_LLM.http_utils as http_utils
    monkeypatch.setattr(http_utils, "create_async_client", lambda *a, **k: FakeClient())

    chunks = []
    async for line in handler.stream_inference(prompt="hello"):
        chunks.append(line)
    assert any("data: [DONE]" in c for c in chunks)
