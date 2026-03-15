"""Integration tests for ACP persistence layer.

These tests verify the full flow: store -> DB -> retrieval, exercising
multiple layers together rather than unit-testing in isolation.
"""
import json
import os
import tempfile

import pytest

from tldw_Server_API.app.core.DB_Management.ACP_Sessions_DB import ACPSessionsDB
from tldw_Server_API.app.core.DB_Management.Orchestration_DB import OrchestrationDB
from tldw_Server_API.app.core.Agent_Orchestration.models import TaskStatus, RunStatus
from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistry
from tldw_Server_API.app.core.Agent_Client_Protocol.health_monitor import AgentHealthMonitor
from tldw_Server_API.app.services.acp_runtime_policy_service import ACPRuntimePolicyService
from tldw_Server_API.app.services.admin_acp_sessions_service import ACPSessionStore

pytestmark = [pytest.mark.unit]


@pytest.fixture
def session_db():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "acp_sessions.db")
        db = ACPSessionsDB(db_path=path)
        yield db
        db.close()


@pytest.fixture
def orch_db():
    with tempfile.TemporaryDirectory() as tmp:
        db = OrchestrationDB(user_id=1, db_dir=tmp)
        yield db
        db.close()


@pytest.fixture
def registry_with_db(tmp_path, session_db):
    yaml_content = """
agents:
  - type: claude_code
    name: Claude Code
    command: nonexistent_xyz
    requires_api_key: ANTHROPIC_API_KEY
    default: true
    install_instructions:
      - "npm install -g @anthropic-ai/claude-code"
    docs_url: "https://docs.anthropic.com/claude-code"
"""
    yaml_file = tmp_path / "agents.yaml"
    yaml_file.write_text(yaml_content)
    registry = AgentRegistry(yaml_path=str(yaml_file), db=session_db)
    registry.load()
    return registry


class TestSessionPersistenceFlow:
    """Verify session CRUD persists to SQLite and survives reconnection."""

    def test_session_create_persists_to_db(self, session_db):
        """Create a session via DB, verify all fields survive round-trip."""
        row = session_db.register_session(
            session_id="integration-s1",
            user_id=42,
            agent_type="claude_code",
            name="Integration Test",
            cwd="/tmp/test",
            tags=["integration", "test"],
            mcp_servers=[{"name": "fs", "type": "stdio"}],
        )
        assert row["session_id"] == "integration-s1"
        assert row["user_id"] == 42
        assert row["agent_type"] == "claude_code"
        assert row["tags"] == ["integration", "test"]
        assert row["mcp_servers"] == [{"name": "fs", "type": "stdio"}]
        assert row["status"] == "active"

        # Re-fetch to confirm persistence
        fetched = session_db.get_session("integration-s1")
        assert fetched is not None
        assert fetched["name"] == "Integration Test"
        assert fetched["tags"] == ["integration", "test"]

    def test_session_messages_accumulate(self, session_db):
        """Record multiple prompts and verify message count + token accumulation."""
        session_db.register_session(session_id="msg-test", user_id=1)

        # First prompt
        session_db.record_prompt(
            "msg-test",
            [{"role": "user", "content": "Hello"}],
            {"content": [{"text": "Hi there"}], "usage": {"input_tokens": 10, "output_tokens": 5}},
        )
        # Second prompt
        session_db.record_prompt(
            "msg-test",
            [{"role": "user", "content": "How are you?"}],
            {"content": [{"text": "Fine"}], "usage": {"input_tokens": 20, "output_tokens": 8}},
        )

        session = session_db.get_session("msg-test")
        assert session["message_count"] == 4  # 2 user + 2 assistant
        assert session["prompt_tokens"] == 30
        assert session["completion_tokens"] == 13
        assert session["total_tokens"] == 43

        messages = session_db.get_messages("msg-test")
        assert len(messages) == 4
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_fork_preserves_lineage_in_db(self, session_db):
        """Fork a session chain and verify lineage is persisted."""
        session_db.register_session(session_id="root", user_id=1, agent_type="codex")
        session_db.record_prompt(
            "root",
            [{"role": "user", "content": "start"}],
            {"content": "ok", "usage": {}},
        )
        session_db.fork_session("root", "fork1", message_index=999, user_id=1)
        session_db.fork_session("fork1", "fork2", message_index=999, user_id=1)

        lineage = session_db.get_fork_lineage("fork2")
        assert lineage == ["root", "fork1"]

        # Forked session should have messages copied
        fork_msgs = session_db.get_messages("fork1")
        assert len(fork_msgs) == 2

    def test_quota_enforcement(self, session_db):
        """Verify quota checks work end-to-end."""
        session_db.configure_quotas(max_concurrent_per_user=2, max_tokens_per_session=100)

        session_db.register_session(session_id="q1", user_id=1)
        session_db.register_session(session_id="q2", user_id=1)

        # Should be at limit
        error = session_db.check_session_quota(1)
        assert error is not None
        assert error["code"] == "quota_exceeded"

        # Close one, should be under limit
        session_db.close_session("q1")
        assert session_db.check_session_quota(1) is None

        # Token quota
        session_db.update_token_usage("q2", prompt_tokens=80, completion_tokens=30)
        token_error = session_db.check_token_quota("q2")
        assert token_error is not None
        assert token_error["code"] == "token_quota_exceeded"

    def test_session_cleanup_eviction(self, session_db):
        """Verify TTL eviction works."""
        session_db.configure_quotas(session_ttl_seconds=0)
        session_db.register_session(session_id="expiring", user_id=1)
        evicted = session_db.evict_expired_sessions()
        assert evicted == 1
        session = session_db.get_session("expiring")
        assert session["status"] == "closed"

    @pytest.mark.asyncio
    async def test_runtime_policy_snapshot_persists_to_session_store(self, session_db):
        store = ACPSessionStore(db=session_db)
        await store.register_session(
            session_id="runtime-policy",
            user_id=42,
            persona_id="persona-1",
            workspace_id="workspace-1",
        )
        session = await store.get_session("runtime-policy")
        assert session is not None

        class _Resolver:
            async def resolve_for_context(self, *, user_id, metadata):
                return {
                    "policy_document": {
                        "allowed_tools": ["web.search"],
                        "approval_mode": "require_approval",
                    },
                    "sources": [{"source_kind": "profile"}],
                    "provenance": [{"source_kind": "profile"}],
                }

        service = ACPRuntimePolicyService(policy_resolver=_Resolver())
        snapshot = await service.build_snapshot(session_record=session, user_id=42)
        persisted = await service.persist_snapshot(session_store=store, snapshot=snapshot)

        assert persisted is not None
        assert persisted.policy_snapshot_fingerprint == snapshot.policy_snapshot_fingerprint
        assert persisted.policy_summary == snapshot.policy_summary


