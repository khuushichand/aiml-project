# test_registry.py
# Unit tests for the Voice Command Registry
#
#######################################################################################################################
import pytest

from tldw_Server_API.app.core.VoiceAssistant.schemas import ActionType, VoiceCommand
from tldw_Server_API.app.core.VoiceAssistant.registry import VoiceCommandRegistry


@pytest.fixture
def registry():
    """Create a fresh registry for each test."""
    reg = VoiceCommandRegistry()
    # Mark as loaded to prevent auto-loading defaults during find_matching_commands
    reg._loaded = True
    return reg


class TestCommandRegistration:
    """Tests for command registration."""

    def test_register_system_command(self, registry):
        """Test registering a system command (user_id=0)."""
        command = VoiceCommand(
            id="test-cmd",
            user_id=0,
            name="Test Command",
            phrases=["test"],
            action_type=ActionType.CUSTOM,
            action_config={"action": "test"},
        )

        registry.register_command(command)
        retrieved = registry.get_command("test-cmd")

        assert retrieved is not None
        assert retrieved.name == "Test Command"

    def test_register_user_command(self, registry):
        """Test registering a user-specific command."""
        command = VoiceCommand(
            id="user-cmd",
            user_id=123,
            name="User Command",
            phrases=["my command"],
            action_type=ActionType.CUSTOM,
            action_config={"action": "user"},
        )

        registry.register_command(command)
        retrieved = registry.get_command("user-cmd", user_id=123)

        assert retrieved is not None
        assert retrieved.name == "User Command"

    def test_unregister_command(self, registry):
        """Test unregistering a command."""
        command = VoiceCommand(
            id="to-remove",
            user_id=0,
            name="To Remove",
            phrases=["remove"],
            action_type=ActionType.CUSTOM,
            action_config={},
        )

        registry.register_command(command)
        result = registry.unregister_command("to-remove")

        assert result is True
        assert registry.get_command("to-remove") is None

    def test_unregister_nonexistent(self, registry):
        """Test unregistering a command that doesn't exist."""
        result = registry.unregister_command("nonexistent")
        assert result is False


class TestCommandRetrieval:
    """Tests for command retrieval."""

    def test_get_command_user_before_system(self, registry):
        """Test that user commands are checked before system commands."""
        # Register system command
        sys_cmd = VoiceCommand(
            id="shared-id",
            user_id=0,
            name="System",
            phrases=["shared"],
            action_type=ActionType.CUSTOM,
            action_config={"source": "system"},
        )
        registry.register_command(sys_cmd)

        # Register user command with same ID
        user_cmd = VoiceCommand(
            id="shared-id",
            user_id=123,
            name="User",
            phrases=["shared"],
            action_type=ActionType.CUSTOM,
            action_config={"source": "user"},
        )
        registry.register_command(user_cmd)

        # Should return user command when user_id is provided
        result = registry.get_command("shared-id", user_id=123)
        assert result.action_config["source"] == "user"

    def test_get_all_commands(self, registry):
        """Test getting all commands for a user."""
        # Add system commands
        registry.register_command(VoiceCommand(
            id="sys1",
            user_id=0,
            name="System 1",
            phrases=["sys1"],
            action_type=ActionType.CUSTOM,
            action_config={},
        ))

        # Add user commands
        registry.register_command(VoiceCommand(
            id="user1",
            user_id=123,
            name="User 1",
            phrases=["user1"],
            action_type=ActionType.CUSTOM,
            action_config={},
        ))

        all_cmds = registry.get_all_commands(user_id=123, include_system=True)
        assert len(all_cmds) == 2

        user_only = registry.get_all_commands(user_id=123, include_system=False)
        assert len(user_only) == 1
        assert user_only[0].name == "User 1"

    def test_get_all_commands_sorted_by_priority(self, registry):
        """Test that commands are sorted by priority descending."""
        registry.register_command(VoiceCommand(
            id="low",
            user_id=0,
            name="Low Priority",
            phrases=["low"],
            action_type=ActionType.CUSTOM,
            action_config={},
            priority=1,
        ))

        registry.register_command(VoiceCommand(
            id="high",
            user_id=0,
            name="High Priority",
            phrases=["high"],
            action_type=ActionType.CUSTOM,
            action_config={},
            priority=100,
        ))

        registry.register_command(VoiceCommand(
            id="mid",
            user_id=0,
            name="Mid Priority",
            phrases=["mid"],
            action_type=ActionType.CUSTOM,
            action_config={},
            priority=50,
        ))

        cmds = registry.get_all_commands()
        assert cmds[0].name == "High Priority"
        assert cmds[1].name == "Mid Priority"
        assert cmds[2].name == "Low Priority"


