import re

from .models import PromptBlock, PromptDefinition, PromptVariableDefinition

_LEGACY_TEMPLATE_PATTERN = re.compile(
    r"{{\s*([a-zA-Z0-9_]+)\s*}}|\{([a-zA-Z0-9_]+)\}|\$([a-zA-Z0-9_]+)|<([a-zA-Z0-9_]+)>"
)


def extract_legacy_prompt_variables(*templates: str | None) -> list[str]:
    variables: list[str] = []
    for template in templates:
        for match in _LEGACY_TEMPLATE_PATTERN.finditer(template or ""):
            variable_name = _match_variable_name(match)
            if variable_name not in variables:
                variables.append(variable_name)
    return variables


def normalize_legacy_prompt_template(template: str | None) -> str:
    if not template:
        return ""
    return _LEGACY_TEMPLATE_PATTERN.sub(
        lambda match: "{{" + _match_variable_name(match) + "}}",
        template,
    )


def convert_legacy_prompt_to_definition(
    *,
    system_prompt: str | None,
    user_prompt: str | None,
) -> PromptDefinition:
    variables = extract_legacy_prompt_variables(system_prompt, user_prompt)
    blocks: list[PromptBlock] = []

    normalized_system_prompt = normalize_legacy_prompt_template(system_prompt)
    if normalized_system_prompt:
        blocks.append(
            PromptBlock(
                id="legacy_system",
                name="System Instructions",
                role="system",
                kind="instructions",
                content=normalized_system_prompt,
                enabled=True,
                order=10,
                is_template="{{" in normalized_system_prompt,
            )
        )

    normalized_user_prompt = normalize_legacy_prompt_template(user_prompt)
    if normalized_user_prompt:
        blocks.append(
            PromptBlock(
                id="legacy_user",
                name="User Prompt",
                role="user",
                kind="task",
                content=normalized_user_prompt,
                enabled=True,
                order=20,
                is_template="{{" in normalized_user_prompt,
            )
        )

    variable_definitions = [
        PromptVariableDefinition(
            name=variable_name,
            label=variable_name.replace("_", " ").title(),
            required=True,
            input_type="textarea",
        )
        for variable_name in variables
    ]

    return PromptDefinition(
        variables=variable_definitions,
        blocks=blocks,
    )


def _match_variable_name(match: re.Match[str]) -> str:
    for group in match.groups():
        if group:
            return group
    return ""
