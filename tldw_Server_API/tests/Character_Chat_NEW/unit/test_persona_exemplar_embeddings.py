"""Unit tests for persona exemplar embedding scorer."""

import pytest

from tldw_Server_API.app.core.Character_Chat.modules.persona_exemplar_embeddings import (
    build_character_exemplar_collection_name,
    delete_character_exemplar_embeddings,
    score_exemplars_with_embeddings,
    score_exemplars_with_vector_index,
    upsert_character_exemplar_embeddings,
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


@pytest.mark.unit
def test_score_exemplars_with_embeddings_uses_vector_scores_when_complete():
    candidates = [
        {"id": "e1", "text": "first"},
        {"id": "e2", "text": "second"},
    ]

    def _vector_scores(**kwargs):  # noqa: ARG001
        return {"e1": 0.95, "e2": 0.25}

    def _unexpected_embeddings(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("Embedding fallback should not execute when vector scores cover all candidates")

    scores = score_exemplars_with_embeddings(
        user_turn="query text",
        candidates=candidates,
        user_id="1",
        character_id=7,
        vector_score_fn=_vector_scores,
        create_embeddings_fn=_unexpected_embeddings,
        embedding_config={"embedding_config": {"default_model_id": "stub:model"}},
    )

    assert scores == {"e1": 0.95, "e2": 0.25}


@pytest.mark.unit
def test_score_exemplars_with_embeddings_merges_vector_and_embedding_scores():
    candidates = [
        {"id": "e1", "text": "first"},
        {"id": "e2", "text": "second"},
    ]

    def _vector_scores(**kwargs):  # noqa: ARG001
        return {"e1": 0.8}

    def _fake_embeddings_batch(texts, config, model_id_override):  # noqa: ARG001
        assert len(texts) == 3
        return [
            [1.0, 0.0],  # query
            [0.0, 1.0],  # e1 - ignored because vector score already present
            [1.0, 0.0],  # e2 -> normalized cosine 1.0
        ]

    scores = score_exemplars_with_embeddings(
        user_turn="query text",
        candidates=candidates,
        user_id="1",
        character_id=7,
        vector_score_fn=_vector_scores,
        create_embeddings_fn=_fake_embeddings_batch,
        embedding_config={"embedding_config": {"default_model_id": "stub:model"}},
    )

    assert scores["e1"] == 0.8
    assert scores["e2"] == 1.0


@pytest.mark.unit
def test_score_exemplars_with_vector_index_filters_to_candidates_and_normalizes_distance():
    class _FakeManager:
        def vector_search(self, **kwargs):  # noqa: ANN003
            assert kwargs["collection_name"] == build_character_exemplar_collection_name("user-1", 42)
            return [
                {"id": "e1", "distance": 0.2},
                {"id": "e3", "distance": 0.5},  # not in candidates; should be dropped
            ]

    scores = score_exemplars_with_vector_index(
        user_turn="query text",
        candidates=[{"id": "e1", "text": "first"}, {"id": "e2", "text": "second"}],
        user_id="user-1",
        character_id=42,
        chroma_manager=_FakeManager(),
        embedding_config={"embedding_config": {"default_model_id": "stub:model"}},
    )

    assert scores == {"e1": 0.9}


@pytest.mark.unit
def test_upsert_character_exemplar_embeddings_stores_vectors_in_collection():
    class _FakeManager:
        def __init__(self):
            self.calls: list[dict] = []

        def store_in_chroma(self, **kwargs):  # noqa: ANN003
            self.calls.append(kwargs)

    def _fake_embeddings_batch(texts, config, model_id_override):  # noqa: ARG001
        return [[0.1, 0.2] for _ in texts]

    manager = _FakeManager()
    count = upsert_character_exemplar_embeddings(
        user_id="1",
        character_id=10,
        exemplars=[
            {"id": "e1", "text": "first exemplar", "emotion": "neutral", "scenario": "press_challenge"},
            {"id": "e2", "text": "second exemplar", "emotion": "happy", "scenario": "fan_banter"},
        ],
        chroma_manager=manager,
        create_embeddings_fn=_fake_embeddings_batch,
        embedding_config={"embedding_config": {"default_model_id": "stub:model"}},
    )

    assert count == 2
    assert len(manager.calls) == 1
    call = manager.calls[0]
    assert call["collection_name"] == build_character_exemplar_collection_name("1", 10)
    assert call["ids"] == ["e1", "e2"]
    assert len(call["embeddings"]) == 2


@pytest.mark.unit
def test_delete_character_exemplar_embeddings_deletes_ids_from_collection():
    class _FakeManager:
        def __init__(self):
            self.calls: list[dict] = []

        def delete_from_collection(self, **kwargs):  # noqa: ANN003
            self.calls.append(kwargs)

    manager = _FakeManager()
    count = delete_character_exemplar_embeddings(
        user_id="1",
        character_id=10,
        exemplar_ids=["e1", "", "e2"],
        chroma_manager=manager,
        embedding_config={"embedding_config": {"default_model_id": "stub:model"}},
    )

    assert count == 2
    assert len(manager.calls) == 1
    call = manager.calls[0]
    assert call["collection_name"] == build_character_exemplar_collection_name("1", 10)
    assert call["ids"] == ["e1", "e2"]
