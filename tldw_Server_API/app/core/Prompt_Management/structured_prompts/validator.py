from collections.abc import Mapping
import re
from typing import Any

from .models import PromptDefinition, ValidationIssue

SUPPORTED_SCHEMA_VERSION = 1
VALID_BLOCK_ROLES = {"system", "developer", "user", "assistant"}
_TEMPLATE_VARIABLE_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, PromptDefinition):
        return value.model_dump()
    if isinstance(value, Mapping):
        return value
    return {}


def validate_prompt_definition(definition: dict[str, Any] | PromptDefinition) -> list[ValidationIssue]:
    payload = _as_mapping(definition)
    issues: list[ValidationIssue] = []
    declared_variable_names: set[str] = set()

    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        issues.append(
            ValidationIssue(
                code="unsupported_schema_version",
                message=f"Unsupported schema version: {payload.get('schema_version')!r}",
                path="schema_version",
            )
        )

    variables = payload.get("variables", [])
    if isinstance(variables, list):
        seen_variable_names: set[str] = set()
        for index, variable in enumerate(variables):
            if not isinstance(variable, Mapping):
                continue
            name = str(variable.get("name") or "").strip()
            if not name:
                continue
            if name in seen_variable_names:
                issues.append(
                    ValidationIssue(
                        code="duplicate_variable_name",
                        message=f"Duplicate variable name: {name}",
                        path=f"variables[{index}].name",
                    )
                )
                break
            seen_variable_names.add(name)
            declared_variable_names.add(name)

    blocks = payload.get("blocks", [])
    if isinstance(blocks, list):
        seen_block_ids: set[str] = set()
        for index, block in enumerate(blocks):
            if not isinstance(block, Mapping):
                continue

            block_id = str(block.get("id") or "").strip()
            if block_id:
                if block_id in seen_block_ids:
                    issues.append(
                        ValidationIssue(
                            code="duplicate_block_id",
                            message=f"Duplicate block id: {block_id}",
                            path=f"blocks[{index}].id",
                        )
                    )
                    break
                seen_block_ids.add(block_id)

            role = block.get("role")
            if role not in VALID_BLOCK_ROLES:
                issues.append(
                    ValidationIssue(
                        code="invalid_block_role",
                        message=f"Invalid block role: {role!r}",
                        path=f"blocks[{index}].role",
                    )
                )
                break

            if block.get("is_template") is True:
                content = str(block.get("content") or "")
                for match in _TEMPLATE_VARIABLE_PATTERN.finditer(content):
                    variable_name = match.group(1)
                    if variable_name not in declared_variable_names:
                        issues.append(
                            ValidationIssue(
                                code="unknown_variable_reference",
                                message=f"Unknown variable reference: {variable_name}",
                                path=f"blocks[{index}].content",
                            )
                        )
                        break
                if issues:
                    break

    return issues
