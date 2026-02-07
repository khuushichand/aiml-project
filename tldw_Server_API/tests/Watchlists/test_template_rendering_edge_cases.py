"""Edge-case unit tests for watchlist output template rendering.

Covers: missing variables, empty items, XSS escaping, Unicode content,
very long summaries, JS-style operator normalization, and build_items_context.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from tldw_Server_API.app.services.outputs_service import (
    build_items_context_from_content_items,
    render_output_template,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. Missing variables — graceful fallback
# ---------------------------------------------------------------------------

def test_missing_variable_renders_empty():
    """SandboxedEnvironment renders undefined variables as empty string
    (Jinja2 default Undefined silently resolves to '')."""
    template = "Hello {{ undefined_var }}"
    result = render_output_template(template, {})
    # Undefined renders as empty string, not an error
    assert result == "Hello "


def test_partial_context_renders_available_and_blanks_missing():
    """Variables that ARE provided render; missing ones become empty strings."""
    template = "{{ title }} by {{ author }}"
    result = render_output_template(template, {"title": "Test"})
    assert result == "Test by "


# ---------------------------------------------------------------------------
# 2. Empty items list
# ---------------------------------------------------------------------------

def test_empty_items_list_renders():
    """A template iterating over an empty items list should render without crash."""
    template = "{% for item in items %}{{ item.title }}\n{% endfor %}Done"
    result = render_output_template(template, {"items": []})
    assert "Done" in result
    # No item titles since list is empty
    assert result.strip() == "Done"


def test_empty_items_with_conditional():
    """Template with conditional on empty items."""
    template = "{% if items %}Has items{% else %}No items{% endif %}"
    result = render_output_template(template, {"items": []})
    assert result == "No items"


# ---------------------------------------------------------------------------
# 3. XSS in item title — autoescape protects
# ---------------------------------------------------------------------------

def test_xss_script_tag_escaped():
    """SandboxedEnvironment with autoescape=True should escape HTML entities."""
    template = "Title: {{ title }}"
    result = render_output_template(template, {"title": "<script>alert(1)</script>"})
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_xss_in_loop_escaped():
    """Script tags in item list also escaped."""
    template = "{% for item in items %}{{ item.title }}{% endfor %}"
    items = [{"title": '<img src=x onerror="alert(1)">'}]
    result = render_output_template(template, {"items": items})
    assert "onerror" not in result or "&" in result
    assert "<img" not in result


def test_html_entities_escaped():
    """Angle brackets and ampersands are escaped."""
    template = "{{ content }}"
    result = render_output_template(template, {"content": "A < B & C > D"})
    assert "&lt;" in result
    assert "&amp;" in result
    assert "&gt;" in result


# ---------------------------------------------------------------------------
# 4. Unicode content
# ---------------------------------------------------------------------------

def test_unicode_japanese():
    """Japanese characters render correctly."""
    template = "Title: {{ title }}"
    result = render_output_template(template, {"title": "日本語のタイトル"})
    assert "日本語のタイトル" in result


def test_unicode_arabic():
    """Arabic characters render correctly."""
    template = "Title: {{ title }}"
    result = render_output_template(template, {"title": "عنوان عربي"})
    assert "عنوان عربي" in result


def test_unicode_emoji():
    """Emoji characters render correctly."""
    template = "Status: {{ status }}"
    result = render_output_template(template, {"status": "Complete ✅🎉"})
    assert "✅" in result
    assert "🎉" in result


def test_unicode_mixed_scripts():
    """Mixed CJK, Cyrillic, and Latin characters."""
    template = "{{ text }}"
    text = "Hello 世界 Мир"
    result = render_output_template(template, {"text": text})
    assert "世界" in result
    assert "Мир" in result


# ---------------------------------------------------------------------------
# 5. Very long summary
# ---------------------------------------------------------------------------

def test_very_long_summary_renders():
    """A 10K-character summary should render without OOM or crash."""
    long_summary = "A" * 10_000
    template = "Summary: {{ summary }}"
    result = render_output_template(template, {"summary": long_summary})
    assert len(result) >= 10_000
    assert result.startswith("Summary: ")


def test_very_long_items_list():
    """A template with 1000 items should render without crash."""
    items = [{"title": f"Item {i}", "url": f"https://example.com/{i}"} for i in range(1000)]
    template = "{% for item in items %}{{ item.title }}\n{% endfor %}"
    result = render_output_template(template, {"items": items})
    assert "Item 0" in result
    assert "Item 999" in result


# ---------------------------------------------------------------------------
# 6. JS-style operators — _normalize_template_syntax
# ---------------------------------------------------------------------------

def test_js_or_operator_normalized():
    """JS || operator is normalized to Jinja2 'or'."""
    template = "{{ title || 'Untitled' }}"
    result = render_output_template(template, {"title": ""})
    assert result == "Untitled"


def test_js_and_operator_normalized():
    """JS && operator is normalized to Jinja2 'and'."""
    template = "{% if items && show %}visible{% endif %}"
    result = render_output_template(template, {"items": [1], "show": True})
    assert result == "visible"


def test_js_operators_in_complex_expression():
    """Multiple JS operators in a single expression."""
    template = "{{ (a || 'x') }}-{{ (b || 'y') }}"
    result = render_output_template(template, {"a": "hello", "b": ""})
    assert result == "hello-y"


# ---------------------------------------------------------------------------
# 7. build_items_context_from_content_items
# ---------------------------------------------------------------------------

def test_build_context_basic():
    """Builds context from SimpleNamespace objects (mimicking DB rows)."""
    rows = [
        SimpleNamespace(
            id=1,
            media_id=100,
            title="Test Article",
            url="https://example.com/article",
            canonical_url="https://example.com/article",
            domain="example.com",
            summary="A test article",
            published_at="2025-01-01T00:00:00Z",
            created_at="2025-01-01T00:00:00Z",
            tags=["tech", "news"],
        ),
    ]
    items = build_items_context_from_content_items(rows)
    assert len(items) == 1
    item = items[0]
    assert item["id"] == 100  # media_id takes precedence
    assert item["content_item_id"] == 1
    assert item["title"] == "Test Article"
    assert item["url"] == "https://example.com/article"
    assert item["domain"] == "example.com"
    assert item["tags"] == ["tech", "news"]


def test_build_context_missing_fields():
    """Handles rows with missing optional fields."""
    rows = [SimpleNamespace(id=2)]
    items = build_items_context_from_content_items(rows)
    assert len(items) == 1
    item = items[0]
    assert item["id"] == 2  # Falls back to id since no media_id
    assert item["title"] == "Untitled"
    assert item["url"] == ""
    assert item["tags"] == []


def test_build_context_tags_non_list():
    """Non-list tags are converted to empty list."""
    rows = [SimpleNamespace(id=3, tags="not-a-list")]
    items = build_items_context_from_content_items(rows)
    assert items[0]["tags"] == []


def test_build_context_empty_iterable():
    """Empty iterable produces empty list."""
    items = build_items_context_from_content_items([])
    assert items == []


def test_build_context_url_fallback_to_url():
    """When canonical_url is None, falls back to url."""
    rows = [SimpleNamespace(id=4, canonical_url=None, url="https://fallback.com")]
    items = build_items_context_from_content_items(rows)
    assert items[0]["url"] == "https://fallback.com"


# ---------------------------------------------------------------------------
# 8. Template with markdown_link filter
# ---------------------------------------------------------------------------

def test_markdown_link_filter():
    """The custom markdown_link filter creates [text](url) links."""
    template = "{{ title|markdown_link(url) }}"
    result = render_output_template(template, {"title": "Click here", "url": "https://example.com"})
    # autoescape may escape parts, but the structure should be present
    assert "Click here" in result
    assert "example.com" in result


def test_markdown_link_filter_no_url():
    """markdown_link with empty url returns just the text."""
    template = "{{ title|markdown_link(url) }}"
    result = render_output_template(template, {"title": "No link", "url": ""})
    assert "No link" in result


# ---------------------------------------------------------------------------
# 9. Template syntax errors
# ---------------------------------------------------------------------------

def test_syntax_error_returns_original():
    """Jinja2 syntax error falls back to returning original template."""
    template = "{% for item in items %}"  # Missing endfor
    result = render_output_template(template, {"items": []})
    assert result == template


def test_unclosed_variable_returns_original():
    """Unclosed {{ returns original template."""
    template = "Hello {{ name"
    result = render_output_template(template, {"name": "World"})
    assert result == template