class TestOrchestrationPersistenceFlow:
    """Verify orchestration project/task/run/review persists correctly."""

    def test_full_task_lifecycle(self, orch_db):
        """Create project -> task -> run -> complete -> review -> approve."""
        project = orch_db.create_project(name="Integration Project")
        assert project.id > 0

        task = orch_db.create_task(
            project.id, title="Build feature",
            description="Implement the thing",
            agent_type="claude_code",
        )
        assert task.status == TaskStatus.TODO

        # Transition through states
        orch_db.transition_task(task.id, TaskStatus.IN_PROGRESS)
        task = orch_db.get_task(task.id)
        assert task.status == TaskStatus.IN_PROGRESS

        # Create a run
        run = orch_db.create_run(task.id, session_id="acp-session-1", agent_type="claude_code")
        assert run.status == RunStatus.RUNNING
        assert run.agent_type == "claude_code"

        # Complete the run
        completed_run = orch_db.complete_run(run.id, result_summary="Done")
        assert completed_run.status == RunStatus.COMPLETED

        # Move to review
        orch_db.transition_task(task.id, TaskStatus.REVIEW)

        # Submit review -- approve
        reviewed = orch_db.submit_review(task.id, approved=True)
        assert reviewed.status == TaskStatus.COMPLETE
        assert reviewed.review_count == 1

    def test_dependency_gating_persisted(self, orch_db):
        """Verify dependency checks work against persisted state."""
        project = orch_db.create_project(name="Deps")
        t1 = orch_db.create_task(project.id, title="T1")
        t2 = orch_db.create_task(project.id, title="T2", dependency_id=t1.id)

        assert orch_db.check_dependency_ready(t2.id) is False

        # Complete T1
        orch_db.transition_task(t1.id, TaskStatus.IN_PROGRESS)
        orch_db.transition_task(t1.id, TaskStatus.REVIEW)
        orch_db.submit_review(t1.id, approved=True)

        assert orch_db.check_dependency_ready(t2.id) is True

    def test_review_rejection_and_triage(self, orch_db):
        """Verify reviewer gate with rejection leading to triage."""
        project = orch_db.create_project(name="Review")
        task = orch_db.create_task(
            project.id, title="T1", max_review_attempts=2,
        )

        # First cycle: reject
        orch_db.transition_task(task.id, TaskStatus.IN_PROGRESS)
        orch_db.transition_task(task.id, TaskStatus.REVIEW)
        result = orch_db.submit_review(task.id, approved=False)
        assert result.status == TaskStatus.IN_PROGRESS
        assert result.review_count == 1

        # Second cycle: reject again -> should triage
        orch_db.transition_task(task.id, TaskStatus.REVIEW)
        result = orch_db.submit_review(task.id, approved=False)
        assert result.status == TaskStatus.TRIAGE
        assert result.review_count == 2

    def test_project_summary(self, orch_db):
        """Verify project summary reflects persisted state."""
        project = orch_db.create_project(name="Summary")
        orch_db.create_task(project.id, title="T1")
        t2 = orch_db.create_task(project.id, title="T2")
        orch_db.transition_task(t2.id, TaskStatus.IN_PROGRESS)
        t3 = orch_db.create_task(project.id, title="T3")
        orch_db.transition_task(t3.id, TaskStatus.IN_PROGRESS)
        orch_db.transition_task(t3.id, TaskStatus.REVIEW)
        orch_db.submit_review(t3.id, approved=True)

        summary = orch_db.get_project_summary(project.id)
        assert summary["total_tasks"] == 3
        assert summary["status_counts"]["todo"] == 1
        assert summary["status_counts"]["inprogress"] == 1
        assert summary["status_counts"]["complete"] == 1

    def test_cascade_delete(self, orch_db):
        """Verify project delete cascades to tasks and runs."""
        project = orch_db.create_project(name="Cascade")
        task = orch_db.create_task(project.id, title="T1")
        orch_db.create_run(task.id, session_id="s1")

        assert orch_db.delete_project(project.id) is True
        assert orch_db.get_project(project.id) is None
        assert orch_db.get_task(task.id) is None


