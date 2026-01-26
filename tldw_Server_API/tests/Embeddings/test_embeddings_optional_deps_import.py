import builtins
import importlib
import sys


def test_embeddings_create_imports_without_optional_deps(monkeypatch):
    module_name = "tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create"

    # Force a clean import
    sys.modules.pop(module_name, None)

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith("onnxruntime") or name.startswith("huggingface_hub"):
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    mod = importlib.import_module(module_name)
    assert mod is not None

    # Ensure revision checks are safe when huggingface_hub is unavailable
    mod._ensure_hf_revision("dummy/model", "deadbeef")
