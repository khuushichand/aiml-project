"""Test helpers for stubbing heavyweight ML imports in Characters tests."""

from types import ModuleType
import sys


def stub_heavy_ml_imports() -> None:
    """Install lightweight stand-ins for optional ML modules used by app imports."""
    sys.modules.setdefault("torch", ModuleType("torch"))
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
