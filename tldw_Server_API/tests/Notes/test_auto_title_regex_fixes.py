import pytest

from tldw_Server_API.app.core.Writing.note_title import generate_note_title_heuristic


def test_sentence_split_on_period():


    content = "First sentence. Second part should be ignored on same line.\nMore body."
    title = generate_note_title_heuristic(content, max_len=250)
    assert title == "First sentence"


def test_sentence_split_on_exclamation_and_question():


    content_exclaim = "Wow! This continues on the same line."
    content_question = "Really? Additional details after the question."
    t1 = generate_note_title_heuristic(content_exclaim, max_len=250)
    t2 = generate_note_title_heuristic(content_question, max_len=250)
    # '!' and '?' are preserved by trailing punctuation strip
    assert t1 == "Wow!"
    assert t2 == "Really?"


def test_sentence_split_on_dashes():


    content_emdash = "Overview — details follow here."
    content_hyphen = "Overview - details follow here."
    t1 = generate_note_title_heuristic(content_emdash, max_len=250)
    t2 = generate_note_title_heuristic(content_hyphen, max_len=250)
    assert t1 == "Overview"
    assert t2 == "Overview"


def test_blockquote_stripping_single_and_nested():


    content_single = "> Quoted title should drop marker"
    content_nested = ">> Deeply quoted title"
    t1 = generate_note_title_heuristic(content_single, max_len=250)
    t2 = generate_note_title_heuristic(content_nested, max_len=250)
    assert t1 == "Quoted title should drop marker"
    assert t2 == "Deeply quoted title"


def test_ellipsis_stripping_unicode_and_three_dots():


    content_unicode = "My title…"
    content_three = "My title..."
    t1 = generate_note_title_heuristic(content_unicode, max_len=250)
    t2 = generate_note_title_heuristic(content_three, max_len=250)
    assert t1 == "My title"
    assert t2 == "My title"
