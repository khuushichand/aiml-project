from typing import Any, Dict
from unittest.mock import patch


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

    captured: Dict[str, Any] = {}

    def _fake_qwen(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    with patch("tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.chat_with_qwen", _fake_qwen):
        adapter = QwenAdapter()
        resp = adapter.chat(_req_base(stream=None, top_p=0.8))
        assert resp == {"ok": True}
        assert captured.get("maxp") == 0.8
        assert "streaming" in captured and captured["streaming"] is None


def test_deepseek_adapter_mapping_top_p_and_stream_true():
    from tldw_Server_API.app.core.LLM_Calls.providers.deepseek_adapter import DeepSeekAdapter

    captured: Dict[str, Any] = {}

    def _fake_deepseek(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    with patch("tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.chat_with_deepseek", _fake_deepseek):
        adapter = DeepSeekAdapter()
        list(adapter.stream(_req_base(stream=True, top_p=0.77)))
        assert captured.get("topp") == 0.77
        assert captured.get("streaming") is True


def test_huggingface_adapter_basic_mapping():
    from tldw_Server_API.app.core.LLM_Calls.providers.huggingface_adapter import HuggingFaceAdapter

    captured: Dict[str, Any] = {}

    def _fake_hf(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    with patch("tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.chat_with_huggingface", _fake_hf):
        adapter = HuggingFaceAdapter()
        resp = adapter.chat(_req_base(top_p=0.9, top_k=40, max_tokens=256))
        assert resp == {"ok": True}
        assert captured.get("top_p") == 0.9
        assert captured.get("top_k") == 40
        assert captured.get("max_tokens") == 256


def test_custom_openai_adapter_knobs():
    from tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter import CustomOpenAIAdapter

    captured: Dict[str, Any] = {}

    def _fake_custom(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    with patch("tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local.chat_with_custom_openai", _fake_custom):
        adapter = CustomOpenAIAdapter()
        resp = adapter.chat(_req_base(top_p=0.5, top_k=20, min_p=0.1))
        assert resp == {"ok": True}
        assert captured.get("maxp") == 0.5 or captured.get("topp") == 0.5
        assert captured.get("topk") == 20
        assert captured.get("minp") == 0.1

