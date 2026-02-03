# tests/Skills/unit/test_skill_executor.py
#
# Unit tests for the SkillExecutor class
#
import pytest

from tldw_Server_API.app.core.Skills.skill_executor import SkillExecutor, SKILL_TOOL_DEFINITION


class TestSkillExecutor:
    """Tests for the SkillExecutor class."""

    @pytest.fixture
    def executor(self):
        return SkillExecutor()

    class TestArgumentSubstitution:
        """Tests for argument substitution."""

        @pytest.fixture
        def executor(self):
            return SkillExecutor()

        def test_substitute_arguments_full(self, executor):
            """Test $ARGUMENTS substitution."""
            content = "Do something with $ARGUMENTS please."
            result = executor.substitute_arguments(content, "arg1 arg2 arg3")

            assert result == "Do something with arg1 arg2 arg3 please."

        def test_substitute_arguments_empty(self, executor):
            """Test $ARGUMENTS with empty arguments."""
            content = "Do something with $ARGUMENTS please."
            result = executor.substitute_arguments(content, "")

            assert result == "Do something with  please."

        def test_substitute_arguments_indexed(self, executor):
            """Test $0, $1, $2 substitution."""
            content = "First: $0, Second: $1, Third: $2"
            result = executor.substitute_arguments(content, "apple banana cherry")

            assert result == "First: apple, Second: banana, Third: cherry"

        def test_substitute_arguments_indexed_bracket_form(self, executor):
            """Test $ARGUMENTS[0], $ARGUMENTS[1] substitution."""
            content = "First: $ARGUMENTS[0], Second: $ARGUMENTS[1]"
            result = executor.substitute_arguments(content, "apple banana")

            assert result == "First: apple, Second: banana"

        def test_substitute_arguments_out_of_range(self, executor):
            """Test out-of-range indexed arguments return empty string."""
            content = "Has: $0, Missing: $1"
            result = executor.substitute_arguments(content, "only-one")

            assert result == "Has: only-one, Missing: "

        def test_substitute_arguments_quoted(self, executor):
            """Test arguments with quotes are handled correctly."""
            content = "Process: $0"
            result = executor.substitute_arguments(content, '"multi word arg"')

            assert result == "Process: multi word arg"

        def test_substitute_arguments_mixed(self, executor):
            """Test mixed argument styles."""
            content = "All: $ARGUMENTS, First: $0, Second: $ARGUMENTS[1]"
            result = executor.substitute_arguments(content, "one two three")

            assert result == "All: one two three, First: one, Second: two"

        def test_substitute_arguments_no_placeholders(self, executor):
            """Test content without placeholders is unchanged."""
            content = "No placeholders here."
            result = executor.substitute_arguments(content, "ignored args")

            assert result == "No placeholders here."

        def test_substitute_arguments_none_content(self, executor):
            """Test empty content returns empty string."""
            result = executor.substitute_arguments("", "args")
            assert result == ""

    class TestToolResolution:
        """Tests for allowed-tools resolution."""

        @pytest.fixture
        def executor(self):
            return SkillExecutor()

        def test_resolve_allowed_tools_simple(self, executor):
            """Test simple tool name resolution."""
            allowed = ["Read", "Grep", "Glob"]
            result = executor.resolve_allowed_tools(allowed)

            assert result == ["Read", "Grep", "Glob"]

        def test_resolve_allowed_tools_with_patterns(self, executor):
            """Test tool patterns like Bash(git *)."""
            allowed = ["Read", "Bash(git *)", "Bash(npm run *)"]
            result = executor.resolve_allowed_tools(allowed)

            assert "Read" in result
            assert "Bash(git *)" in result
            assert "Bash(npm run *)" in result

        def test_resolve_allowed_tools_empty(self, executor):
            """Test empty allowed tools returns empty list."""
            result = executor.resolve_allowed_tools(None)
            assert result == []

            result = executor.resolve_allowed_tools([])
            assert result == []

        def test_resolve_allowed_tools_filters_unavailable(self, executor):
            """Test that unavailable tools are filtered when available list provided."""
            allowed = ["Read", "Grep", "Write"]
            available = ["Read", "Grep"]
            result = executor.resolve_allowed_tools(allowed, available)

            assert "Read" in result
            assert "Grep" in result
            assert "Write" not in result

    class TestPatternMatching:
        """Tests for tool command pattern matching."""

        @pytest.fixture
        def executor(self):
            return SkillExecutor()

        def test_matches_simple_tool(self, executor):
            """Test simple tool name matching."""
            assert executor.matches_tool_pattern("Read", "", "Read") is True
            assert executor.matches_tool_pattern("Write", "", "Read") is False

        def test_matches_bash_git_pattern(self, executor):
            """Test Bash(git *) pattern."""
            pattern = "Bash(git *)"

            assert executor.matches_tool_pattern("Bash", "git status", pattern) is True
            assert executor.matches_tool_pattern("Bash", "git commit -m 'test'", pattern) is True
            assert executor.matches_tool_pattern("Bash", "npm install", pattern) is False
            assert executor.matches_tool_pattern("Read", "git status", pattern) is False

        def test_matches_npm_run_pattern(self, executor):
            """Test Bash(npm run *) pattern."""
            pattern = "Bash(npm run *)"

            assert executor.matches_tool_pattern("Bash", "npm run test", pattern) is True
            assert executor.matches_tool_pattern("Bash", "npm run build", pattern) is True
            assert executor.matches_tool_pattern("Bash", "npm install", pattern) is False

        def test_matches_exact_command(self, executor):
            """Test exact command matching."""
            pattern = "Bash(make build)"

            assert executor.matches_tool_pattern("Bash", "make build", pattern) is True
            assert executor.matches_tool_pattern("Bash", "make test", pattern) is False

    class TestFilterTools:
        """Tests for tool filtering."""

        @pytest.fixture
        def executor(self):
            return SkillExecutor()

        def test_filter_tools_no_restrictions(self, executor):
            """Test that all tools pass with no restrictions."""
            tools = [
                {"name": "Read"},
                {"name": "Write"},
                {"name": "Bash"},
            ]
            result = executor.filter_tools_for_skill(tools, [])

            assert len(result) == 3

        def test_filter_tools_with_restrictions(self, executor):
            """Test filtering tools based on allowed list."""
            tools = [
                {"name": "Read"},
                {"name": "Write"},
                {"name": "Bash"},
            ]
            allowed = ["Read", "Bash"]
            result = executor.filter_tools_for_skill(tools, allowed)

            names = [t["name"] for t in result]
            assert "Read" in names
            assert "Bash" in names
            assert "Write" not in names

        def test_filter_tools_with_patterns(self, executor):
            """Test that patterns still allow the base tool."""
            tools = [
                {"name": "Read"},
                {"name": "Bash"},
            ]
            allowed = ["Read", "Bash(git *)"]
            result = executor.filter_tools_for_skill(tools, allowed)

            names = [t["name"] for t in result]
            assert "Read" in names
            assert "Bash" in names


