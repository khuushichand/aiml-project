from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.endpoints import quizzes as quizzes_endpoint
from tldw_Server_API.app.api.v1.schemas.quizzes import QuizGenerateRequest
from tldw_Server_API.app.services.quiz_generator import QuizProvenanceValidationError


@pytest.mark.asyncio
async def test_generate_quiz_legacy_media_id_maps_to_single_media_source(monkeypatch):
    captured: dict = {}

    async def fake_generate_quiz_from_sources(**kwargs):
        captured.update(kwargs)
        return {"quiz": {"id": 1}, "questions": []}

    monkeypatch.setattr(quizzes_endpoint, "generate_quiz_from_sources", fake_generate_quiz_from_sources)

    request = QuizGenerateRequest.model_validate({"media_id": 42, "num_questions": 5})
    await quizzes_endpoint.generate_quiz(request=request, db=Mock(), media_db=Mock())

    assert captured["sources"] == [{"source_type": "media", "source_id": "42"}]


@pytest.mark.asyncio
async def test_generate_quiz_forwards_sources_array(monkeypatch):
    captured: dict = {}

    async def fake_generate_quiz_from_sources(**kwargs):
        captured.update(kwargs)
        return {"quiz": {"id": 1}, "questions": []}

    monkeypatch.setattr(quizzes_endpoint, "generate_quiz_from_sources", fake_generate_quiz_from_sources)

    request = QuizGenerateRequest.model_validate(
        {
            "num_questions": 6,
            "sources": [{"source_type": "note", "source_id": "note-1"}],
        }
    )
    await quizzes_endpoint.generate_quiz(request=request, db=Mock(), media_db=Mock())

    assert captured["sources"] == [{"source_type": "note", "source_id": "note-1"}]


@pytest.mark.asyncio
async def test_generate_quiz_maps_provenance_validation_error_to_422(monkeypatch):
    async def fake_generate_quiz_from_sources(**kwargs):
        raise QuizProvenanceValidationError("invalid source citations")

    monkeypatch.setattr(quizzes_endpoint, "generate_quiz_from_sources", fake_generate_quiz_from_sources)

    request = QuizGenerateRequest.model_validate(
        {
            "num_questions": 6,
            "sources": [{"source_type": "note", "source_id": "note-1"}],
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        await quizzes_endpoint.generate_quiz(request=request, db=Mock(), media_db=Mock())

    assert exc_info.value.status_code == 422
