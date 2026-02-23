import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import (
    normalize_pdf_text_for_storage,
)


pytestmark = pytest.mark.unit


def test_reflows_soft_wrapped_paragraph_lines():
    src = (
        "We are not just interested in models that perform well on a\n"
        "single physical task, but rather models that robustly generalize.\n\n"
        "Therefore, we test generalization."
    )
    out = normalize_pdf_text_for_storage(src)
    assert "perform well on a single physical task" in out
    assert "\n\nTherefore, we test generalization." in out


def test_preserves_structural_blocks():
    src = (
        "## Page 1\n\n"
        "# Heading\n"
        "- list item one\n"
        "- list item two\n\n"
        "| a | b |\n"
        "|---|---|\n"
        "| 1 | 2 |\n\n"
        "Paragraph line one\n"
        "line two\n\n"
        "---\n"
    )
    out = normalize_pdf_text_for_storage(src)
    assert "# Heading" in out
    assert "- list item one" in out
    assert "| a | b |" in out
    assert "Paragraph line one line two" in out
    assert "## Page 1" in out
    assert "\n---\n" in f"\n{out}\n"


def test_repairs_hyphenated_soft_wraps():
    src = "generaliza-\ntion improves.\n\nnon-\nLinear stays separated."
    out = normalize_pdf_text_for_storage(src)
    assert "generalization improves." in out
    assert "non- Linear stays separated." in out


def test_idempotent_normalization():
    src = "Line one\nline two\n\n# Keep heading\n"
    first = normalize_pdf_text_for_storage(src)
    second = normalize_pdf_text_for_storage(first)
    assert first == second


def test_preserves_fenced_code_blocks():
    src = (
        "```python\n"
        "foo = 1\n"
        "bar = 2\n"
        "```\n\n"
        "Paragraph line one\n"
        "line two"
    )
    out = normalize_pdf_text_for_storage(src)
    assert "```python\nfoo = 1\nbar = 2\n```" in out
    assert "Paragraph line one line two" in out


def test_preserves_blockquote_lines():
    src = (
        "> quoted line one\n"
        "> quoted line two\n\n"
        "Paragraph starts\n"
        "and continues."
    )
    out = normalize_pdf_text_for_storage(src)
    assert "> quoted line one" in out
    assert "> quoted line two" in out
    assert "Paragraph starts and continues." in out


def test_reflows_with_crlf_input():
    src = "Alpha line one\r\nline two\r\n\r\nBeta line one\r\nline two"
    out = normalize_pdf_text_for_storage(src)
    assert out == "Alpha line one line two\n\nBeta line one line two"


def test_preserves_indented_code_style_blocks():
    src = (
        "    def foo():\n"
        "        return 1\n\n"
        "Paragraph starts\n"
        "and continues"
    )
    out = normalize_pdf_text_for_storage(src)
    assert "    def foo():" in out
    assert "        return 1" in out
    assert "Paragraph starts and continues" in out


def test_preserves_ordered_list_blocks():
    src = (
        "1. first item\n"
        "2. second item\n\n"
        "Paragraph starts\n"
        "and continues."
    )
    out = normalize_pdf_text_for_storage(src)
    assert "1. first item" in out
    assert "2. second item" in out
    assert "Paragraph starts and continues." in out


def test_single_pipe_text_still_reflows():
    src = "A | B relation starts here\nand continues there."
    out = normalize_pdf_text_for_storage(src)
    assert out == "A | B relation starts here and continues there."
