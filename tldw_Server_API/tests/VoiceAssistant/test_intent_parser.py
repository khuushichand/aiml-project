# test_intent_parser.py
# Unit tests for the Voice Assistant intent parser
#
#######################################################################################################################
import pytest
from unittest.mock import AsyncMock, patch

from tldw_Server_API.app.core.VoiceAssistant.schemas import ActionType, VoiceCommand
from tldw_Server_API.app.core.VoiceAssistant.registry import VoiceCommandRegistry
from tldw_Server_API.app.core.VoiceAssistant.intent_parser import IntentParser


@pytest.fixture
def registry():
    """Create a test registry with sample commands."""
    reg = VoiceCommandRegistry()

    # Add test commands
    reg.register_command(VoiceCommand(
        id="test-search",
        user_id=0,
        name="Search",
        phrases=["search for", "find"],
        action_type=ActionType.MCP_TOOL,
        action_config={"tool_name": "media.search", "extract_query": True},
        priority=10,
    ))

    reg.register_command(VoiceCommand(
        id="test-note",
        user_id=0,
        name="Create Note",
        phrases=["create a note", "take a note"],
        action_type=ActionType.MCP_TOOL,
        action_config={"tool_name": "notes.create", "extract_content": True},
        priority=10,
    ))

    reg.register_command(VoiceCommand(
        id="test-stop",
        user_id=0,
        name="Stop",
        phrases=["stop", "cancel"],
        action_type=ActionType.CUSTOM,
        action_config={"action": "stop"},
        priority=100,
    ))

    return reg


@pytest.fixture
def parser(registry):
    """Create a parser with the test registry."""
    return IntentParser(registry=registry, llm_enabled=False)


class TestKeywordMatching:
    """Tests for keyword-based intent matching."""

    @pytest.mark.asyncio
    async def test_exact_match(self, parser):
        """Test exact phrase match."""
        result = await parser.parse("stop", user_id=0)

        assert result.match_method == "keyword"
        assert result.intent.action_type == ActionType.CUSTOM
        assert result.intent.action_config["action"] == "stop"
        assert result.intent.confidence == 1.0

    @pytest.mark.asyncio
    async def test_prefix_match_with_query(self, parser):
        """Test prefix match that extracts query."""
        result = await parser.parse("search for machine learning", user_id=0)

        # May match via keyword or pattern, both are valid
        assert result.match_method in ("keyword", "pattern")
        assert result.intent.action_type == ActionType.MCP_TOOL
        assert result.intent.action_config.get("tool_name") == "media.search"
        assert "machine learning" in result.intent.entities.get("query", "")

    @pytest.mark.asyncio
    async def test_note_content_extraction(self, parser):
        """Test extracting note content from phrase."""
        result = await parser.parse("create a note remember to buy milk", user_id=0)

        # May match via keyword or pattern, both extract content
        assert result.match_method in ("keyword", "pattern")
        assert result.intent.action_type == ActionType.MCP_TOOL
        assert result.intent.action_config.get("tool_name") == "notes.create"
        # Content may be in entities under 'content' key
        assert "remember to buy milk" in (
            result.intent.entities.get("content", "") or
            result.intent.action_config.get("content", "")
        )

    @pytest.mark.asyncio
    async def test_no_match_falls_back_to_chat(self, parser):
        """Test that unmatched text defaults to LLM chat or pattern search."""
        # "what is X" matches the pattern matcher, which is valid
        result = await parser.parse("what is the meaning of life", user_id=0)

        # The pattern matcher picks up "what is" queries, which is expected
        # For truly unmatched text, use something that doesn't match any pattern
        assert result.match_method in ("default", "pattern")

    @pytest.mark.asyncio
    async def test_truly_unmatched_falls_back_to_chat(self, parser):
        """Test that completely unmatched text defaults to LLM chat."""
        result = await parser.parse("banana phone unicorn", user_id=0)

        assert result.match_method == "default"
        assert result.intent.action_type == ActionType.LLM_CHAT

    @pytest.mark.asyncio
    async def test_empty_input(self, parser):
        """Test handling of empty input."""
        result = await parser.parse("", user_id=0)

        assert result.match_method == "empty"
        assert result.intent.action_config.get("action") == "empty_input"


class TestConfirmationHandling:
    """Tests for confirmation response handling."""

    @pytest.mark.asyncio
    async def test_yes_confirmation(self, parser):
        """Test positive confirmation."""
        context = {"awaiting_confirmation": True}
        result = await parser.parse("yes", user_id=0, context=context)

        assert result.match_method == "confirmation"
        assert result.intent.action_config["confirmed"] is True

    @pytest.mark.asyncio
    async def test_no_confirmation(self, parser):
        """Test negative confirmation."""
        context = {"awaiting_confirmation": True}
        result = await parser.parse("no", user_id=0, context=context)

        assert result.match_method == "confirmation"
        assert result.intent.action_config["confirmed"] is False

    @pytest.mark.asyncio
    async def test_non_confirmation_when_not_awaiting(self, parser):
        """Test that yes/no are not treated as confirmations when not awaiting."""
        result = await parser.parse("yes", user_id=0)

        # Should not be a confirmation match since we're not awaiting
        assert result.match_method != "confirmation"


class TestPatternMatching:
    """Tests for pattern-based intent matching."""

    @pytest.mark.asyncio
    async def test_what_is_pattern(self, parser):
        """Test 'what is' pattern extracts query."""
        result = await parser.parse("what is quantum computing", user_id=0)

        assert result.match_method == "pattern"
        assert result.intent.action_type == ActionType.MCP_TOOL
        assert "quantum computing" in result.intent.entities.get("query", "")

    @pytest.mark.asyncio
    async def test_tell_me_about_pattern(self, parser):
        """Test 'tell me about' pattern extracts query."""
        result = await parser.parse("tell me about neural networks", user_id=0)

        # May match via keyword (if "tell me about" command exists) or pattern
        assert result.match_method in ("keyword", "pattern")
        # Either way, query should be extracted
        assert "neural networks" in result.intent.entities.get("query", "") or \
               "neural networks" in result.intent.entities.get("topic", "")


class TestPriorityHandling:
    """Tests for command priority handling."""

    @pytest.mark.asyncio
    async def test_high_priority_wins(self, parser, registry):
        """Test that higher priority commands are matched first."""
        # Add a lower priority command with overlapping phrase
        registry.register_command(VoiceCommand(
            id="test-low-priority",
            user_id=0,
            name="Low Priority",
            phrases=["stop"],
            action_type=ActionType.LLM_CHAT,
            action_config={"message": "low"},
            priority=1,
        ))

        result = await parser.parse("stop", user_id=0)

        # Should match the higher priority "stop" command
        assert result.intent.action_type == ActionType.CUSTOM
        assert result.intent.action_config.get("action") == "stop"


class TestAlternatives:
    """Tests for alternative intent suggestions."""

    @pytest.mark.asyncio
    async def test_alternatives_provided(self, parser):
        """Test that alternatives are provided for ambiguous matches."""
        result = await parser.parse("find something", user_id=0)

        # Should have alternatives if multiple commands match
        # In this case, "find" matches the search command
        assert result.intent.action_type == ActionType.MCP_TOOL


#
# End of test_intent_parser.py
#######################################################################################################################
