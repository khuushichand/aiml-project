# test_session.py
# Unit tests for the Voice Session Manager
#
#######################################################################################################################
import pytest
from datetime import datetime, timedelta

from tldw_Server_API.app.core.VoiceAssistant.session import VoiceSessionManager
from tldw_Server_API.app.core.VoiceAssistant.schemas import VoiceIntent, VoiceSessionState, ActionType


@pytest.fixture
def session_manager():
    """Create a fresh session manager for each test."""
    return VoiceSessionManager()


class TestSessionCreation:
    """Tests for session creation."""

    @pytest.mark.asyncio
    async def test_create_session(self, session_manager):
        """Test creating a new session."""
        session = await session_manager.create_session(user_id=1)

        assert session is not None
        assert session.user_id == 1
        assert session.state == VoiceSessionState.IDLE
        assert session.session_id is not None
        assert len(session.conversation_history) == 0

    @pytest.mark.asyncio
    async def test_create_session_with_metadata(self, session_manager):
        """Test creating a session with metadata."""
        metadata = {"client": "test", "version": "1.0"}
        session = await session_manager.create_session(user_id=1, metadata=metadata)

        assert session.metadata == metadata

    @pytest.mark.asyncio
    async def test_session_limit_per_user(self, session_manager):
        """Test that session limit per user is enforced."""
        # Create max sessions
        sessions = []
        for _ in range(session_manager.MAX_SESSIONS_PER_USER):
            session = await session_manager.create_session(user_id=1)
            sessions.append(session.session_id)

        # Create one more - should remove oldest
        new_session = await session_manager.create_session(user_id=1)

        # First session should be removed
        old_session = await session_manager.get_session(sessions[0], touch=False)
        assert old_session is None

        # New session should exist
        assert new_session is not None


