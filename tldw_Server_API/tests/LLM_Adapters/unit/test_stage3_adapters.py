from typing import Any, Dict


def _req_base(**overrides) -> Dict[str, Any]:
    req = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "test-model",
        "api_key": "x",
        "temperature": 0.5,
    }
    req.update(overrides)
    return req


def test_qwen_adapter_mapping_preserves_stream_none_and_top_p():
    from tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter import QwenAdapter

    adapter = QwenAdapter()
    args = adapter._to_handler_args(_req_base(stream=None, top_p=0.8))
    assert args.get("maxp") == 0.8
    assert "streaming" in args and args["streaming"] is None


def test_deepseek_adapter_mapping_top_p_and_stream_true():
    from tldw_Server_API.app.core.LLM_Calls.providers.deepseek_adapter import DeepSeekAdapter

    adapter = DeepSeekAdapter()
    args = adapter._to_handler_args(_req_base(stream=True, top_p=0.77))
    assert args.get("topp") == 0.77
    assert args.get("streaming") is True


def test_huggingface_adapter_basic_mapping():
    from tldw_Server_API.app.core.LLM_Calls.providers.huggingface_adapter import HuggingFaceAdapter

    adapter = HuggingFaceAdapter()
    args = adapter._to_handler_args(_req_base(top_p=0.9, top_k=40, max_tokens=256))
    assert args.get("top_p") == 0.9
    assert args.get("top_k") == 40
    assert args.get("max_tokens") == 256


def test_custom_openai_adapter_knobs():
    from tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter import CustomOpenAIAdapter

    adapter = CustomOpenAIAdapter()
    args = adapter._to_handler_args(_req_base(top_p=0.5, top_k=20, min_p=0.1))
    assert args.get("maxp") == 0.5
    assert args.get("topp") == 0.5
    assert args.get("topk") == 20
    assert args.get("minp") == 0.1
