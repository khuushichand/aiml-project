from __future__ import annotations


def test_scope_key_for_tool_call_includes_assignment_identity_for_workspace_membership() -> None:
    from tldw_Server_API.app.services.mcp_hub_approval_service import _scope_key_for_tool_call

    first = _scope_key_for_tool_call(
        "files.read",
        {"path": "src/README.md"},
        scope_payload={
            "workspace_id": "workspace-beta",
            "selected_assignment_id": 11,
            "workspace_source_mode": "named",
            "selected_workspace_trust_source": "shared_registry",
            "reason": "workspace_not_allowed_but_trusted",
        },
    )
    second = _scope_key_for_tool_call(
        "files.read",
        {"path": "src/README.md"},
        scope_payload={
            "workspace_id": "workspace-beta",
            "selected_assignment_id": 12,
            "workspace_source_mode": "named",
            "selected_workspace_trust_source": "shared_registry",
            "reason": "workspace_not_allowed_but_trusted",
        },
    )

    assert first.startswith("tool:files.read|args:")
    assert second.startswith("tool:files.read|args:")
    assert first != second


def test_scope_key_for_tool_call_includes_workspace_trust_source_for_workspace_membership() -> None:
    from tldw_Server_API.app.services.mcp_hub_approval_service import _scope_key_for_tool_call

    first = _scope_key_for_tool_call(
        "files.read",
        {"path": "src/README.md"},
        scope_payload={
            "workspace_id": "workspace-beta",
            "selected_assignment_id": 11,
            "workspace_source_mode": "named",
            "selected_workspace_trust_source": "shared_registry",
            "reason": "workspace_not_allowed_but_trusted",
        },
    )
    second = _scope_key_for_tool_call(
        "files.read",
        {"path": "src/README.md"},
        scope_payload={
            "workspace_id": "workspace-beta",
            "selected_assignment_id": 11,
            "workspace_source_mode": "named",
            "selected_workspace_trust_source": "user_local",
            "reason": "workspace_not_allowed_but_trusted",
        },
    )

    assert first.startswith("tool:files.read|args:")
    assert second.startswith("tool:files.read|args:")
    assert first != second
