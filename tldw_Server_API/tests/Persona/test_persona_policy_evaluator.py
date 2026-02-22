import pytest

from tldw_Server_API.app.core.Persona.policy_evaluator import (
    default_allow_rules,
    evaluate_canonical_policy,
)


pytestmark = pytest.mark.unit


def test_canonical_policy_denies_when_persona_layer_has_no_rules():
    decision = evaluate_canonical_policy(
        step_type="mcp_tool",
        action_name="media.search",
        persona_policy_rules=[],
        session_policy_rules=default_allow_rules("mcp_tool"),
        skill_policy_rules=default_allow_rules("mcp_tool"),
        session_scopes={"read", "write:preview"},
        allow_export=False,
        allow_delete=False,
    )

    assert decision["allow"] is False
    assert decision["reason_code"] == "POLICY_PERSONA_NO_RULES"


def test_canonical_policy_honors_bounded_wildcards():
    decision = evaluate_canonical_policy(
        step_type="mcp_tool",
        action_name="media.search",
        persona_policy_rules=[{"rule_kind": "mcp_tool", "rule_name": "media.*", "allowed": True}],
        session_policy_rules=default_allow_rules("mcp_tool"),
        skill_policy_rules=default_allow_rules("mcp_tool"),
        session_scopes={"read", "write:preview"},
        allow_export=False,
        allow_delete=False,
    )

    assert decision["allow"] is True
    assert decision["reason_code"] is None


def test_canonical_policy_explicit_deny_overrides_allow():
    decision = evaluate_canonical_policy(
        step_type="mcp_tool",
        action_name="media.search",
        persona_policy_rules=[
            {"rule_kind": "mcp_tool", "rule_name": "*", "allowed": True},
            {"rule_kind": "mcp_tool", "rule_name": "media.search", "allowed": False},
        ],
        session_policy_rules=default_allow_rules("mcp_tool"),
        skill_policy_rules=default_allow_rules("mcp_tool"),
        session_scopes={"read", "write:preview"},
        allow_export=False,
        allow_delete=False,
    )

    assert decision["allow"] is False
    assert decision["reason_code"] == "POLICY_PERSONA_EXPLICIT_DENY"


def test_canonical_policy_requires_session_layer_allow():
    decision = evaluate_canonical_policy(
        step_type="mcp_tool",
        action_name="media.search",
        persona_policy_rules=[{"rule_kind": "mcp_tool", "rule_name": "media.search", "allowed": True}],
        session_policy_rules=[],
        skill_policy_rules=default_allow_rules("mcp_tool"),
        session_scopes={"read", "write:preview"},
        allow_export=False,
        allow_delete=False,
    )

    assert decision["allow"] is False
    assert decision["reason_code"] == "POLICY_SESSION_NO_RULES"


def test_canonical_policy_blocks_export_when_disabled():
    decision = evaluate_canonical_policy(
        step_type="mcp_tool",
        action_name="export_report",
        persona_policy_rules=[{"rule_kind": "mcp_tool", "rule_name": "export_report", "allowed": True}],
        session_policy_rules=default_allow_rules("mcp_tool"),
        skill_policy_rules=default_allow_rules("mcp_tool"),
        session_scopes={"read", "write:preview", "write:export"},
        allow_export=False,
        allow_delete=False,
    )

    assert decision["allow"] is False
    assert decision["reason_code"] == "POLICY_EXPORT_DISABLED"


def test_canonical_policy_allows_internal_rag_query_step():
    decision = evaluate_canonical_policy(
        step_type="rag_query",
        action_name="knowledge.search",
        persona_policy_rules=[],
        session_policy_rules=[],
        skill_policy_rules=[],
        session_scopes={"read"},
        allow_export=False,
        allow_delete=False,
    )

    assert decision["allow"] is True
    assert decision["step_type"] == "rag_query"
    assert decision["effective_allowed_tools"] == ["knowledge.search"]


def test_canonical_policy_unknown_exportish_tool_does_not_escalate_scope():
    decision = evaluate_canonical_policy(
        step_type="mcp_tool",
        action_name="notes.export_preview_like",
        persona_policy_rules=[{"rule_kind": "mcp_tool", "rule_name": "notes.export_preview_like", "allowed": True}],
        session_policy_rules=default_allow_rules("mcp_tool"),
        skill_policy_rules=default_allow_rules("mcp_tool"),
        session_scopes={"read"},
        allow_export=False,
        allow_delete=False,
    )

    assert decision["allow"] is True
    assert decision["required_scope"] == "read"
    assert decision["action"] == "read"
    assert decision["reason_code"] is None


def test_canonical_policy_unknown_deleteish_tool_does_not_escalate_scope():
    decision = evaluate_canonical_policy(
        step_type="mcp_tool",
        action_name="reports.delete_preview_like",
        persona_policy_rules=[{"rule_kind": "mcp_tool", "rule_name": "reports.delete_preview_like", "allowed": True}],
        session_policy_rules=default_allow_rules("mcp_tool"),
        skill_policy_rules=default_allow_rules("mcp_tool"),
        session_scopes={"read"},
        allow_export=False,
        allow_delete=False,
    )

    assert decision["allow"] is True
    assert decision["required_scope"] == "read"
    assert decision["action"] == "read"
    assert decision["reason_code"] is None
