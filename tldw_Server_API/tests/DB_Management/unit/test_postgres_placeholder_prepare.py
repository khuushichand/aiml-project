import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.backends.query_utils import (
    convert_sqlite_placeholders_to_postgres,
    prepare_backend_statement,
    prepare_backend_many_statement,
)


def test_convert_placeholders_ignores_single_quoted_literals():
    sql = "SELECT '? literal ?' as txt, id FROM table WHERE id = ? AND note = '?keep?'"
    converted = convert_sqlite_placeholders_to_postgres(sql)
    # Only the WHERE id = ? should be converted
    assert "'? literal ?'" in converted
    assert "'?keep?'" in converted
    assert converted.count("%s") == 1


def test_convert_placeholders_ignores_double_quoted_identifiers_or_literals():
    sql = 'SELECT id, "weird?col" FROM "my?table" WHERE id = ?'
    converted = convert_sqlite_placeholders_to_postgres(sql)
    assert '"weird?col"' in converted
    assert '"my?table"' in converted
    assert converted.endswith("%s") or "%s" in converted


def test_prepare_backend_statement_positional_params():
    sql = "UPDATE users SET name = ? WHERE id = ?"
    params = ("Alice", 7)
    converted, prepared = prepare_backend_statement(BackendType.POSTGRESQL, sql, params)
    assert converted == "UPDATE users SET name = %s WHERE id = %s"
    assert prepared == params


def test_prepare_backend_many_statement_batch_params():
    sql = "INSERT INTO items (sku, qty) VALUES (?, ?)"
    params_list = [("A", 1), ("B", 2)]
    converted, prepared_list = prepare_backend_many_statement(
        BackendType.POSTGRESQL, sql, params_list
    )
    assert converted == "INSERT INTO items (sku, qty) VALUES (%s, %s)"
    assert prepared_list == params_list


@pytest.mark.skipif(
    pytest.importorskip(
        "tldw_Server_API.app.core.DB_Management.backends.postgresql_backend",
        reason="psycopg not available",
    ) is None,
    reason="psycopg not available",
)
def test_postgres_backend_prepare_query_no_replace_inside_literals():
    from tldw_Server_API.app.core.DB_Management.backends.postgresql_backend import (
        PostgreSQLBackend,
    )
    from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseConfig

    backend = PostgreSQLBackend(DatabaseConfig(backend_type=BackendType.POSTGRESQL))
    sql = "SELECT '? literal ?' as txt, id FROM table WHERE id = ? AND note = 'x?y'"
    converted, params = backend._prepare_query(sql, (42,))
    assert converted.count("%s") == 1
    assert "'? literal ?'" in converted and "'x?y'" in converted
    assert params == (42,)
