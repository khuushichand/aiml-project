import json
import pytest

from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreConfig, VectorStoreType
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.pgvector_adapter import PGVectorAdapter


@pytest.mark.unit
def test_fast_path_plain_equality_jsonb_containment():
    cfg = VectorStoreConfig(
        store_type=VectorStoreType.PGVECTOR,
        connection_params={"dsn": "postgresql://u:p@localhost:5432/db"},
        embedding_dim=8,
        user_id="1",
    )
    adapter = PGVectorAdapter(cfg)

    filt = {"genre": "a", "kind": "chunk"}
    where_sql, params = adapter._build_where_from_filter(filt)

    assert "WHERE metadata @> %s" in where_sql
    assert len(params) == 1
    # Param is a JSON string containing our filter
    obj = json.loads(params[0])
    assert obj == filt


@pytest.mark.unit
def test_operator_disables_fast_path_and_builds_predicates_or_numeric():
    cfg = VectorStoreConfig(
        store_type=VectorStoreType.PGVECTOR,
        connection_params={"dsn": "postgresql://u:p@localhost:5432/db"},
        embedding_dim=8,
        user_id="1",
    )
    adapter = PGVectorAdapter(cfg)

    filt = {"$or": [{"tag": "b"}, {"num": {"$gte": 2}}]}
    where_sql, params = adapter._build_where_from_filter(filt)

    assert "metadata @>" not in where_sql
    assert " OR " in where_sql
    assert "(metadata->>%s) = %s" in where_sql
    assert "(metadata->>%s)::numeric >=" in where_sql
    # Param order follows the traversal order
    assert params == ["tag", "b", "num", 2.0]


@pytest.mark.unit
def test_in_operator_uses_any_and_empty_list_is_not_fastpathed():
    cfg = VectorStoreConfig(
        store_type=VectorStoreType.PGVECTOR,
        connection_params={"dsn": "postgresql://u:p@localhost:5432/db"},
        embedding_dim=8,
        user_id="1",
    )
    adapter = PGVectorAdapter(cfg)

    # Non-empty list → ANY(array)
    where_sql1, params1 = adapter._build_where_from_filter({"media_id": {"$in": ["1", "3"]}})
    assert " = ANY(" in where_sql1
    assert params1 == ["media_id", ["1", "3"]]

    # Empty list → falls back to equality with '[]' string (matches nothing)
    where_sql2, params2 = adapter._build_where_from_filter({"media_id": {"$in": []}})
    assert " = ANY(" not in where_sql2
    assert " IN " not in where_sql2
    assert params2 == ["media_id", "[]"]


@pytest.mark.unit
def test_nested_and_or_predicates_shape():
    cfg = VectorStoreConfig(
        store_type=VectorStoreType.PGVECTOR,
        connection_params={"dsn": "postgresql://u:p@localhost:5432/db"},
        embedding_dim=8,
        user_id="1",
    )
    adapter = PGVectorAdapter(cfg)

    filt = {"$and": [
        {"$or": [{"tag": "a"}, {"tag": "b"}]},
        {"num": {"$lt": 3}}
    ]}
    where_sql, params = adapter._build_where_from_filter(filt)

    # Expect nested ( ... OR ... ) AND (...)
    assert where_sql.count(" OR ") >= 1
    assert where_sql.count(" AND ") >= 1
    assert "(metadata->>%s) = %s" in where_sql
    assert "(metadata->>%s)::numeric <" in where_sql
    # Param order: tag, 'a', tag, 'b', num, 3.0
    assert params == ["tag", "a", "tag", "b", "num", 3.0]


@pytest.mark.unit
def test_not_equal_operator_compiles():
    cfg = VectorStoreConfig(
        store_type=VectorStoreType.PGVECTOR,
        connection_params={"dsn": "postgresql://u:p@localhost:5432/db"},
        embedding_dim=8,
        user_id="1",
    )
    adapter = PGVectorAdapter(cfg)

    where_sql, params = adapter._build_where_from_filter({"tag": {"$neq": "b"}})
    assert "<> %s" in where_sql
    assert params == ["tag", "b"]


@pytest.mark.unit
def test_numeric_compare_on_missing_key_generates_numeric_predicate():
    cfg = VectorStoreConfig(
        store_type=VectorStoreType.PGVECTOR,
        connection_params={"dsn": "postgresql://u:p@localhost:5432/db"},
        embedding_dim=8,
        user_id="1",
    )
    adapter = PGVectorAdapter(cfg)

    # Key might be missing at runtime; builder should still produce numeric predicate
    where_sql, params = adapter._build_where_from_filter({"score": {"$gte": 0.5}})
    assert "(metadata->>%s)::numeric >=" in where_sql
    assert params == ["score", 0.5]
