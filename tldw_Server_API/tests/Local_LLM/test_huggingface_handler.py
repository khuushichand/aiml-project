from pathlib import Path
import subprocess
import sys

import pytest


def _hf_runtime_is_importable() -> bool:
    probe = subprocess.run(
        [sys.executable, "-c", "import transformers, torch; print('ok')"],
        check=False,
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0


if not _hf_runtime_is_importable():
    pytest.skip(
        "transformers/torch runtime is unavailable or crashes during import in this environment",
        allow_module_level=True,
    )

transformers = pytest.importorskip("transformers")
torch = pytest.importorskip("torch")

from tldw_Server_API.app.core.Local_LLM.Huggingface_Handler import HuggingFaceHandler
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Schemas import HuggingFaceConfig
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions import ModelDownloadError


@pytest.mark.asyncio
async def test_hf_download_rejects_traversal(monkeypatch, tmp_path: Path):
    models_dir = tmp_path / "models"
    cfg = HuggingFaceConfig(models_dir=models_dir)
    handler = HuggingFaceHandler(cfg, global_app_config={})
    handler._ensure_hf_dependencies()

    import tldw_Server_API.app.core.Local_LLM.Huggingface_Handler as hf_mod

    def _should_not_call(*args, **kwargs):
        raise AssertionError("download should not be invoked for unsafe paths")

    monkeypatch.setattr(hf_mod.AutoTokenizer, "from_pretrained", _should_not_call)
    monkeypatch.setattr(hf_mod.AutoModelForCausalLM, "from_pretrained", _should_not_call)

    with pytest.raises(ModelDownloadError):
        await handler.download_model("gpt2", save_directory="../evil")


@pytest.mark.asyncio
async def test_hf_cache_key_includes_quantization(monkeypatch, tmp_path: Path):
    cfg = HuggingFaceConfig(models_dir=tmp_path)
    handler = HuggingFaceHandler(cfg, global_app_config={})
    handler._ensure_hf_dependencies()
    model_dir = tmp_path / "toy"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "config.json").write_text("{}")

    import tldw_Server_API.app.core.Local_LLM.Huggingface_Handler as hf_mod

    tok_calls = []
    model_calls = []

    def fake_tokenizer(*args, **kwargs):
        obj = object()
        tok_calls.append(obj)
        return obj

    def fake_model(*args, **kwargs):
        obj = object()
        model_calls.append(obj)
        return obj

    monkeypatch.setattr(hf_mod.AutoTokenizer, "from_pretrained", staticmethod(fake_tokenizer))
    monkeypatch.setattr(hf_mod.AutoModelForCausalLM, "from_pretrained", staticmethod(fake_model))
    monkeypatch.setattr(hf_mod, "BitsAndBytesConfig", lambda **kwargs: {"bnb": kwargs})

    model_a, tok_a = await handler._load_model_and_tokenizer("toy", {"load_in_8bit": True})
    model_b, tok_b = await handler._load_model_and_tokenizer("toy", {"load_in_8bit": True})
    model_c, tok_c = await handler._load_model_and_tokenizer("toy", {"load_in_4bit": True})

    assert model_a is model_b
    assert tok_a is tok_b
    assert model_a is not model_c
    assert tok_a is not tok_c
    assert len(model_calls) == 2
    assert len(tok_calls) == 2
