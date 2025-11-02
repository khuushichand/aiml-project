import pytest

from tldw_Server_API.app.core.Local_LLM import (
    LLMInferenceManager,
    LLMManagerConfig,
    HuggingFaceConfig,
)
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions import InferenceError


def test_manager_get_handler_unknown_backend():
    mgr = LLMInferenceManager(LLMManagerConfig(huggingface=HuggingFaceConfig(enabled=False)))
    with pytest.raises(InferenceError):
        mgr.get_handler("does-not-exist")


@pytest.mark.asyncio
async def test_manager_get_server_status_unsupported():
    # Enable huggingface only; it has no get_server_status method
    mgr = LLMInferenceManager(LLMManagerConfig(huggingface=HuggingFaceConfig(enabled=True)))
    with pytest.raises(InferenceError):
        await mgr.get_server_status("huggingface")
