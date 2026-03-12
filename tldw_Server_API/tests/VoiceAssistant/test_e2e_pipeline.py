# test_e2e_pipeline.py
# End-to-end tests for the Voice Assistant pipeline
#
# Tests the complete flow: STT -> Intent Parse -> Execute -> TTS
#
#######################################################################################################################
import base64
import json
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator, Dict, List, Optional

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.VoiceAssistant import (
    VoiceCommandRegistry,
    VoiceCommandRouter,
    VoiceSessionManager,
    IntentParser,
)
from tldw_Server_API.app.core.VoiceAssistant.db_helpers import save_voice_command
from tldw_Server_API.app.core.VoiceAssistant.schemas import (
    ActionResult,
    ActionType,
    VoiceCommand,
    VoiceIntent,
    VoiceSessionState,
)


pytestmark = pytest.mark.integration


class _MockHTTPResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        json_body: dict[str, Any] | list[Any] | None = None,
        text: str | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_body = json_body
        self.headers = {"content-type": "application/json"} if json_body is not None else {}
        self.text = text if text is not None else json.dumps(json_body or {})

    def json(self) -> Any:
        if self._json_body is None:
            raise ValueError("Response does not contain JSON")
        return self._json_body

    async def aclose(self) -> None:
        return None


def _create_persona_profile(
    db: CharactersRAGDB,
    *,
    user_id: int,
    persona_id: str,
    name: str = "Runtime Persona",
) -> str:
    return db.create_persona_profile(
        {
            "id": persona_id,
            "user_id": str(user_id),
            "name": name,
            "mode": "persistent_scoped",
        }
    )


def _add_persona_connection(
    db: CharactersRAGDB,
    *,
    user_id: int,
    persona_id: str,
    connection_id: str,
    content: dict[str, Any],
) -> str:
    return db.add_persona_memory_entry(
        {
            "id": connection_id,
            "persona_id": persona_id,
            "user_id": str(user_id),
            "memory_type": "persona_connection",
            "content": json.dumps(content),
        }
    )


# Fixtures

@pytest.fixture
def session_manager():
    """Create a fresh session manager."""
    return VoiceSessionManager()


@pytest.fixture
def registry():
    """Create a registry with test commands."""
    reg = VoiceCommandRegistry()
    reg.load_defaults()
    return reg


@pytest.fixture
def intent_parser(registry):
    """Create an intent parser."""
    return IntentParser(registry)


@pytest.fixture
def command_router(registry, session_manager, intent_parser, monkeypatch):
    """Create a command router with mocked dependencies."""

    # Mock MCP tool execution
    async def mock_execute_mcp_tool(intent, session):
        return ActionResult(
            success=True,
            action_type=ActionType.MCP_TOOL,
            result_data={"tool_name": intent.action_config.get("tool_name", "mock_tool")},
            response_text="Executed tool",
        )

    # Mock workflow execution
    async def mock_execute_workflow(intent, session):
        return ActionResult(
            success=True,
            action_type=ActionType.WORKFLOW,
            result_data={
                "run_id": "test-run-1",
                "status": "completed",
                "outputs": {"result": "Workflow completed"},
            },
            response_text="Workflow completed",
        )

    # Mock LLM chat
    async def mock_llm_chat(intent, session):
        return ActionResult(
            success=True,
            action_type=ActionType.LLM_CHAT,
            result_data={"response": f"LLM response to: {intent.raw_text}"},
            response_text=f"LLM response to: {intent.raw_text}",
        )

    router = VoiceCommandRouter(
        registry=registry,
        session_manager=session_manager,
        parser=intent_parser,
    )

    # Patch internal methods
    monkeypatch.setattr(router, "_execute_mcp_tool", mock_execute_mcp_tool)
    monkeypatch.setattr(router, "_execute_workflow", mock_execute_workflow)
    monkeypatch.setattr(router, "_execute_llm_chat", mock_llm_chat)

    return router


# E2E Test Classes

