from pathlib import Path


def test_flashcards_guide_exists_and_is_indexed() -> None:
    guide = Path("Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md")
    assert guide.exists()  # nosec B101 - pytest assertion in test code

    index_text = Path("Docs/User_Guides/index.md").read_text()
    assert "WebUI_Extension/Flashcards_Study_Guide.md" in index_text  # nosec B101
    assert "Flashcards Study Guide" in index_text  # nosec B101
