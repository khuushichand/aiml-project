"""
Canonical persona policy evaluation.

This module centralizes policy semantics for persona agent execution so the
planner preflight and executor share the exact same allow/deny behavior.
"""

from __future__ import annotations

from typing import Any

_VALID_RULE_KINDS = {"mcp_tool", "skill"}
_VALID_STEP_TYPES = {"mcp_tool", "skill", "rag_query", "final_answer"}
_EXPORT_TOOL_ALLOWLIST = {
    "chatbooks.export",
    "export_report",
    "media.export",
    "notes.export",
}
_DELETE_TOOL_ALLOWLIST = {
    "chats.delete",
    "delete_session",
    "media.delete",
    "notes.delete",
}


def normalize_policy_rules(
    raw_rules: Any,
    *,
    rule_kind: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize raw policy rules into a canonical list."""
    normalized_kind = str(rule_kind or "").strip().lower() or None
    if normalized_kind is not None and normalized_kind not in _VALID_RULE_KINDS:
        return []
    if not isinstance(raw_rules, list):
        return []

    out: list[dict[str, Any]] = []
    for entry in raw_rules:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("rule_kind") or "").strip().lower()
        if kind not in _VALID_RULE_KINDS:
            continue
        if normalized_kind is not None and kind != normalized_kind:
            continue
        name = str(entry.get("rule_name") or "").strip().lower()
        if not name:
            continue
        out.append(
            {
                "rule_kind": kind,
                "rule_name": name,
                "allowed": bool(entry.get("allowed", True)),
                "require_confirmation": bool(entry.get("require_confirmation", False)),
            }
        )
    return out


def default_allow_rules(rule_kind: str) -> list[dict[str, Any]]:
    """Return a permissive wildcard rule list for an explicit policy layer."""
    kind = str(rule_kind or "").strip().lower()
    if kind not in _VALID_RULE_KINDS:
        return []
    return [
        {
            "rule_kind": kind,
            "rule_name": "*",
            "allowed": True,
            "require_confirmation": False,
        }
    ]


def _matches_rule_name(rule_name: str, action_name: str) -> bool:
    """
    Bounded wildcard matcher.

    Supported patterns:
    - "*"
    - "prefix*"
    - exact name
    """
    pattern = str(rule_name or "").strip().lower()
    target = str(action_name or "").strip().lower()
    if not pattern or not target:
        return False
    if pattern == "*":
        return True
    if "*" not in pattern:
        return pattern == target
    if pattern.count("*") != 1 or not pattern.endswith("*"):
        return False
    prefix = pattern[:-1]
    if not prefix:
        return False
    return target.startswith(prefix)


def _required_scope_for_step(step_type: str, action_name: str) -> tuple[str, str, bool]:
    normalized_step_type = str(step_type or "").strip().lower()
    normalized_action_name = str(action_name or "").strip().lower()
    if normalized_step_type == "mcp_tool" and normalized_action_name == "ingest_url":
        return "write", "write:preview", True
    if normalized_action_name in _EXPORT_TOOL_ALLOWLIST:
        return "export", "write:export", True
    if normalized_action_name in _DELETE_TOOL_ALLOWLIST:
        return "delete", "write:delete", True
    return "read", "read", False


def _evaluate_layer(
    layer_name: str,
    layer_rules: list[dict[str, Any]],
    *,
    action_name: str,
) -> dict[str, Any]:
    label = str(layer_name or "policy").strip().lower()
    code_prefix = f"POLICY_{label.upper()}"
    if not layer_rules:
        return {
            "allow": False,
            "requires_confirmation": False,
            "reason_code": f"{code_prefix}_NO_RULES",
            "reason": f"{label} policy has no rules for this action.",
            "matched_allow_patterns": [],
            "matched_deny_patterns": [],
        }

    matched_allow_patterns: list[str] = []
    matched_deny_patterns: list[str] = []
    requires_confirmation = False

    for rule in layer_rules:
        if not _matches_rule_name(str(rule.get("rule_name") or ""), action_name):
            continue
        pattern = str(rule.get("rule_name") or "").strip().lower()
        if not bool(rule.get("allowed", True)):
            matched_deny_patterns.append(pattern)
            continue
        matched_allow_patterns.append(pattern)
        requires_confirmation = requires_confirmation or bool(rule.get("require_confirmation", False))

    if matched_deny_patterns:
        return {
            "allow": False,
            "requires_confirmation": False,
            "reason_code": f"{code_prefix}_EXPLICIT_DENY",
            "reason": f"{label} policy explicitly denies this action.",
            "matched_allow_patterns": matched_allow_patterns,
            "matched_deny_patterns": matched_deny_patterns,
        }

    if not matched_allow_patterns:
        return {
            "allow": False,
            "requires_confirmation": False,
            "reason_code": f"{code_prefix}_NO_MATCH",
            "reason": f"{label} policy does not allow this action.",
            "matched_allow_patterns": [],
            "matched_deny_patterns": [],
        }

    return {
        "allow": True,
        "requires_confirmation": requires_confirmation,
        "reason_code": None,
        "reason": None,
        "matched_allow_patterns": matched_allow_patterns,
        "matched_deny_patterns": [],
    }


def evaluate_canonical_policy(
    *,
    step_type: str,
    action_name: str,
    persona_policy_rules: Any,
    session_policy_rules: Any,
    skill_policy_rules: Any = None,
    session_scopes: set[str] | None = None,
    allow_export: bool,
    allow_delete: bool,
) -> dict[str, Any]:
    """
    Evaluate canonical persona policy for a single step/action.

    Semantics:
    - deny by default
    - explicit deny beats allow
    - empty rule layer grants nothing
    - bounded wildcard support only ("*" and "prefix*")
    """
    normalized_step_type = str(step_type or "").strip().lower()
    normalized_action_name = str(action_name or "").strip().lower()
    if normalized_step_type not in _VALID_STEP_TYPES or not normalized_action_name:
        return {
            "allow": False,
            "requires_confirmation": True,
            "required_scope": "read",
            "reason_code": "POLICY_INVALID_ACTION",
            "reason": "Invalid action or step type for policy evaluation.",
            "action": "unknown",
            "step_type": normalized_step_type or "unknown",
            "rule_kind": None,
            "effective_allowed_tools": [],
        }

    action, required_scope, base_requires_confirmation = _required_scope_for_step(
        normalized_step_type,
        normalized_action_name,
    )

    if action == "export" and not allow_export:
        return {
            "allow": False,
            "requires_confirmation": True,
            "required_scope": required_scope,
            "reason_code": "POLICY_EXPORT_DISABLED",
            "reason": "Export tools are disabled by persona policy.",
            "action": action,
            "step_type": normalized_step_type,
            "rule_kind": "mcp_tool",
            "effective_allowed_tools": [],
        }
    if action == "delete" and not allow_delete:
        return {
            "allow": False,
            "requires_confirmation": True,
            "required_scope": required_scope,
            "reason_code": "POLICY_DELETE_DISABLED",
            "reason": "Delete tools are disabled by persona policy.",
            "action": action,
            "step_type": normalized_step_type,
            "rule_kind": "mcp_tool",
            "effective_allowed_tools": [],
        }

    effective_scopes = set(session_scopes or set())
    if required_scope and required_scope not in effective_scopes:
        return {
            "allow": False,
            "requires_confirmation": base_requires_confirmation,
            "required_scope": required_scope,
            "reason_code": "POLICY_SCOPE_MISSING",
            "reason": f"Missing required scope '{required_scope}'.",
            "action": action,
            "step_type": normalized_step_type,
            "rule_kind": "skill" if normalized_step_type == "skill" else "mcp_tool",
            "effective_allowed_tools": [],
        }

    # Internal persona planner step types are not governed by explicit allowlists.
    if normalized_step_type in {"rag_query", "final_answer"}:
        effective_allowed_tools = [normalized_action_name] if normalized_step_type == "rag_query" else []
        return {
            "allow": True,
            "requires_confirmation": base_requires_confirmation,
            "required_scope": required_scope,
            "reason_code": None,
            "reason": None,
            "action": action,
            "step_type": normalized_step_type,
            "rule_kind": None,
            "effective_allowed_tools": effective_allowed_tools,
        }

    rule_kind = "skill" if normalized_step_type == "skill" else "mcp_tool"

    # Keep legacy ingest_url scaffold behavior while still applying scope gates.
    if normalized_step_type == "mcp_tool" and normalized_action_name == "ingest_url":
        return {
            "allow": True,
            "requires_confirmation": True,
            "required_scope": required_scope,
            "reason_code": None,
            "reason": None,
            "action": action,
            "step_type": normalized_step_type,
            "rule_kind": rule_kind,
            "effective_allowed_tools": [normalized_action_name],
        }

    persona_rules = normalize_policy_rules(persona_policy_rules, rule_kind=rule_kind)
    session_rules = normalize_policy_rules(session_policy_rules, rule_kind=rule_kind)
    skill_rules = normalize_policy_rules(skill_policy_rules, rule_kind=rule_kind)

    persona_layer = _evaluate_layer("persona", persona_rules, action_name=normalized_action_name)
    if not persona_layer["allow"]:
        return {
            "allow": False,
            "requires_confirmation": base_requires_confirmation,
            "required_scope": required_scope,
            "reason_code": persona_layer["reason_code"],
            "reason": persona_layer["reason"],
            "action": action,
            "step_type": normalized_step_type,
            "rule_kind": rule_kind,
            "effective_allowed_tools": [],
        }

    session_layer = _evaluate_layer("session", session_rules, action_name=normalized_action_name)
    if not session_layer["allow"]:
        return {
            "allow": False,
            "requires_confirmation": base_requires_confirmation,
            "required_scope": required_scope,
            "reason_code": session_layer["reason_code"],
            "reason": session_layer["reason"],
            "action": action,
            "step_type": normalized_step_type,
            "rule_kind": rule_kind,
            "effective_allowed_tools": [],
        }

    skill_layer = _evaluate_layer("skill", skill_rules, action_name=normalized_action_name)
    if not skill_layer["allow"]:
        return {
            "allow": False,
            "requires_confirmation": base_requires_confirmation,
            "required_scope": required_scope,
            "reason_code": skill_layer["reason_code"],
            "reason": skill_layer["reason"],
            "action": action,
            "step_type": normalized_step_type,
            "rule_kind": rule_kind,
            "effective_allowed_tools": [],
        }

    return {
        "allow": True,
        "requires_confirmation": (
            base_requires_confirmation
            or bool(persona_layer["requires_confirmation"])
            or bool(session_layer["requires_confirmation"])
            or bool(skill_layer["requires_confirmation"])
        ),
        "required_scope": required_scope,
        "reason_code": None,
        "reason": None,
        "action": action,
        "step_type": normalized_step_type,
        "rule_kind": rule_kind,
        "effective_allowed_tools": [normalized_action_name] if normalized_step_type == "mcp_tool" else [],
    }