class TestCommandMatching:
    """Tests for command phrase matching."""

    def test_exact_match(self, registry):
        """Test exact phrase match."""
        registry.register_command(VoiceCommand(
            id="test",
            user_id=0,
            name="Test",
            phrases=["stop"],
            action_type=ActionType.CUSTOM,
            action_config={},
        ))

        matches = registry.find_matching_commands("stop")
        assert len(matches) == 1
        assert matches[0][0].name == "Test"
        assert matches[0][2] == 1.0  # Exact match score

    def test_prefix_match(self, registry):
        """Test prefix phrase match."""
        registry.register_command(VoiceCommand(
            id="search",
            user_id=0,
            name="Search",
            phrases=["search for"],
            action_type=ActionType.MCP_TOOL,
            action_config={"tool_name": "search"},
        ))

        matches = registry.find_matching_commands("search for cats")
        assert len(matches) == 1
        assert matches[0][0].name == "Search"
        assert 0 < matches[0][2] < 1.0  # Partial match score

    def test_no_match(self, registry):
        """Test no matches found."""
        registry.register_command(VoiceCommand(
            id="test",
            user_id=0,
            name="Test",
            phrases=["hello"],
            action_type=ActionType.CUSTOM,
            action_config={},
        ))

        matches = registry.find_matching_commands("goodbye")
        assert len(matches) == 0

    def test_multiple_matches(self, registry):
        """Test multiple commands matching."""
        registry.register_command(VoiceCommand(
            id="find1",
            user_id=0,
            name="Find Media",
            phrases=["find"],
            action_type=ActionType.MCP_TOOL,
            action_config={"tool_name": "media.search"},
            priority=10,
        ))

        registry.register_command(VoiceCommand(
            id="find2",
            user_id=0,
            name="Find Notes",
            phrases=["find notes", "find in notes"],
            action_type=ActionType.MCP_TOOL,
            action_config={"tool_name": "notes.search"},
            priority=15,
        ))

        matches = registry.find_matching_commands("find something")
        assert len(matches) >= 1

    def test_disabled_commands_excluded(self, registry):
        """Test that disabled commands are not matched."""
        registry.register_command(VoiceCommand(
            id="disabled",
            user_id=0,
            name="Disabled",
            phrases=["disabled"],
            action_type=ActionType.CUSTOM,
            action_config={},
            enabled=False,
        ))

        matches = registry.find_matching_commands("disabled")
        assert len(matches) == 0


class TestDefaultsLoading:
    """Tests for loading default commands."""

    def test_load_builtin_defaults(self):
        """Test loading built-in defaults."""
        # Create fresh registry without marking as loaded
        registry = VoiceCommandRegistry()
        registry._load_builtin_defaults()

        # Should have some default commands
        all_cmds = registry.get_all_commands()
        assert len(all_cmds) > 0

        # Should have stop command
        stop_matches = registry.find_matching_commands("stop")
        assert len(stop_matches) > 0

    def test_load_defaults_idempotent(self):
        """Test that loading defaults multiple times is safe."""
        # Create fresh registry without marking as loaded
        registry = VoiceCommandRegistry()
        registry.load_defaults()
        count1 = len(registry.get_all_commands())

        registry.load_defaults()
        count2 = len(registry.get_all_commands())

        assert count1 == count2


class TestDatabaseLoading:
    """Tests for loading commands from database."""

    def test_load_from_db_rows(self):
        """Test loading commands from database row format."""
        registry = VoiceCommandRegistry()
        registry._loaded = True

        db_rows = [
            {
                "id": "db-cmd-1",
                "name": "DB Command",
                "phrases": '["database", "from db"]',
                "action_type": "custom",
                "action_config": '{"action": "db_action"}',
                "priority": 5,
                "enabled": 1,
                "requires_confirmation": 0,
            }
        ]

        registry.load_user_commands_from_db(user_id=456, db_rows=db_rows)

        cmd = registry.get_command("db-cmd-1", user_id=456)
        assert cmd is not None
        assert cmd.name == "DB Command"
        assert "database" in cmd.phrases
        assert cmd.action_config["action"] == "db_action"


#
# End of test_registry.py
#######################################################################################################################
