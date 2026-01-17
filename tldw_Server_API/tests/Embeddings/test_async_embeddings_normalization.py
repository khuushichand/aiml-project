import pytest

from tldw_Server_API.app.core.Embeddings.async_embeddings import _normalize_embedding_response


def test_normalize_embedding_response_vector():
    result = _normalize_embedding_response([1.0, 2.0, 3.0])
    assert result == [1.0, 2.0, 3.0]


def test_normalize_embedding_response_single_row():
    result = _normalize_embedding_response([[1.0, 2.0, 3.0]])
    assert result == [1.0, 2.0, 3.0]


def test_normalize_embedding_response_mean_pool():
    result = _normalize_embedding_response([[1.0, 3.0], [3.0, 5.0]])
    assert result == [2.0, 4.0]


def test_normalize_embedding_response_dict():
    result = _normalize_embedding_response({"embeddings": [1.0, 2.0]})
    assert result == [1.0, 2.0]


def test_normalize_embedding_response_rejects_error():
    with pytest.raises(ValueError):
        _normalize_embedding_response({"error": "invalid"})