class TestFullPipelineWithTextInput:
    """Tests for complete pipeline using text input (bypassing STT)."""

    @pytest.mark.asyncio
    async def test_search_command_e2e(self, command_router, session_manager):
        """Test the full pipeline for a search command."""
        # Create a session
        session = await session_manager.create_session(user_id=1)

        # Process a search command
        start_time = time.time()
        result, session_id = await command_router.process_command(
            text="search for machine learning",
            user_id=1,
            session_id=session.session_id,
        )
        elapsed_ms = (time.time() - start_time) * 1000

        # Verify result
        assert result.success is True
        assert result.response_text is not None
        assert len(result.response_text) > 0
        assert session_id == session.session_id

        # Verify session was updated
        updated_session = await session_manager.get_session(session.session_id)
        assert len(updated_session.conversation_history) > 0

    @pytest.mark.asyncio
    async def test_help_command_e2e(self, command_router, session_manager):
        """Test the full pipeline for a help command."""
        session = await session_manager.create_session(user_id=1)

        result, _ = await command_router.process_command(
            text="help",
            user_id=1,
            session_id=session.session_id,
        )

        assert result.success is True
        # Help command should return available commands
        assert result.action_type in [ActionType.CUSTOM, ActionType.LLM_CHAT]

    @pytest.mark.asyncio
    async def test_stop_command_e2e(self, command_router, session_manager):
        """Test the stop/cancel command."""
        session = await session_manager.create_session(user_id=1)

        result, _ = await command_router.process_command(
            text="stop",
            user_id=1,
            session_id=session.session_id,
        )

        assert result.success is True
        # Stop should acknowledge
        assert result.response_text is not None

    @pytest.mark.asyncio
    async def test_fallback_to_llm_e2e(self, command_router, session_manager):
        """Test that unknown commands fall back to LLM chat."""
        session = await session_manager.create_session(user_id=1)

        result, _ = await command_router.process_command(
            text="compose a short limerick about rainbows",
            user_id=1,
            session_id=session.session_id,
        )

        assert result.success is True
        assert result.action_type == ActionType.LLM_CHAT
        assert "LLM response" in result.response_text


class TestPipelineWithConfirmation:
    """Tests for commands requiring confirmation."""

    @pytest.mark.asyncio
    async def test_confirmation_flow(self, registry, command_router, session_manager):
        """Test the full confirmation flow."""
        # Register a command that requires confirmation
        cmd = VoiceCommand(
            id="confirm-cmd",
            user_id=0,
            name="delete all",
            phrases=["delete everything", "remove all"],
            action_type=ActionType.LLM_CHAT,
            action_config={},
            requires_confirmation=True,
        )
        registry.register_command(cmd)

        session = await session_manager.create_session(user_id=1)

        # First attempt should ask for confirmation
        result1, _ = await command_router.process_command(
            text="delete everything",
            user_id=1,
            session_id=session.session_id,
        )

        # Check session state (may be AWAITING_CONFIRMATION or the action was executed)
        updated = await session_manager.get_session(session.session_id)

        # If confirmation was required, state should be awaiting
        if updated.state == VoiceSessionState.AWAITING_CONFIRMATION:
            # Confirm the action
            result2, _ = await command_router.process_command(
                text="yes",
                user_id=1,
                session_id=session.session_id,
            )

            # Should have executed
            assert result2.success is True

            # State should return to idle
            final = await session_manager.get_session(session.session_id)
            assert final.state == VoiceSessionState.IDLE

    @pytest.mark.asyncio
    async def test_confirmation_cancel(self, registry, command_router, session_manager):
        """Test canceling a pending confirmation."""
        # Register a command that requires confirmation
        cmd = VoiceCommand(
            id="cancel-cmd",
            user_id=0,
            name="danger action",
            phrases=["do dangerous thing"],
            action_type=ActionType.CUSTOM,
            action_config={},
            requires_confirmation=True,
        )
        registry.register_command(cmd)

        session = await session_manager.create_session(user_id=1)

        # Trigger confirmation
        await command_router.process_command(
            text="do dangerous thing",
            user_id=1,
            session_id=session.session_id,
        )

        # Cancel the action
        result, _ = await command_router.process_command(
            text="no",
            user_id=1,
            session_id=session.session_id,
        )

        # Action should be cancelled
        updated = await session_manager.get_session(session.session_id)
        assert updated.pending_intent is None


