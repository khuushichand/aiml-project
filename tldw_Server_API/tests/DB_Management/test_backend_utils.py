from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.backends.query_utils import (
    convert_sqlite_placeholders_to_postgres,
    normalise_params,
    prepare_backend_many_statement,
    prepare_backend_statement,
    transform_sqlite_query_for_postgres,
)


def test_normalise_params_handles_sequences_and_scalars():
    assert normalise_params(None) is None
    assert normalise_params((1, 2)) == (1, 2)
    assert normalise_params([1, 2]) == (1, 2)
    assert normalise_params({'a': 1}) == {'a': 1}
    assert normalise_params(5) == (5,)


def test_convert_sqlite_placeholders_to_postgres_preserves_literals():
    query = "SELECT '?' as literal, col FROM table WHERE id = ?"
    converted = convert_sqlite_placeholders_to_postgres(query)
    assert converted == "SELECT '?' as literal, col FROM table WHERE id = %s"


def test_transform_sqlite_query_for_postgres_rewrites_conflicts_and_collation():
    source = "INSERT OR IGNORE INTO demo(name) VALUES (?) COLLATE NOCASE"
    transformed = transform_sqlite_query_for_postgres(source)
    assert 'INSERT OR IGNORE' not in transformed.upper()
    assert 'COLLATE' not in transformed.upper()
    assert 'ON CONFLICT DO NOTHING' in transformed.upper()


def test_prepare_backend_statement_noop_for_sqlite():
    query, params = prepare_backend_statement(BackendType.SQLITE, "SELECT 1", (1,))
    assert query == "SELECT 1"
    assert params == (1,)


def test_prepare_backend_statement_applies_placeholder_conversion_and_transform():
    query, params = prepare_backend_statement(
        BackendType.POSTGRESQL,
        "INSERT OR IGNORE INTO demo VALUES (?)",
        ["value"],
        apply_default_transform=True,
        ensure_returning=True,
    )
    assert query == "INSERT INTO demo VALUES (%s) ON CONFLICT DO NOTHING RETURNING id"
    assert params == ("value",)


def test_prepare_backend_many_statement_handles_lists():
    query, params = prepare_backend_many_statement(
        BackendType.POSTGRESQL,
        "UPDATE demo SET name = ? WHERE id = ?",
        [["alice", 1], ["bob", 2]],
    )
    assert query == "UPDATE demo SET name = %s WHERE id = %s"
    assert params == [("alice", 1), ("bob", 2)]


def test_transform_sqlite_query_for_postgres_rewrites_randomblob_and_json_extract():
    source = (
        "INSERT INTO prompt_studio_job_queue (uuid, payload) "
        "VALUES (lower(hex(randomblob(16))), json_extract(scores, '$.quality'))"
    )
    transformed = transform_sqlite_query_for_postgres(source, ensure_returning=True)
    assert "gen_random_bytes" in transformed
    assert "->> 'quality'" in transformed
    assert "RETURNING id" in transformed


def test_transform_sqlite_query_for_postgres_converts_boolean_columns():
    source = "SELECT * FROM table WHERE deleted = 0 AND is_active = 1 AND priority = 0"
    transformed = transform_sqlite_query_for_postgres(source)
    assert "deleted = FALSE" in transformed
    assert "is_active = TRUE" in transformed
    # Non-boolean column should remain unchanged
    assert "priority = 0" in transformed
