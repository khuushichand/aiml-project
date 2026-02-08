"""Unit tests for persona exemplar embedding scorer."""

import pytest

from tldw_Server_API.app.core.Character_Chat.modules.persona_exemplar_embeddings import (
    score_exemplars_with_embeddings,
)


@pytest.mark.unit
def test_score_exemplars_with_embeddings_normalizes_cosine_similarity():
    candidates = [
        {"id": "same", "text": "same direction"},
        {"id": "orthogonal", "text": "orthogonal direction"},
        {"id": "opposite", "text": "opposite direction"},
    ]

    def _fake_embeddings_batch(texts, config, model_id_override):  # noqa: ARG001
        assert len(texts) == 4
        return [
            [1.0, 0.0],   # query
            [1.0, 0.0],   # cosine 1.0 => normalized 1.0
            [0.0, 1.0],   # cosine 0.0 => normalized 0.5
            [-1.0, 0.0],  # cosine -1.0 => normalized 0.0
        ]

    scores = score_exemplars_with_embeddings(
        user_turn="query text",
        candidates=candidates,
        create_embeddings_fn=_fake_embeddings_batch,
        embedding_config={"embedding_config": {"default_model_id": "stub:model"}},
    )

    assert scores["same"] == 1.0
    assert scores["orthogonal"] == 0.5
    assert scores["opposite"] == 0.0


@pytest.mark.unit
def test_score_exemplars_with_embeddings_skips_invalid_candidate_records():
    candidates = [
        {"id": "", "text": "missing id"},
        {"id": "missing-text", "text": "   "},
        {"id": "valid", "text": "valid text"},
    ]

    def _fake_embeddings_batch(texts, config, model_id_override):  # noqa: ARG001
        assert len(texts) == 2
        return [[1.0, 0.0], [1.0, 0.0]]

    scores = score_exemplars_with_embeddings(
        user_turn="query text",
        candidates=candidates,
        create_embeddings_fn=_fake_embeddings_batch,
        embedding_config={"embedding_config": {"default_model_id": "stub:model"}},
    )

    assert scores == {"valid": 1.0}


@pytest.mark.unit
def test_score_exemplars_with_embeddings_returns_empty_on_embedding_error():
    def _raise_error(texts, config, model_id_override):  # noqa: ARG001
        raise RuntimeError("backend error")

    scores = score_exemplars_with_embeddings(
        user_turn="query text",
        candidates=[{"id": "e1", "text": "example"}],
        create_embeddings_fn=_raise_error,
        embedding_config={"embedding_config": {"default_model_id": "stub:model"}},
    )

    assert scores == {}