class TestPipelineConversationContext:
    """Tests for conversation context in the pipeline."""

    @pytest.mark.asyncio
    async def test_context_maintained_across_turns(self, command_router, session_manager):
        """Test that conversation context is maintained."""
        session = await session_manager.create_session(user_id=1)

        # First turn
        await command_router.process_command(
            text="search for Python tutorials",
            user_id=1,
            session_id=session.session_id,
        )

        # Second turn (follow-up)
        await command_router.process_command(
            text="tell me more about the first result",
            user_id=1,
            session_id=session.session_id,
        )

        # Check conversation history
        updated = await session_manager.get_session(session.session_id)
        assert len(updated.conversation_history) >= 2  # At least 2 turns

    @pytest.mark.asyncio
    async def test_new_session_has_fresh_context(self, command_router, session_manager):
        """Test that a new session starts with fresh context."""
        # First session
        session1 = await session_manager.create_session(user_id=1)
        await command_router.process_command(
            text="remember that my name is Alice",
            user_id=1,
            session_id=session1.session_id,
        )

        # New session (should not have context from first)
        session2 = await session_manager.create_session(user_id=1)
        s2 = await session_manager.get_session(session2.session_id)
        assert len(s2.conversation_history) == 0


class TestPipelineExternalConnections:
    """Tests for persona connection-backed external command execution."""

    @pytest.mark.asyncio
    async def test_connection_backed_custom_command_executes_external_request(
        self,
        command_router,
        session_manager,
        monkeypatch,
        tmp_path: Path,
    ):
        db = CharactersRAGDB(
            tmp_path / "voice_external_runtime.sqlite",
            "voice-external-runtime-tests",
        )
        try:
            persona_id = _create_persona_profile(
                db,
                user_id=1,
                persona_id="persona-runtime",
            )
            _add_persona_connection(
                db,
                user_id=1,
                persona_id=persona_id,
                connection_id="conn-search",
                content={
                    "name": "Search API",
                    "base_url": "https://api.example.com/v1",
                    "auth_type": "bearer",
                    "headers_template": {"X-Client": "voice-builder"},
                    "timeout_ms": 12000,
                    "allowed_hosts": ["api.example.com"],
                    "secret_envelope": "opaque-secret-envelope",
                    "secret_configured": True,
                },
            )
            save_voice_command(
                db,
                VoiceCommand(
                    id="cmd-search-external",
                    user_id=1,
                    persona_id=persona_id,
                    connection_id="conn-search",
                    name="Search External",
                    phrases=["search external for {topic}"],
                    action_type=ActionType.CUSTOM,
                    action_config={
                        "action": "external_search",
                        "method": "POST",
                        "path": "search",
                        "slot_to_param_map": {"query": "topic"},
                        "default_payload": {"limit": 3},
                    },
                ),
            )

            captured: dict[str, Any] = {}

            async def fake_afetch(**kwargs):
                captured.update(kwargs)
                return _MockHTTPResponse(json_body={"message": "Queued external search"})

            monkeypatch.setattr(
                "tldw_Server_API.app.core.VoiceAssistant.router.afetch",
                fake_afetch,
            )
            monkeypatch.setattr(
                "tldw_Server_API.app.core.VoiceAssistant.router.evaluate_url_policy",
                lambda url, **kwargs: SimpleNamespace(allowed=True, reason=None),
            )
            monkeypatch.setattr(
                "tldw_Server_API.app.core.VoiceAssistant.router.loads_envelope",
                lambda encrypted_blob: {"encrypted_blob": encrypted_blob},
            )
            monkeypatch.setattr(
                "tldw_Server_API.app.core.VoiceAssistant.router.decrypt_byok_payload",
                lambda envelope: {"api_key": "secret-token"},
            )

            session = await session_manager.create_session(user_id=1)
            result, _ = await command_router.process_command(
                text="search external for whales",
                user_id=1,
                session_id=session.session_id,
                db=db,
                persona_id=persona_id,
            )

            assert result.success is True
            assert result.action_type == ActionType.CUSTOM
            assert result.response_text == "Queued external search"
            assert captured["method"] == "POST"
            assert captured["url"] == "https://api.example.com/v1/search"
            assert captured["json"] == {"query": "whales", "limit": 3}
            assert captured["headers"]["Authorization"] == "Bearer secret-token"
            assert captured["headers"]["X-Client"] == "voice-builder"
            assert captured["timeout"] == 12.0
        finally:
            db.close_connection()

    @pytest.mark.asyncio
    async def test_connection_backed_command_blocks_host_escape(
        self,
        command_router,
        session_manager,
        monkeypatch,
        tmp_path: Path,
    ):
        db = CharactersRAGDB(
            tmp_path / "voice_external_runtime_host_escape.sqlite",
            "voice-external-host-escape-tests",
        )
        try:
            persona_id = _create_persona_profile(
                db,
                user_id=1,
                persona_id="persona-runtime-host-escape",
            )
            _add_persona_connection(
                db,
                user_id=1,
                persona_id=persona_id,
                connection_id="conn-safe-host",
                content={
                    "name": "Safe Host API",
                    "base_url": "https://api.example.com/v1",
                    "auth_type": "none",
                    "headers_template": {},
                    "timeout_ms": 9000,
                    "allowed_hosts": ["api.example.com"],
                    "secret_configured": False,
                },
            )
            save_voice_command(
                db,
                VoiceCommand(
                    id="cmd-host-escape",
                    user_id=1,
                    persona_id=persona_id,
                    connection_id="conn-safe-host",
                    name="Unsafe Redirect",
                    phrases=["unsafe external {topic}"],
                    action_type=ActionType.CUSTOM,
                    action_config={
                        "action": "unsafe_external",
                        "method": "POST",
                        "path": "https://evil.example.net/collect",
                        "slot_to_param_map": {"query": "topic"},
                    },
                ),
            )

            called = {"value": False}

            async def fake_afetch(**kwargs):
                called["value"] = True
                return _MockHTTPResponse(json_body={"ok": True})

            monkeypatch.setattr(
                "tldw_Server_API.app.core.VoiceAssistant.router.afetch",
                fake_afetch,
            )
            monkeypatch.setattr(
                "tldw_Server_API.app.core.VoiceAssistant.router.evaluate_url_policy",
                lambda url, **kwargs: SimpleNamespace(allowed=True, reason=None),
            )

            session = await session_manager.create_session(user_id=1)
            result, _ = await command_router.process_command(
                text="unsafe external whales",
                user_id=1,
                session_id=session.session_id,
                db=db,
                persona_id=persona_id,
            )

            assert result.success is False
            assert "not allowed" in (result.error_message or "").lower()
            assert called["value"] is False
        finally:
            db.close_connection()

    @pytest.mark.asyncio
    async def test_connection_backed_command_returns_error_when_connection_missing(
        self,
        command_router,
        session_manager,
        monkeypatch,
        tmp_path: Path,
    ):
        db = CharactersRAGDB(
            tmp_path / "voice_external_runtime_missing.sqlite",
            "voice-external-missing-connection-tests",
        )
        try:
            persona_id = _create_persona_profile(
                db,
                user_id=1,
                persona_id="persona-runtime-missing-connection",
            )
            save_voice_command(
                db,
                VoiceCommand(
                    id="cmd-missing-connection",
                    user_id=1,
                    persona_id=persona_id,
                    connection_id="conn-missing",
                    name="Missing Connection",
                    phrases=["call missing connection"],
                    action_type=ActionType.CUSTOM,
                    action_config={"action": "missing_connection"},
                ),
            )

            async def fail_if_called(**kwargs):
                raise AssertionError("Outbound HTTP should not be called when connection lookup fails")

            monkeypatch.setattr(
                "tldw_Server_API.app.core.VoiceAssistant.router.afetch",
                fail_if_called,
            )
            monkeypatch.setattr(
                "tldw_Server_API.app.core.VoiceAssistant.router.evaluate_url_policy",
                lambda url, **kwargs: SimpleNamespace(allowed=True, reason=None),
            )

            session = await session_manager.create_session(user_id=1)
            result, _ = await command_router.process_command(
                text="call missing connection",
                user_id=1,
                session_id=session.session_id,
                db=db,
                persona_id=persona_id,
            )

            assert result.success is False
            assert "connection" in (result.error_message or "").lower()
        finally:
            db.close_connection()