class TestSessionRetrieval:
    """Tests for session retrieval."""

    @pytest.mark.asyncio
    async def test_get_session(self, session_manager):
        """Test getting an existing session."""
        created = await session_manager.create_session(user_id=1)
        retrieved = await session_manager.get_session(created.session_id)

        assert retrieved is not None
        assert retrieved.session_id == created.session_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, session_manager):
        """Test getting a session that doesn't exist."""
        result = await session_manager.get_session("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_or_create_existing(self, session_manager):
        """Test get_or_create with existing session."""
        created = await session_manager.create_session(user_id=1)
        session, was_created = await session_manager.get_or_create_session(
            session_id=created.session_id,
            user_id=1
        )

        assert session.session_id == created.session_id
        assert was_created is False

    @pytest.mark.asyncio
    async def test_get_or_create_new(self, session_manager):
        """Test get_or_create without existing session."""
        session, was_created = await session_manager.get_or_create_session(
            session_id=None,
            user_id=1
        )

        assert session is not None
        assert was_created is True


class TestSessionState:
    """Tests for session state management."""

    @pytest.mark.asyncio
    async def test_update_state(self, session_manager):
        """Test updating session state."""
        session = await session_manager.create_session(user_id=1)

        result = await session_manager.update_state(
            session.session_id,
            VoiceSessionState.PROCESSING
        )

        assert result is True

        updated = await session_manager.get_session(session.session_id)
        assert updated.state == VoiceSessionState.PROCESSING

    @pytest.mark.asyncio
    async def test_update_state_nonexistent(self, session_manager):
        """Test updating state of nonexistent session."""
        result = await session_manager.update_state(
            "nonexistent",
            VoiceSessionState.PROCESSING
        )
        assert result is False


class TestConversationHistory:
    """Tests for conversation history management."""

    @pytest.mark.asyncio
    async def test_add_turn(self, session_manager):
        """Test adding a conversation turn."""
        session = await session_manager.create_session(user_id=1)

        await session_manager.add_turn(
            session.session_id,
            "user",
            "Hello, assistant"
        )

        updated = await session_manager.get_session(session.session_id)
        assert len(updated.conversation_history) == 1
        assert updated.conversation_history[0]["role"] == "user"
        assert updated.conversation_history[0]["content"] == "Hello, assistant"

    @pytest.mark.asyncio
    async def test_conversation_history_limit(self, session_manager):
        """Test that conversation history is limited to 20 turns."""
        session = await session_manager.create_session(user_id=1)

        # Add more than 20 turns
        for i in range(25):
            await session_manager.add_turn(
                session.session_id,
                "user" if i % 2 == 0 else "assistant",
                f"Message {i}"
            )

        updated = await session_manager.get_session(session.session_id)
        assert len(updated.conversation_history) == 20

    @pytest.mark.asyncio
    async def test_get_context_messages(self, session_manager):
        """Test getting context messages for LLM."""
        session = await session_manager.create_session(user_id=1)

        await session_manager.add_turn(session.session_id, "user", "Hi")
        await session_manager.add_turn(session.session_id, "assistant", "Hello!")
        await session_manager.add_turn(session.session_id, "user", "How are you?")

        updated = await session_manager.get_session(session.session_id)
        context = updated.get_context_messages(max_turns=2)

        assert len(context) == 2
        assert context[0]["role"] == "assistant"
        assert context[1]["role"] == "user"


class TestPendingIntent:
    """Tests for pending intent management."""

    @pytest.mark.asyncio
    async def test_set_pending_intent(self, session_manager):
        """Test setting a pending intent."""
        session = await session_manager.create_session(user_id=1)

        intent = VoiceIntent(
            action_type=ActionType.MCP_TOOL,
            action_config={"tool_name": "test"},
            raw_text="test command",
        )

        await session_manager.set_pending_intent(session.session_id, intent)

        updated = await session_manager.get_session(session.session_id)
        assert updated.pending_intent is not None
        assert updated.pending_intent.raw_text == "test command"
        assert updated.state == VoiceSessionState.AWAITING_CONFIRMATION

    @pytest.mark.asyncio
    async def test_clear_pending_intent(self, session_manager):
        """Test clearing a pending intent."""
        session = await session_manager.create_session(user_id=1)

        intent = VoiceIntent(
            action_type=ActionType.MCP_TOOL,
            action_config={},
            raw_text="test",
        )

        await session_manager.set_pending_intent(session.session_id, intent)
        await session_manager.set_pending_intent(session.session_id, None)

        updated = await session_manager.get_session(session.session_id)
        assert updated.pending_intent is None
        assert updated.state == VoiceSessionState.IDLE


class TestSessionEnd:
    """Tests for session termination."""

    @pytest.mark.asyncio
    async def test_end_session(self, session_manager):
        """Test ending a session."""
        session = await session_manager.create_session(user_id=1)
        session_id = session.session_id

        result = await session_manager.end_session(session_id)
        assert result is True

        # Session should no longer exist
        retrieved = await session_manager.get_session(session_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_end_nonexistent_session(self, session_manager):
        """Test ending a session that doesn't exist."""
        result = await session_manager.end_session("nonexistent")
        assert result is False


class TestSessionCount:
    """Tests for session counting."""

    @pytest.mark.asyncio
    async def test_get_session_count_total(self, session_manager):
        """Test getting total session count."""
        await session_manager.create_session(user_id=1)
        await session_manager.create_session(user_id=2)
        await session_manager.create_session(user_id=1)

        count = session_manager.get_session_count()
        assert count == 3

    @pytest.mark.asyncio
    async def test_get_session_count_per_user(self, session_manager):
        """Test getting session count per user."""
        await session_manager.create_session(user_id=1)
        await session_manager.create_session(user_id=2)
        await session_manager.create_session(user_id=1)

        count_user1 = session_manager.get_session_count(user_id=1)
        count_user2 = session_manager.get_session_count(user_id=2)

        assert count_user1 == 2
        assert count_user2 == 1


#
# End of test_session.py
#######################################################################################################################
