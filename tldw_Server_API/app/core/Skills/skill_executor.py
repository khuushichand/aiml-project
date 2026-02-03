# app/core/Skills/skill_executor.py
#
# Execute skills with argument substitution and fork support
#
"""
Skill Executor
==============

Executes skills with:
- Argument substitution ($ARGUMENTS, $0, $1, etc.)
- Tool resolution against MCP registry
- Inline and fork execution modes
"""

import re
import shlex
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class SkillExecutionResult:
    """Result of skill execution."""
    skill_name: str
    rendered_prompt: str
    allowed_tools: list[str] = field(default_factory=list)
    model_override: Optional[str] = None
    execution_mode: str = "inline"  # "inline" or "fork"
    fork_output: Optional[str] = None


@dataclass
class RequestContext:
    """Context for skill execution."""
    user_id: int
    default_model: Optional[str] = None
    conversation_id: Optional[str] = None
    available_tools: list[str] = field(default_factory=list)


class SkillExecutor:
    """Execute skills with argument substitution and tool resolution."""

    # Pattern for $ARGUMENTS[N] or $N
    INDEXED_ARG_PATTERN = re.compile(r'\$ARGUMENTS\[(\d+)\]|\$(\d+)')

    def substitute_arguments(self, content: str, arguments: str) -> str:
        """
        Replace argument placeholders with actual values.

        Supports:
        - $ARGUMENTS - all arguments as a single string
        - $ARGUMENTS[N] - specific argument by index (0-based)
        - $N - shorthand for $ARGUMENTS[N]

        Args:
            content: The skill content with placeholders
            arguments: The arguments string

        Returns:
            Content with arguments substituted
        """
        if not content:
            return content

        # Parse arguments
        try:
            args = shlex.split(arguments) if arguments else []
        except ValueError:
            # If shlex fails, fall back to simple split
            args = arguments.split() if arguments else []

        def replace_indexed(match: re.Match) -> str:
            # Get the index from either group
            idx_str = match.group(1) or match.group(2)
            idx = int(idx_str)
            if idx < len(args):
                return args[idx]
            return ""  # Empty string for out-of-range indices

        # Replace indexed arguments first
        result = self.INDEXED_ARG_PATTERN.sub(replace_indexed, content)

        # Replace $ARGUMENTS with the full arguments string
        result = result.replace("$ARGUMENTS", arguments or "")

        return result

    def resolve_allowed_tools(
        self,
        allowed_tools: Optional[list[str]],
        available_tools: Optional[list[str]] = None,
    ) -> list[str]:
        """
        Resolve allowed-tools against available tools.

        Handles patterns like:
        - Simple names: "Read", "Grep", "Glob"
        - Tool with command restriction: "Bash(git *)"

        Args:
            allowed_tools: List of allowed tool specs from skill
            available_tools: List of available tools from MCP registry

        Returns:
            Resolved list of allowed tool names/patterns
        """
        if not allowed_tools:
            return []

        resolved = []
        for tool_spec in allowed_tools:
            tool_spec = tool_spec.strip()
            if not tool_spec:
                continue

            if "(" in tool_spec:
                # Tool with command restriction: "Bash(git *)"
                # Keep the full pattern for command validation later
                resolved.append(tool_spec)
            else:
                # Simple tool name - add if no available_tools check
                # or if it's in the available tools
                if available_tools is None or tool_spec in available_tools:
                    resolved.append(tool_spec)
                else:
                    logger.warning(f"Tool '{tool_spec}' not available, skipping")

        return resolved

    def filter_tools_for_skill(
        self,
        all_tools: list[dict[str, Any]],
        allowed_tools: list[str],
    ) -> list[dict[str, Any]]:
        """
        Filter MCP tools based on skill's allowed-tools.

        Args:
            all_tools: List of all available MCP tool definitions
            allowed_tools: List of allowed tool patterns from skill

        Returns:
            Filtered list of tool definitions
        """
        if not allowed_tools:
            return all_tools  # No restriction

        # Extract base tool names from patterns
        allowed_base_names = set()
        for tool_spec in allowed_tools:
            if "(" in tool_spec:
                base_name = tool_spec.split("(")[0].strip()
            else:
                base_name = tool_spec.strip()
            allowed_base_names.add(base_name)

        # Filter tools
        filtered = []
        for tool in all_tools:
            tool_name = tool.get("name", "")
            if tool_name in allowed_base_names:
                filtered.append(tool)

        return filtered

    def matches_tool_pattern(self, tool_name: str, command: str, pattern: str) -> bool:
        """
        Check if a tool invocation matches an allowed pattern.

        Examples:
        - "Bash(git *)" matches Bash tool with command "git status"
        - "Bash(npm run *)" matches Bash tool with command "npm run test"

        Args:
            tool_name: The tool being invoked (e.g., "Bash")
            command: The command/arguments for the tool
            pattern: The allowed pattern (e.g., "Bash(git *)")

        Returns:
            True if the invocation matches the pattern
        """
        if "(" not in pattern:
            # Simple tool name, just match the name
            return tool_name == pattern.strip()

        # Extract base name and command pattern
        match = re.match(r'^(\w+)\((.+)\)$', pattern.strip())
        if not match:
            return False

        base_name, cmd_pattern = match.groups()

        if tool_name != base_name:
            return False

        # Convert glob-style pattern to regex
        # * matches any characters (including spaces for command args)
        regex_pattern = re.escape(cmd_pattern)
        regex_pattern = regex_pattern.replace(r'\*', '.*')
        regex_pattern = f'^{regex_pattern}$'

        try:
            return bool(re.match(regex_pattern, command.strip()))
        except re.error:
            logger.warning(f"Invalid command pattern: {pattern}")
            return False

    async def execute(
        self,
        skill_data: dict[str, Any],
        arguments: str,
        context: Optional[RequestContext] = None,
    ) -> SkillExecutionResult:
        """
        Execute a skill.

        Args:
            skill_data: The skill data dict (from SkillsService.get_skill)
            arguments: Arguments to pass to the skill
            context: Request context for execution

        Returns:
            SkillExecutionResult with rendered prompt and metadata
        """
        skill_name = skill_data.get("name", "unknown")
        content = skill_data.get("content", "")
        allowed_tools = skill_data.get("allowed_tools") or []
        model = skill_data.get("model")
        execution_context = skill_data.get("context", "inline")

        # Substitute arguments
        rendered = self.substitute_arguments(content, arguments)

        # Resolve allowed tools
        available = context.available_tools if context else None
        resolved_tools = self.resolve_allowed_tools(allowed_tools, available)

        if execution_context == "fork":
            return await self._execute_forked(
                skill_name=skill_name,
                rendered_prompt=rendered,
                allowed_tools=resolved_tools,
                model=model,
                context=context,
            )
        else:
            return self._execute_inline(
                skill_name=skill_name,
                rendered_prompt=rendered,
                allowed_tools=resolved_tools,
                model=model,
            )

    def _execute_inline(
        self,
        skill_name: str,
        rendered_prompt: str,
        allowed_tools: list[str],
        model: Optional[str] = None,
    ) -> SkillExecutionResult:
        """
        Inline execution - inject prompt into current conversation.

        Returns the rendered prompt for inclusion in the main conversation.
        """
        return SkillExecutionResult(
            skill_name=skill_name,
            rendered_prompt=rendered_prompt,
            allowed_tools=allowed_tools,
            model_override=model,
            execution_mode="inline",
        )

    async def _execute_forked(
        self,
        skill_name: str,
        rendered_prompt: str,
        allowed_tools: list[str],
        model: Optional[str] = None,
        context: Optional[RequestContext] = None,
    ) -> SkillExecutionResult:
        """
        Fork execution - run in isolated subagent context.

        Creates an isolated chat session for skill execution.
        """
        # For now, implement a simple fork that returns the rendered prompt
        # with a note about fork execution. Full fork implementation would
        # create an isolated chat session and execute the skill there.

        # TODO: Full fork implementation would:
        # 1. Create isolated chat session
        # 2. Execute with skill's allowed-tools
        # 3. Capture and return the subagent's response

        # Placeholder: Return rendered prompt with fork metadata
        fork_header = f"[Executing skill '{skill_name}' in fork mode]\n\n"

        logger.info(
            f"Fork execution for skill '{skill_name}' - "
            f"full fork mode requires chat service integration"
        )

        # For now, return the prompt as if inline but mark as fork
        return SkillExecutionResult(
            skill_name=skill_name,
            rendered_prompt=fork_header + rendered_prompt,
            allowed_tools=allowed_tools,
            model_override=model,
            execution_mode="fork",
            fork_output=None,  # Would contain subagent response
        )


# Skill tool definition for LLM invocation
SKILL_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "Skill",
        "description": (
            "Execute a skill with optional arguments. Use this to invoke available skills "
            "that provide specialized capabilities. Check the available-skills context for "
            "skill names and their purposes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "skill": {
                    "type": "string",
                    "description": "The skill name to execute (e.g., 'summarize', 'code-review')"
                },
                "args": {
                    "type": "string",
                    "description": "Optional arguments for the skill (e.g., 'detailed' or 'issue-123')"
                }
            },
            "required": ["skill"]
        }
    }
}