class TestSkillExecution:
    """Tests for skill execution."""

    @pytest.fixture
    def executor(self):
        return SkillExecutor()

    @pytest.mark.asyncio
    async def test_execute_inline(self, executor):
        """Test inline execution mode."""
        skill_data = {
            "name": "test-skill",
            "content": "Do something with $ARGUMENTS",
            "context": "inline",
            "allowed_tools": ["Read"],
            "model": None,
        }

        result = await executor.execute(skill_data, "my-args")

        assert result.skill_name == "test-skill"
        assert result.rendered_prompt == "Do something with my-args"
        assert result.execution_mode == "inline"
        assert "Read" in result.allowed_tools

    @pytest.mark.asyncio
    async def test_execute_fork(self, executor):
        """Test fork execution mode."""
        skill_data = {
            "name": "fork-skill",
            "content": "Forked task: $ARGUMENTS",
            "context": "fork",
            "allowed_tools": ["Read", "Grep"],
            "model": "gpt-4",
        }

        result = await executor.execute(skill_data, "task-args")

        assert result.skill_name == "fork-skill"
        assert result.execution_mode == "fork"
        assert result.model_override == "gpt-4"
        assert "Forked task: task-args" in result.rendered_prompt

    @pytest.mark.asyncio
    async def test_execute_with_model_override(self, executor):
        """Test that model override is preserved."""
        skill_data = {
            "name": "model-skill",
            "content": "Content",
            "context": "inline",
            "allowed_tools": None,
            "model": "claude-3-opus",
        }

        result = await executor.execute(skill_data, "")

        assert result.model_override == "claude-3-opus"


class TestSkillToolDefinition:
    """Tests for the Skill tool definition."""

    def test_skill_tool_definition_structure(self):
        """Test that SKILL_TOOL_DEFINITION has correct structure."""
        assert "type" in SKILL_TOOL_DEFINITION
        assert SKILL_TOOL_DEFINITION["type"] == "function"

        func = SKILL_TOOL_DEFINITION["function"]
        assert func["name"] == "Skill"
        assert "description" in func
        assert "parameters" in func

        params = func["parameters"]
        assert params["type"] == "object"
        assert "skill" in params["properties"]
        assert "args" in params["properties"]
        assert "skill" in params["required"]