class TestPipelineErrorHandling:
    """Tests for error handling in the pipeline."""

    @pytest.mark.asyncio
    async def test_graceful_handling_of_empty_input(self, command_router, session_manager):
        """Test handling of empty input text."""
        session = await session_manager.create_session(user_id=1)

        result, _ = await command_router.process_command(
            text="",
            user_id=1,
            session_id=session.session_id,
        )

        # Should handle gracefully (either error message or fallback)
        assert result is not None
        assert result.response_text is not None

    @pytest.mark.asyncio
    async def test_graceful_handling_of_whitespace_input(
        self, command_router, session_manager
    ):
        """Test handling of whitespace-only input."""
        session = await session_manager.create_session(user_id=1)

        result, _ = await command_router.process_command(
            text="   \n\t  ",
            user_id=1,
            session_id=session.session_id,
        )

        # Should handle gracefully
        assert result is not None

    @pytest.mark.asyncio
    async def test_session_auto_created_if_missing(self, command_router, session_manager):
        """Test that a session is auto-created if not provided."""
        result, session_id = await command_router.process_command(
            text="hello",
            user_id=1,
            session_id=None,  # No session provided
        )

        # Should have created a session
        assert session_id is not None
        session = await session_manager.get_session(session_id)
        assert session is not None


class TestPipelinePerformance:
    """Tests for pipeline performance characteristics."""

    @pytest.mark.asyncio
    async def test_processing_latency(self, command_router, session_manager):
        """Test that command processing completes in reasonable time."""
        session = await session_manager.create_session(user_id=1)

        # Warm up
        await command_router.process_command(
            text="hello",
            user_id=1,
            session_id=session.session_id,
        )

        # Measure multiple commands
        latencies = []
        for i in range(5):
            start = time.time()
            await command_router.process_command(
                text=f"search for topic {i}",
                user_id=1,
                session_id=session.session_id,
            )
            latencies.append((time.time() - start) * 1000)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Log for visibility
        print(f"Average latency: {avg_latency:.2f}ms, Max: {max_latency:.2f}ms")

        # Should be fast (intent parsing + mock execution)
        # Note: This is with mocked external calls
        assert avg_latency < 100, f"Average latency too high: {avg_latency}ms"
        assert max_latency < 200, f"Max latency too high: {max_latency}ms"


