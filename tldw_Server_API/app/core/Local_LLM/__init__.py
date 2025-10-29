"""Local LLM package exports with lazy loading.

Exposes manager, configs, and exceptions for convenient imports while
deferring heavy submodule imports until first access.
"""

from typing import TYPE_CHECKING, Any
import importlib

__all__ = [
    "LLMInferenceManager",
    "LLMManagerConfig",
    "OllamaConfig",
    "HuggingFaceConfig",
    "LlamafileConfig",
    "LlamaCppConfig",
    "LLMInferenceLibError",
    "ModelNotFoundError",
    "ModelDownloadError",
    "ServerError",
    "InferenceError",
]

_ATTR_MAP = {
    "LLMInferenceManager": ("tldw_Server_API.app.core.Local_LLM.LLM_Inference_Manager", "LLMInferenceManager"),
    "LLMManagerConfig": ("tldw_Server_API.app.core.Local_LLM.LLM_Inference_Schemas", "LLMManagerConfig"),
    "OllamaConfig": ("tldw_Server_API.app.core.Local_LLM.LLM_Inference_Schemas", "OllamaConfig"),
    "HuggingFaceConfig": ("tldw_Server_API.app.core.Local_LLM.LLM_Inference_Schemas", "HuggingFaceConfig"),
    "LlamafileConfig": ("tldw_Server_API.app.core.Local_LLM.LLM_Inference_Schemas", "LlamafileConfig"),
    "LlamaCppConfig": ("tldw_Server_API.app.core.Local_LLM.LLM_Inference_Schemas", "LlamaCppConfig"),
    "LLMInferenceLibError": ("tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions", "LLMInferenceLibError"),
    "ModelNotFoundError": ("tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions", "ModelNotFoundError"),
    "ModelDownloadError": ("tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions", "ModelDownloadError"),
    "ServerError": ("tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions", "ServerError"),
    "InferenceError": ("tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions", "InferenceError"),
}

def __getattr__(name: str) -> Any:
    mod_attr = _ATTR_MAP.get(name)
    if not mod_attr:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = mod_attr
    module = importlib.import_module(module_name)
    return getattr(module, attr)

if TYPE_CHECKING:  # for static type checkers
    from .LLM_Inference_Manager import LLMInferenceManager as LLMInferenceManager
    from .LLM_Inference_Schemas import (
        LLMManagerConfig as LLMManagerConfig,
        OllamaConfig as OllamaConfig,
        HuggingFaceConfig as HuggingFaceConfig,
        LlamafileConfig as LlamafileConfig,
        LlamaCppConfig as LlamaCppConfig,
    )
    from .LLM_Inference_Exceptions import (
        LLMInferenceLibError as LLMInferenceLibError,
        ModelNotFoundError as ModelNotFoundError,
        ModelDownloadError as ModelDownloadError,
        ServerError as ServerError,
        InferenceError as InferenceError,
    )
