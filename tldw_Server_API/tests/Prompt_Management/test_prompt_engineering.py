import pytest
import sys
import types


def test_extract_prompt_no_instructions_tag():
    # Provide a fake chat_orchestrator before importing the module to avoid heavy deps
    mod = types.ModuleType("chat_orchestrator_stub")
    setattr(mod, "chat_api_call", lambda **kwargs: kwargs.get('prompt'))
    sys.modules['tldw_Server_API.app.core.Chat.chat_orchestrator'] = mod

    from tldw_Server_API.app.core.Prompt_Management import Prompt_Engineering as PE

    # No <Instructions> tag present; trailing sign-off should be stripped
    raw = "Hello there. Let me know if you need anything"
    out = PE.extract_prompt(raw)
    assert out == "Hello there.", "Expected fallback to strip sign-off and keep core text"


def test_variable_replacement_double_brace(monkeypatch):
    captured = {}

    def fake_chat_api_call(**kwargs):
        # Capture the prompt that reaches the chat layer
        captured['prompt'] = kwargs.get('prompt')
        # Return the prompt back to the caller for easy assertions
        return kwargs.get('prompt')

    # Pre-insert fake chat orchestrator to avoid importing heavy dependencies
    mod = types.ModuleType("chat_orchestrator_stub")
    setattr(mod, "chat_api_call", fake_chat_api_call)
    sys.modules['tldw_Server_API.app.core.Chat.chat_orchestrator'] = mod

    from tldw_Server_API.app.core.Prompt_Management import Prompt_Engineering as PE
    # Ensure we override any cached binding from previous imports
    monkeypatch.setattr(PE, 'chat_api_call', fake_chat_api_call)

    generated = "Task: {{$A}} then {{$B}}."
    values = "first, second"

    response = PE.test_generated_prompt(
        api_endpoint="local",
        api_key="none",
        generated_prompt=generated,
        variable_values_str=values,
        temperature=0.0,
    )

    assert response == "Task: first then second.", "Expected placeholders to be replaced in response"
    assert captured['prompt'] == "Task: first then second.", "Expected chat layer to receive replaced prompt"


def test_variable_replacement_repeated_placeholders(monkeypatch):
    captured = {}

    def fake_chat_api_call(**kwargs):
        captured['prompt'] = kwargs.get('prompt')
        return kwargs.get('prompt')

    # Ensure module is importable and patch chat function on the module
    mod = types.ModuleType("chat_orchestrator_stub")
    setattr(mod, "chat_api_call", fake_chat_api_call)
    sys.modules['tldw_Server_API.app.core.Chat.chat_orchestrator'] = mod
    from tldw_Server_API.app.core.Prompt_Management import Prompt_Engineering as PE
    monkeypatch.setattr(PE, 'chat_api_call', fake_chat_api_call)

    generated = "Echo {{$X}} and again {{$X}}."
    values = "foo"

    response = PE.test_generated_prompt(
        api_endpoint="local",
        api_key="none",
        generated_prompt=generated,
        variable_values_str=values,
        temperature=0.0,
    )

    assert response == "Echo foo and again foo.", "Repeated placeholders must be replaced consistently"
    assert captured['prompt'] == "Echo foo and again foo.", "Chat should receive fully replaced prompt"


def test_variable_replacement_extra_values_ignored(monkeypatch):
    captured = {}

    def fake_chat_api_call(**kwargs):
        captured['prompt'] = kwargs.get('prompt')
        return kwargs.get('prompt')

    mod = types.ModuleType("chat_orchestrator_stub")
    setattr(mod, "chat_api_call", fake_chat_api_call)
    sys.modules['tldw_Server_API.app.core.Chat.chat_orchestrator'] = mod
    from tldw_Server_API.app.core.Prompt_Management import Prompt_Engineering as PE
    monkeypatch.setattr(PE, 'chat_api_call', fake_chat_api_call)

    generated = "A {{$A}} B {{$B}}."
    values = "one, two, three"

    response = PE.test_generated_prompt(
        api_endpoint="local",
        api_key="none",
        generated_prompt=generated,
        variable_values_str=values,
        temperature=0.0,
    )

    assert response == "A one B two.", "Extra values should be ignored beyond placeholders"
    assert captured['prompt'] == "A one B two.", "Chat should receive prompt with only mapped replacements"


def test_variable_replacement_missing_values_left_intact(monkeypatch):
    captured = {}

    def fake_chat_api_call(**kwargs):
        captured['prompt'] = kwargs.get('prompt')
        return kwargs.get('prompt')

    mod = types.ModuleType("chat_orchestrator_stub")
    setattr(mod, "chat_api_call", fake_chat_api_call)
    sys.modules['tldw_Server_API.app.core.Chat.chat_orchestrator'] = mod
    from tldw_Server_API.app.core.Prompt_Management import Prompt_Engineering as PE
    monkeypatch.setattr(PE, 'chat_api_call', fake_chat_api_call)

    generated = "A {{$A}} B {{$B}} C {{$C}}."
    values = "one"

    response = PE.test_generated_prompt(
        api_endpoint="local",
        api_key="none",
        generated_prompt=generated,
        variable_values_str=values,
        temperature=0.0,
    )

    assert response == "A one B {{$B}} C {{$C}}.", "Unmapped placeholders should remain intact"
    assert captured['prompt'] == "A one B {{$B}} C {{$C}}.", "Chat should receive prompt with remaining placeholders"


def test_invalid_placeholder_formats_unchanged(monkeypatch):
    captured = {}

    def fake_chat_api_call(**kwargs):
        captured['prompt'] = kwargs.get('prompt')
        return kwargs.get('prompt')

    # Use a real module object to avoid inserting an unhashable
    # SimpleNamespace into sys.modules (which breaks Hypothesis introspection).
    mod = types.ModuleType("chat_orchestrator_stub")
    setattr(mod, "chat_api_call", fake_chat_api_call)
    sys.modules['tldw_Server_API.app.core.Chat.chat_orchestrator'] = mod
    from tldw_Server_API.app.core.Prompt_Management import Prompt_Engineering as PE
    monkeypatch.setattr(PE, 'chat_api_call', fake_chat_api_call)

    # These formats should NOT be matched by the {{ $VAR }} pattern used
    generated = "Bad1 {$A} Bad2 {{A}} Bad3 {{ $A }} Good {{$A}}."
    values = "ok"

    response = PE.test_generated_prompt(
        api_endpoint="local",
        api_key="none",
        generated_prompt=generated,
        variable_values_str=values,
        temperature=0.0,
    )

    assert response == "Bad1 {$A} Bad2 {{A}} Bad3 {{ $A }} Good ok.", "Only exact {{$VAR}} should be replaced"
    assert captured['prompt'] == "Bad1 {$A} Bad2 {{A}} Bad3 {{ $A }} Good ok.", "Chat should receive correctly replaced prompt"
