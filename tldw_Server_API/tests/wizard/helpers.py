from __future__ import annotations

import json
from typing import Any, Dict, Optional, Sequence


def assert_wizard_json(output: str, *, command: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
    payload = json.loads(output)
    assert isinstance(payload, dict)
    assert "command" in payload
    assert "status" in payload
    if command is not None:
        assert payload.get("command") == command
    if status is not None:
        assert payload.get("status") == status
    return payload


def assert_wizard_error(payload: Dict[str, Any], *, action_key: Optional[str] = None) -> Dict[str, Any]:
    assert payload.get("status") == "error"
    assert "actions" in payload
    actions = payload.get("actions") or []
    assert isinstance(actions, list)
    if action_key is not None:
        assert any(action_key in action for action in actions)
    return payload


def assert_action_field(
    actions: list[Dict[str, Any]],
    action_key: str,
    field_path: str | Sequence[str],
    expected: Any,
) -> Dict[str, Any]:
    payload = None
    for action in actions:
        if action_key in action:
            payload = action.get(action_key)
            break
    assert payload is not None
    path = field_path.split(".") if isinstance(field_path, str) else list(field_path)
    current: Any = payload
    for key in path:
        assert isinstance(current, dict)
        assert key in current
        current = current[key]
    assert current == expected
    return payload


def assert_action_fields(
    actions: list[Dict[str, Any]],
    action_key: str,
    expectations: Dict[str, Any],
) -> Dict[str, Any]:
    payload = None
    for action in actions:
        if action_key in action:
            payload = action.get(action_key)
            break
    assert payload is not None
    for field_path, expected in expectations.items():
        path = field_path.split(".")
        current: Any = payload
        for key in path:
            assert isinstance(current, dict)
            assert key in current
            current = current[key]
        assert current == expected
    return payload
