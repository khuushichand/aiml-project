"""Tests for archetype_schemas Pydantic models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.archetype_schemas import (
    ArchetypeBuddyDefaults,
    ArchetypeMCPConfig,
    ArchetypePersonaDefaults,
    ArchetypePolicyDefaults,
    ArchetypeStarterCommand,
    ArchetypeSummary,
    ArchetypeTemplate,
    ArchetypeToolOverride,
    MCPCatalogEntry,
)
from tldw_Server_API.app.api.v1.schemas.persona import (
    PersonaProfileCreate,
    PersonaProfileResponse,
    PersonaSetupStep,
)

pytestmark = pytest.mark.unit


class TestArchetypeSummary:
    def test_roundtrip(self):
        data = {"key": "researcher", "label": "Researcher", "tagline": "Deep-dive into any topic", "icon": "microscope"}
        summary = ArchetypeSummary(**data)
        assert summary.model_dump() == data

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            ArchetypeSummary(key="x", label="X", icon="i")


class TestArchetypeTemplate:
    def test_minimal_fields(self):
        """Template with only required ArchetypeSummary fields; optional sections use defaults."""
        tpl = ArchetypeTemplate(key="minimal", label="Minimal", tagline="Bare-bones template", icon="box")
        assert tpl.key == "minimal"
        assert tpl.persona.name == ""
        assert tpl.mcp_modules.enabled == []
        assert tpl.mcp_modules.disabled == []
        assert tpl.suggested_external_servers == []
        assert tpl.policy.confirmation_mode == "destructive_only"
        assert tpl.policy.tool_overrides == []
        assert tpl.voice_defaults == {}
        assert tpl.scope_rules == []
        assert tpl.buddy.species is None
        assert tpl.starter_commands == []

    def test_full_fields(self):
        tpl = ArchetypeTemplate(
            key="power_user",
            label="Power User",
            tagline="All the tools",
            icon="rocket",
            persona=ArchetypePersonaDefaults(
                name="Power",
                system_prompt="You are a power user assistant.",
                personality_traits=["concise", "technical"],
            ),
            mcp_modules=ArchetypeMCPConfig(enabled=["media", "rag"], disabled=["tts"]),
            suggested_external_servers=["https://mcp.example.com"],
            policy=ArchetypePolicyDefaults(
                confirmation_mode="always",
                tool_overrides=[ArchetypeToolOverride(tool="delete_media", requires_confirmation=True)],
            ),
            voice_defaults={"tts_provider": "openai", "tts_voice": "nova"},
            scope_rules=[{"rule_type": "media_tag", "rule_value": "research"}],
            buddy=ArchetypeBuddyDefaults(species="owl", palette="warm", silhouette="round"),
            starter_commands=[
                ArchetypeStarterCommand(template_key="summarize_video"),
                ArchetypeStarterCommand(custom={"action": "search", "query": "latest papers"}),
            ],
        )
        dumped = tpl.model_dump()
        assert dumped["key"] == "power_user"
        assert dumped["persona"]["personality_traits"] == ["concise", "technical"]
        assert dumped["mcp_modules"]["enabled"] == ["media", "rag"]
        assert dumped["policy"]["confirmation_mode"] == "always"
        assert len(dumped["policy"]["tool_overrides"]) == 1
        assert dumped["buddy"]["species"] == "owl"
        assert len(dumped["starter_commands"]) == 2
        assert dumped["suggested_external_servers"] == ["https://mcp.example.com"]
        assert dumped["voice_defaults"]["tts_voice"] == "nova"
        assert dumped["scope_rules"][0]["rule_type"] == "media_tag"

    def test_inherits_summary_fields(self):
        tpl = ArchetypeTemplate(key="k", label="L", tagline="T", icon="I")
        assert isinstance(tpl, ArchetypeSummary)


class TestMCPCatalogEntry:
    def test_creation_minimal(self):
        entry = MCPCatalogEntry(
            key="github",
            name="GitHub",
            description="Access GitHub repos",
            url_template="https://github.mcp.example.com/{org}",
            auth_type="oauth2",
            category="developer",
        )
        assert entry.key == "github"
        assert entry.logo_key is None
        assert entry.suggested_for == []

    def test_creation_full(self):
        entry = MCPCatalogEntry(
            key="slack",
            name="Slack",
            description="Read and send Slack messages",
            url_template="https://slack.mcp.example.com",
            auth_type="api_key",
            category="communication",
            logo_key="slack_logo",
            suggested_for=["researcher", "power_user"],
        )
        assert entry.logo_key == "slack_logo"
        assert entry.suggested_for == ["researcher", "power_user"]

    def test_roundtrip(self):
        data = {
            "key": "jira",
            "name": "Jira",
            "description": "Track issues",
            "url_template": "https://jira.mcp.example.com",
            "auth_type": "bearer",
            "category": "project_management",
        }
        entry = MCPCatalogEntry(**data)
        assert entry.model_dump() == {**data, "logo_key": None, "suggested_for": []}


class TestArchetypeStarterCommand:
    def test_template_key_only(self):
        cmd = ArchetypeStarterCommand(template_key="summarize_video")
        assert cmd.template_key == "summarize_video"
        assert cmd.custom is None

    def test_custom_only(self):
        cmd = ArchetypeStarterCommand(custom={"action": "search"})
        assert cmd.template_key is None
        assert cmd.custom == {"action": "search"}

    def test_both_raises(self):
        with pytest.raises(ValidationError, match="Exactly one"):
            ArchetypeStarterCommand(template_key="foo", custom={"action": "bar"})

    def test_neither_raises(self):
        with pytest.raises(ValidationError, match="Exactly one"):
            ArchetypeStarterCommand()

    def test_explicit_none_and_value(self):
        cmd = ArchetypeStarterCommand(template_key=None, custom={"x": 1})
        assert cmd.custom == {"x": 1}

    def test_explicit_none_both_raises(self):
        with pytest.raises(ValidationError, match="Exactly one"):
            ArchetypeStarterCommand(template_key=None, custom=None)


class TestPersonaSchemaArchetypeKey:
    def test_persona_setup_step_includes_archetype(self):
        from typing import get_args

        args = get_args(PersonaSetupStep)
        assert "archetype" in args
        assert len(args) == 6

    def test_profile_create_archetype_key_default_none(self):
        profile = PersonaProfileCreate(name="Test")
        assert profile.archetype_key is None

    def test_profile_create_archetype_key_set(self):
        profile = PersonaProfileCreate(name="Test", archetype_key="researcher")
        assert profile.archetype_key == "researcher"

    def test_profile_response_archetype_key_default_none(self):
        resp = PersonaProfileResponse(
            id="p1",
            name="Test",
            mode="session_scoped",
            created_at="2026-01-01T00:00:00Z",
            last_modified="2026-01-01T00:00:00Z",
        )
        assert resp.archetype_key is None

    def test_profile_response_archetype_key_set(self):
        resp = PersonaProfileResponse(
            id="p1",
            name="Test",
            archetype_key="power_user",
            mode="session_scoped",
            created_at="2026-01-01T00:00:00Z",
            last_modified="2026-01-01T00:00:00Z",
        )
        assert resp.archetype_key == "power_user"
