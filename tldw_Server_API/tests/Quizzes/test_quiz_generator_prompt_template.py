import os

import pytest

os.environ.setdefault("TEST_MODE", "1")
pytestmark = pytest.mark.unit

from tldw_Server_API.app.services.quiz_generator import QUIZ_GENERATION_PROMPT


def test_quiz_generation_prompt_template_formats_with_literal_citation_object():
    rendered_prompt = QUIZ_GENERATION_PROMPT.format(
        num_questions=3,
        content="Sample content",
        difficulty="mixed",
        question_types="multiple_choice, true_false",
        focus_instruction="- Focus on these topics: testing",
        source_contract="- Allowed sources for source_citations.source_type/source_id: note:note-1",
    )

    assert '"label": "Optional citation label"' in rendered_prompt
    assert '"source_type": "media" | "note" | "flashcard_deck" | "flashcard_card"' in rendered_prompt
    assert "Allowed sources for source_citations.source_type/source_id: note:note-1" in rendered_prompt
    assert "{num_questions}" not in rendered_prompt
    assert "{content}" not in rendered_prompt
