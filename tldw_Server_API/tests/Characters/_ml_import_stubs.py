"""Test helpers for stubbing heavyweight ML imports in Characters tests."""

import importlib.machinery
from types import ModuleType
from types import SimpleNamespace
import sys


def stub_heavy_ml_imports() -> None:
    """Install lightweight stand-ins for optional ML modules used by app imports."""
    if "torch" not in sys.modules:
        torch_stub = ModuleType("torch")
        torch_stub.__spec__ = importlib.machinery.ModuleSpec("torch", loader=None)
        # SciPy checks torch.Tensor during import-time array API compatibility probes.
        torch_stub.Tensor = object
        torch_stub.nn = SimpleNamespace(Module=object)
        sys.modules["torch"] = torch_stub
    sys.modules.setdefault("transformers", ModuleType("transformers"))
    sys.modules.setdefault("optimum", ModuleType("optimum"))

    if "optimum.onnxruntime" in sys.modules:
        return

    optimum_onnxruntime = ModuleType("optimum.onnxruntime")
    optimum_onnxruntime.ORTModelForFeatureExtraction = object
    sys.modules["optimum.onnxruntime"] = optimum_onnxruntime

    optimum_module = sys.modules.get("optimum")
    if optimum_module is not None:
        setattr(optimum_module, "onnxruntime", optimum_onnxruntime)
