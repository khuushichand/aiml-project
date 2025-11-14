from tldw_Server_API.app.core.Writing.note_title import generate_note_title_heuristic, generate_note_title, TitleGenOptions


def test_generate_note_title_heuristic_truncation():
    content = "Title first line. More details on the next line.\nSecond line with more context."
    t = generate_note_title_heuristic(content, max_len=10)
    assert len(t) <= 10
    assert t  # not empty


def test_generate_note_title_entrypoint_fallback():
    # Ensure entrypoint returns something sane for empty content
    t = generate_note_title("", options=TitleGenOptions(max_len=30))
    assert t and len(t) <= 30