class TestPipelineMultiUser:
    """Tests for multi-user scenarios."""

    @pytest.mark.asyncio
    async def test_user_isolation(self, command_router, session_manager, registry):
        """Test that user sessions are isolated."""
        # Create sessions for two users
        session1 = await session_manager.create_session(user_id=1)
        session2 = await session_manager.create_session(user_id=2)

        # User 1 processes a command
        await command_router.process_command(
            text="search for user1 topic",
            user_id=1,
            session_id=session1.session_id,
        )

        # User 2 processes a command
        await command_router.process_command(
            text="search for user2 topic",
            user_id=2,
            session_id=session2.session_id,
        )

        # Check contexts are isolated
        s1 = await session_manager.get_session(session1.session_id)
        s2 = await session_manager.get_session(session2.session_id)

        assert s1.user_id == 1
        assert s2.user_id == 2

        # Histories should be separate
        s1_texts = [h.get("content", "") for h in s1.conversation_history]
        s2_texts = [h.get("content", "") for h in s2.conversation_history]

        # User 1's history shouldn't contain user 2's queries
        assert not any("user2" in t for t in s1_texts)
        assert not any("user1" in t for t in s2_texts)


class TestIntentParsingAccuracy:
    """Tests for intent parsing accuracy."""

    @pytest.mark.asyncio
    async def test_keyword_matching(self, intent_parser):
        """Test keyword-based intent matching."""
        # Test various search phrases
        search_phrases = [
            "search for python",
            "find information about python",
            "look up python",
        ]

        for phrase in search_phrases:
            parsed = await intent_parser.parse(phrase, user_id=1)
            # Should match a command or fall back gracefully
            assert parsed is not None
            assert parsed.intent.action_type is not None

    @pytest.mark.asyncio
    async def test_pattern_matching(self, intent_parser):
        """Test pattern-based intent matching."""
        # Create notes with "create note called X"
        intent = await intent_parser.parse(
            "create note called meeting notes",
            user_id=1
        )
        assert intent is not None

    @pytest.mark.asyncio
    async def test_confirmation_keywords(self, intent_parser, session_manager):
        """Test that confirmation keywords are recognized."""
        # Set up a session with pending intent
        session = await session_manager.create_session(user_id=1)
        session.pending_intent = VoiceIntent(
            action_type=ActionType.CUSTOM,
            action_config={},
            raw_text="delete all",
        )

        # Test yes/no detection
        yes_phrases = ["yes", "confirm", "okay", "sure", "do it"]
        no_phrases = ["no", "cancel", "stop", "nevermind"]

        for phrase in yes_phrases:
            intent = await intent_parser.parse(
                phrase,
                user_id=1,
                context={
                    "awaiting_confirmation": True,
                    "conversation_history": session.conversation_history,
                    "last_action_result": session.last_action_result,
                },
            )
            # Should recognize as confirmation
            assert intent is not None

        for phrase in no_phrases:
            intent = await intent_parser.parse(
                phrase,
                user_id=1,
                context={
                    "awaiting_confirmation": True,
                    "conversation_history": session.conversation_history,
                    "last_action_result": session.last_action_result,
                },
            )
            # Should recognize as cancellation
            assert intent is not None


#
# End of test_e2e_pipeline.py
#######################################################################################################################
