from tldw_Server_API.app.core.Prompt_Management.structured_prompts import (
    convert_legacy_prompt_to_definition,
    extract_legacy_prompt_variables,
)


def test_extract_legacy_prompt_variables_preserves_first_seen_order():
    variables = extract_legacy_prompt_variables(
        "You are helping with {topic}.",
        "Summarize $topic and compare against <baseline> with {{style}}.",
    )

    assert variables == ["topic", "baseline", "style"]


def test_convert_legacy_prompt_to_definition_normalizes_placeholder_styles():
    definition = convert_legacy_prompt_to_definition(
        system_prompt="Be precise about {topic}.",
        user_prompt="Summarize $topic and compare against <baseline> in {{style}}.",
    )

    assert [variable.name for variable in definition.variables] == [
        "topic",
        "baseline",
        "style",
    ]
    assert definition.blocks[0].content == "Be precise about {{topic}}."
    assert definition.blocks[0].is_template is True
    assert definition.blocks[1].content == (
        "Summarize {{topic}} and compare against {{baseline}} in {{style}}."
    )
    assert definition.blocks[1].is_template is True
