import pytest

from tldw_Server_API.app.core.RAG.rag_service.generation import PromptTemplates


pytestmark = pytest.mark.unit


def test_prompt_templates_load_switchable_profile_prompt_keys():
    text = PromptTemplates.get_template("instruction_tuned")

    assert "Use the provided context" in text
    assert "{context}" in text
    assert "{question}" in text


def test_prompt_templates_falls_back_to_default_for_unknown_key():
    unknown = PromptTemplates.get_template("does_not_exist")

    assert "Context:" in unknown
    assert "Question:" in unknown
