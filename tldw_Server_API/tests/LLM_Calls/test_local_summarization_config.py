import pytest

from tldw_Server_API.app.core.LLM_Calls import Summarization_General_Lib as sgl
from tldw_Server_API.app.core.LLM_Calls.Local_Summarization_Lib import (
    summarize_with_local_llm,
)


@pytest.mark.unit
def test_summarize_with_local_llm_routes_to_adapter(monkeypatch):
    captured = {}

    def fake_analyze(**kwargs):
        captured.update(kwargs)
        return "summary result"

    monkeypatch.setattr(sgl, "analyze", fake_analyze)

    result = summarize_with_local_llm(
        "text to summarize",
        "instruction",
        temp=0.5,
        system_message="system",
        streaming=True,
    )

    assert result == "summary result"
    assert captured["api_name"] == "local-llm"
    assert captured["input_data"] == "text to summarize"
    assert captured["custom_prompt_arg"] == "instruction"
    assert captured["temp"] == 0.5
    assert captured["system_message"] == "system"
    assert captured["streaming"] is True
