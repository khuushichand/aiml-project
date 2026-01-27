# VoiceAssistant/registry.py
# Voice Command Registry - Manages storage and retrieval of voice commands
#
#######################################################################################################################
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger

from .schemas import ActionType, VoiceCommand


class VoiceCommandRegistry:
    """
    Manages voice command registration and lookup.

    Commands can be loaded from:
    - Database (per-user custom commands)
    - YAML config file (system defaults)
    - In-memory registration (runtime additions)
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the voice command registry.

        Args:
            config_path: Path to YAML config file with default commands.
                        If None, loads from Config_Files/voice_commands.yaml
        """
        self._commands: Dict[str, VoiceCommand] = {}
        self._user_commands: Dict[int, Dict[str, VoiceCommand]] = {}
        self._config_path = config_path
        self._loaded = False

    def _get_default_config_path(self) -> Path:
        """Get the default config file path."""
        # Navigate up from this file to find Config_Files
        current_dir = Path(__file__).parent
        # tldw_Server_API/app/core/VoiceAssistant -> tldw_Server_API/Config_Files
        config_dir = current_dir.parent.parent.parent / "Config_Files"
        return config_dir / "voice_commands.yaml"

    def load_defaults(self) -> None:
        """Load default commands from YAML config file."""
        if self._loaded:
            return

        config_path = Path(self._config_path) if self._config_path else self._get_default_config_path()

        if not config_path.exists():
            logger.warning(f"Voice commands config not found at {config_path}, using built-in defaults")
            self._load_builtin_defaults()
            self._loaded = True
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            commands = config.get("commands", [])
            for cmd_data in commands:
                try:
                    command = VoiceCommand(
                        id=cmd_data.get("id", str(uuid.uuid4())),
                        user_id=0,  # System commands have user_id 0
                        name=cmd_data["name"],
                        phrases=cmd_data["phrases"],
                        action_type=ActionType(cmd_data["action_type"]),
                        action_config=cmd_data.get("action_config", {}),
                        priority=cmd_data.get("priority", 0),
                        enabled=cmd_data.get("enabled", True),
                        requires_confirmation=cmd_data.get("requires_confirmation", False),
                        description=cmd_data.get("description"),
                        created_at=datetime.utcnow(),
                    )
                    self._commands[command.id] = command
                except Exception as e:
                    logger.warning(f"Failed to load voice command '{cmd_data.get('name', 'unknown')}': {e}")

            logger.info(f"Loaded {len(self._commands)} voice commands from {config_path}")
            self._loaded = True

        except Exception as e:
            logger.error(f"Failed to load voice commands config: {e}")
            self._load_builtin_defaults()
            self._loaded = True

    def _load_builtin_defaults(self) -> None:
        """Load built-in default commands when config file is unavailable."""
        defaults = [
            VoiceCommand(
                id="builtin-search-media",
                user_id=0,
                name="Search Media",
                phrases=[
                    "search for",
                    "find",
                    "look up",
                    "search",
                ],
                action_type=ActionType.MCP_TOOL,
                action_config={
                    "tool_name": "media.search",
                    "extract_query": True,
                },
                priority=10,
                description="Search through ingested media content",
            ),
            VoiceCommand(
                id="builtin-create-note",
                user_id=0,
                name="Create Note",
                phrases=[
                    "create a note",
                    "make a note",
                    "take a note",
                    "note that",
                    "remember that",
                ],
                action_type=ActionType.MCP_TOOL,
                action_config={
                    "tool_name": "notes.create",
                    "extract_content": True,
                },
                priority=10,
                description="Create a new note",
            ),
            VoiceCommand(
                id="builtin-stop",
                user_id=0,
                name="Stop",
                phrases=["stop", "cancel", "never mind", "abort"],
                action_type=ActionType.CUSTOM,
                action_config={"action": "stop"},
                priority=100,  # High priority for control commands
                description="Stop current operation",
            ),
            VoiceCommand(
                id="builtin-help",
                user_id=0,
                name="Help",
                phrases=["help", "what can you do", "commands", "show commands"],
                action_type=ActionType.CUSTOM,
                action_config={"action": "help"},
                priority=50,
                description="List available commands",
            ),
        ]

        for cmd in defaults:
            self._commands[cmd.id] = cmd

        logger.info(f"Loaded {len(defaults)} built-in default voice commands")

    def register_command(self, command: VoiceCommand) -> None:
        """
        Register a voice command.

        Args:
            command: The command to register
        """
        if command.user_id == 0:
            self._commands[command.id] = command
        else:
            if command.user_id not in self._user_commands:
                self._user_commands[command.user_id] = {}
            self._user_commands[command.user_id][command.id] = command

        logger.debug(f"Registered voice command: {command.name} (id={command.id})")

    def unregister_command(self, command_id: str, user_id: int = 0) -> bool:
        """
        Unregister a voice command.

        Args:
            command_id: ID of the command to remove
            user_id: User ID (0 for system commands)

        Returns:
            True if command was removed, False if not found
        """
        if user_id == 0:
            if command_id in self._commands:
                del self._commands[command_id]
                return True
        else:
            if user_id in self._user_commands and command_id in self._user_commands[user_id]:
                del self._user_commands[user_id][command_id]
                return True
        return False

    def get_command(self, command_id: str, user_id: int = 0) -> Optional[VoiceCommand]:
        """
        Get a command by ID.

        Args:
            command_id: ID of the command
            user_id: User ID to check user commands first

        Returns:
            The command if found, None otherwise
        """
        # Check user commands first
        if user_id in self._user_commands and command_id in self._user_commands[user_id]:
            return self._user_commands[user_id][command_id]
        # Then check system commands
        return self._commands.get(command_id)

    def get_all_commands(
        self,
        user_id: int = 0,
        include_system: bool = True,
        include_disabled: bool = False,
    ) -> List[VoiceCommand]:
        """
        Get all available commands for a user.

        Args:
            user_id: User ID
            include_system: Whether to include system commands

        Returns:
            List of available commands, sorted by priority (descending)
        """
        commands = []

        if include_system:
            commands.extend(self._commands.values())

        if user_id in self._user_commands:
            commands.extend(self._user_commands[user_id].values())

        if include_disabled:
            return sorted(commands, key=lambda c: c.priority, reverse=True)

        # Filter enabled commands and sort by priority
        enabled = [c for c in commands if c.enabled]
        return sorted(enabled, key=lambda c: c.priority, reverse=True)

    def refresh_user_commands(
        self,
        db,
        user_id: int,
        include_disabled: bool = True,
    ) -> List[VoiceCommand]:
        """
        Replace cached user commands from the database.

        Args:
            db: CharactersRAGDB instance
            user_id: User ID
            include_disabled: Include disabled commands in the cache

        Returns:
            List of loaded commands
        """
        from .db_helpers import get_user_voice_commands

        commands = get_user_voice_commands(
            db,
            user_id=user_id,
            include_system=False,
            enabled_only=not include_disabled,
        )
        self._user_commands[user_id] = {cmd.id: cmd for cmd in commands}
        return commands

    def find_matching_commands(
        self,
        text: str,
        user_id: int = 0,
    ) -> List[tuple[VoiceCommand, str, float]]:
        """
        Find commands that match the given text.

        Uses prefix matching on registered phrases.

        Args:
            text: The text to match against
            user_id: User ID for user-specific commands

        Returns:
            List of (command, matched_phrase, score) tuples, sorted by score descending
        """
        if not self._loaded:
            self.load_defaults()

        text_lower = text.lower().strip()
        matches = []

        all_commands = self.get_all_commands(user_id)

        for command in all_commands:
            for phrase in command.phrases:
                phrase_lower = phrase.lower()
                score = 0.0

                # Exact match
                if text_lower == phrase_lower:
                    score = 1.0
                # Text starts with phrase (e.g., "search for cats" matches "search for")
                elif text_lower.startswith(phrase_lower):
                    # Score based on how much of the text the phrase covers
                    score = len(phrase_lower) / len(text_lower)
                    # Bonus for longer phrase matches
                    score = min(score + 0.1, 0.99)

                if score > 0:
                    matches.append((command, phrase, score))

        # Sort by score descending, then by priority descending
        matches.sort(key=lambda x: (x[2], x[0].priority), reverse=True)
        return matches

    def load_user_commands_from_db(
        self,
        user_id: int,
        db_rows: List[Dict[str, Any]],
    ) -> None:
        """
        Load user commands from database rows.

        Args:
            user_id: User ID
            db_rows: List of database row dicts with command data
        """
        if user_id not in self._user_commands:
            self._user_commands[user_id] = {}

        for row in db_rows:
            try:
                phrases = row.get("phrases", "[]")
                if isinstance(phrases, str):
                    phrases = json.loads(phrases)

                action_config = row.get("action_config", "{}")
                if isinstance(action_config, str):
                    action_config = json.loads(action_config)

                command = VoiceCommand(
                    id=row["id"],
                    user_id=user_id,
                    name=row["name"],
                    phrases=phrases,
                    action_type=ActionType(row["action_type"]),
                    action_config=action_config,
                    priority=row.get("priority", 0),
                    enabled=bool(row.get("enabled", 1)),
                    requires_confirmation=bool(row.get("requires_confirmation", 0)),
                    description=row.get("description"),
                )
                self._user_commands[user_id][command.id] = command
            except Exception as e:
                logger.warning(f"Failed to load user voice command from DB: {e}")

        logger.debug(f"Loaded {len(self._user_commands.get(user_id, {}))} commands for user {user_id}")


# Singleton instance
_registry_instance: Optional[VoiceCommandRegistry] = None


def get_voice_command_registry() -> VoiceCommandRegistry:
    """Get the singleton voice command registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = VoiceCommandRegistry()
    return _registry_instance


#
# End of VoiceAssistant/registry.py
#######################################################################################################################
