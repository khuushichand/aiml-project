import pytest

from tldw_Server_API.app.core.Writing.note_title import generate_note_title_heuristic, TitleGenOptions, generate_note_title


def test_heuristic_basic_markdown_strip():
    content = """
    # My Big Document Title

    This is the first paragraph. It explains the topic in detail. More text follows.

    ```python
    print('hello')
    ```
    """.strip()

    title = generate_note_title_heuristic(content, max_len=250)
    assert title.startswith("My Big Document Title")
    assert len(title) <= 250


def test_heuristic_link_and_image_stripping():
    content = """
    [Awesome Guide](https://example.com) — an introduction
    ![logo](https://example.com/logo.png)
    Body text.
    """.strip()
    title = generate_note_title_heuristic(content, max_len=50)
    # Link should become just 'Awesome Guide'
    assert "Awesome Guide" in title
    assert "(" not in title
    assert ")" not in title
    assert len(title) <= 50


def test_generate_note_title_entrypoint_defaults():
    content = "   "
    # Empty content should fallback to timestamp title and be truncated
    t = generate_note_title(content, options=TitleGenOptions(max_len=20))
    assert t
    assert len(t) <= 20
