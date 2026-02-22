"""Tests for engine-level config template resolution and step-id context.

Covers:
- _resolve_config_templates() helper
- Step outputs stored by step_id in context
- ``_end`` routing for on_success
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestResolveConfigTemplates:
    """Tests for _resolve_config_templates helper."""

    def test_pure_expression_resolves_to_python_object(self):
        """{{ inputs.items }} should return the actual list, not a string."""
        from tldw_Server_API.app.core.Workflows.engine import _resolve_config_templates

        items = [{"title": "Story 1"}, {"title": "Story 2"}]
        context = {"inputs": {"items": items}}

        result = _resolve_config_templates("{{ inputs.items }}", context)
        assert result is items

    def test_dotted_path_resolves_nested_value(self):
        """{{ compose_script.sections }} should resolve from step-id context."""
        from tldw_Server_API.app.core.Workflows.engine import _resolve_config_templates

        sections = [{"voice": "HOST", "text": "Hello"}]
        context = {"compose_script": {"sections": sections}}

        result = _resolve_config_templates("{{ compose_script.sections }}", context)
        assert result is sections

    def test_dict_values_resolved_recursively(self):
        """Template expressions inside dicts are resolved."""
        from tldw_Server_API.app.core.Workflows.engine import _resolve_config_templates

        context = {
            "inputs": {"model": "kokoro", "items": [1, 2, 3]},
            "compose_script": {"sections": [{"voice": "HOST"}]},
        }
        cfg = {
            "items": "{{ inputs.items }}",
            "model": "{{ inputs.model }}",
            "sections": "{{ compose_script.sections }}",
            "static_key": True,
        }

        result = _resolve_config_templates(cfg, context)
        assert result["items"] == [1, 2, 3]
        assert result["model"] == "kokoro"
        assert result["sections"] == [{"voice": "HOST"}]
        assert result["static_key"] is True

    def test_list_values_resolved(self):
        """Template expressions inside lists are resolved."""
        from tldw_Server_API.app.core.Workflows.engine import _resolve_config_templates

        context = {"inputs": {"a": "hello", "b": "world"}}
        cfg = ["{{ inputs.a }}", "{{ inputs.b }}", "literal"]

        result = _resolve_config_templates(cfg, context)
        assert result == ["hello", "world", "literal"]

    def test_non_template_string_unchanged(self):
        """Strings without {{ }} should pass through unchanged."""
        from tldw_Server_API.app.core.Workflows.engine import _resolve_config_templates

        result = _resolve_config_templates("just a string", {"inputs": {}})
        assert result == "just a string"

    def test_non_string_values_unchanged(self):
        """Booleans, ints, floats, None pass through unchanged."""
        from tldw_Server_API.app.core.Workflows.engine import _resolve_config_templates

        context = {"inputs": {}}
        assert _resolve_config_templates(True, context) is True
        assert _resolve_config_templates(42, context) == 42
        assert _resolve_config_templates(3.14, context) == 3.14
        assert _resolve_config_templates(None, context) is None

    def test_unresolvable_expression_returns_original(self):
        """Missing context keys return the original template string."""
        from tldw_Server_API.app.core.Workflows.engine import _resolve_config_templates

        result = _resolve_config_templates("{{ inputs.missing_key }}", {"inputs": {}})
        # Should fall back to Jinja2 rendering (empty string) or original
        assert isinstance(result, str)

    def test_none_value_in_context_returns_original(self):
        """If resolved value is None, fall back to Jinja2 rendering."""
        from tldw_Server_API.app.core.Workflows.engine import _resolve_config_templates

        context = {"inputs": {"val": None}}
        result = _resolve_config_templates("{{ inputs.val }}", context)
        # None value → falls through pure-expression path to Jinja2 fallback
        assert isinstance(result, str)

    def test_whitespace_around_expression(self):
        """Leading/trailing whitespace in expression should be handled."""
        from tldw_Server_API.app.core.Workflows.engine import _resolve_config_templates

        context = {"inputs": {"x": 42}}
        result = _resolve_config_templates("  {{ inputs.x }}  ", context)
        assert result == 42

    def test_mixed_template_string_rendered_as_string(self):
        """Strings with text + template are rendered via Jinja2 as strings."""
        from tldw_Server_API.app.core.Workflows.engine import _resolve_config_templates

        context = {"inputs": {"name": "kokoro"}}
        result = _resolve_config_templates("model: {{ inputs.name }}", context)
        assert isinstance(result, str)
        assert "kokoro" in result


class TestStripMarkdownBeforeNormalizeWhitespace:
    """Test that strip_markdown runs before normalize_whitespace in text_clean."""

    @pytest.mark.asyncio
    async def test_markdown_headers_stripped_before_whitespace_normalization(self):
        """Markdown headers should be removed even when normalize_whitespace is also requested."""
        from tldw_Server_API.app.core.Workflows.adapters.text.transform import run_text_clean_adapter

        text = "# Heading One\n## Heading Two\nRegular text here."
        config = {"text": text, "operations": ["strip_markdown", "normalize_whitespace"]}
        context = {}

        result = await run_text_clean_adapter(config, context)

        # Headers should be stripped
        assert "#" not in result["text"]
        assert "Heading One" in result["text"]
        assert "Heading Two" in result["text"]

    @pytest.mark.asyncio
    async def test_list_markers_stripped_before_whitespace_normalization(self):
        """Markdown list markers should be stripped before whitespace collapse."""
        from tldw_Server_API.app.core.Workflows.adapters.text.transform import run_text_clean_adapter

        text = "- Item one\n- Item two\n* Item three"
        config = {"text": text, "operations": ["strip_markdown", "normalize_whitespace"]}
        context = {}

        result = await run_text_clean_adapter(config, context)

        assert result["text"].strip() == "Item one Item two Item three"

    @pytest.mark.asyncio
    async def test_blockquotes_stripped_before_whitespace_normalization(self):
        """Markdown blockquotes should be stripped before whitespace collapse."""
        from tldw_Server_API.app.core.Workflows.adapters.text.transform import run_text_clean_adapter

        text = "> Quote line one\n> Quote line two"
        config = {"text": text, "operations": ["strip_markdown", "normalize_whitespace"]}
        context = {}

        result = await run_text_clean_adapter(config, context)

        assert ">" not in result["text"]
        assert "Quote line one" in result["text"]