class TestRegistryPersistenceFlow:
    """Verify dynamic agent registration persists across reload."""

    def test_register_survives_reload(self, registry_with_db):
        """Register an agent, reload registry, verify it persists."""
        registry_with_db.register_agent(
            type="custom_agent",
            name="Custom Agent",
            command="custom-cli",
            description="A custom agent",
            install_instructions=["pip install custom-agent"],
            docs_url="https://custom.agent/docs",
        )

        entry = registry_with_db.get_entry("custom_agent")
        assert entry is not None
        assert entry.name == "Custom Agent"

        # Force reload (simulates server restart)
        registry_with_db._reload_interval = 0
        registry_with_db.load()

        entry = registry_with_db.get_entry("custom_agent")
        assert entry is not None
        assert entry.command == "custom-cli"
        assert entry.install_instructions == ["pip install custom-agent"]

    def test_api_override_yaml_survives_reload(self, registry_with_db):
        """API entry overriding YAML entry persists across reload."""
        registry_with_db.register_agent(
            type="claude_code",
            name="Custom Claude",
            command="my-claude",
        )
        entry = registry_with_db.get_entry("claude_code")
        assert entry.name == "Custom Claude"

        registry_with_db.load()
        entry = registry_with_db.get_entry("claude_code")
        assert entry.name == "Custom Claude"

    def test_deregister_removes_from_db(self, registry_with_db):
        """Deregistered agents don't reappear after reload."""
        registry_with_db.register_agent(type="temp", name="Temp", command="temp")
        assert registry_with_db.get_entry("temp") is not None

        registry_with_db.deregister_agent("temp")
        assert registry_with_db.get_entry("temp") is None

        # After reload, should still be gone
        registry_with_db.load()
        assert registry_with_db.get_entry("temp") is None


class TestHealthMonitorIntegration:
    """Verify health monitor records to DB."""

    def test_health_check_persists_to_db(self, session_db):
        """Health monitor check_all() writes history to DB."""
        from unittest.mock import MagicMock

        mock_registry = MagicMock()
        entry = MagicMock()
        entry.type = "test_agent"
        entry.check_availability.return_value = {"status": "available", "is_configured": True}
        mock_registry.entries = [entry]

        monitor = AgentHealthMonitor(registry=mock_registry, db=session_db)
        monitor.check_all()

        history = session_db.get_health_history("test_agent")
        assert len(history) == 1
        assert history[0]["health"] == "healthy"
        assert history[0]["consecutive_failures"] == 0

    def test_health_failure_history_accumulates(self, session_db):
        """Multiple health checks accumulate in the DB."""
        from unittest.mock import MagicMock

        mock_registry = MagicMock()
        entry = MagicMock()
        entry.type = "failing_agent"
        entry.check_availability.return_value = {"status": "unavailable", "is_configured": False}
        mock_registry.entries = [entry]

        monitor = AgentHealthMonitor(registry=mock_registry, db=session_db, failure_threshold=3)
        monitor.check_all()
        monitor.check_all()
        monitor.check_all()

        history = session_db.get_health_history("failing_agent")
        assert len(history) == 3
        # Most recent first (DESC order)
        assert history[0]["consecutive_failures"] == 3
        assert history[0]["health"] == "unavailable"
        assert history[2]["consecutive_failures"] == 1
        assert history[2]["health"] == "degraded"
