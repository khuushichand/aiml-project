# Unit tests for chat workflows

import pytest

pytestmark = pytest.mark.unit

from tldw_Server_API.app.core.Chat import Workflows as workflows


def test_workflow_defaults_not_shared(monkeypatch):
    wf_list = [{"name": "WF", "prompts": ["P1", "P2"], "context": ""}]
    state, context, history = workflows.initialize_workflow("WF", wf_list)

    calls = []

    def fake_chat(_message, _history, media_content, selected_parts, *_args, **_kwargs):
        calls.append({"media": dict(media_content), "parts": list(selected_parts)})
        media_content["mutated"] = True
        selected_parts.append("mutated")
        return "bot"

    monkeypatch.setattr(workflows, "chat", fake_chat)

    history1, state1, cont1 = workflows.process_workflow_step(
        "hi",
        history,
        context,
        "WF",
        wf_list,
        state,
        api_endpoint="openai",
        api_key=None,
        save_conv=False,
        temp=0.7,
        system_message=None,
    )
    assert cont1 is True

    _history2, _state2, cont2 = workflows.process_workflow_step(
        "hi2",
        history1,
        context,
        "WF",
        wf_list,
        state1,
        api_endpoint="openai",
        api_key=None,
        save_conv=False,
        temp=0.7,
        system_message=None,
    )
    assert cont2 is False

    assert calls[0]["media"] == {}
    assert calls[0]["parts"] == []
    assert calls[1]["media"] == {}
    assert calls[1]["parts"] == []
