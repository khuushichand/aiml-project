from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.postgresql_backend import PostgreSQLBackend


def command_after_cte(sql: str) -> str:
    return PostgreSQLBackend._command_after_cte(sql)


def test_cte_command_detects_materialized_with_column_list():
    sql = """
    WITH data(id, value) AS MATERIALIZED (
        SELECT 1 AS id, 'value' AS value
    )
    INSERT INTO target(id, value) VALUES (1, 'value')
    """
    assert command_after_cte(sql) == "INSERT"


def test_cte_command_detects_not_materialized_with_column_list():
    sql = """
    WITH data(id, value) AS NOT MATERIALIZED (
        SELECT 1 AS id, 'value' AS value
    )
    UPDATE target SET value = 'value' WHERE id = 1
    """
    assert command_after_cte(sql) == "UPDATE"


def test_cte_command_handles_multiple_ctes_with_materialized_markers():
    sql = """
    WITH
    cte_one(id) AS MATERIALIZED (SELECT 1),
    cte_two AS NOT MATERIALIZED (SELECT * FROM cte_one)
    DELETE FROM target WHERE id IN (SELECT id FROM cte_two)
    """
    assert command_after_cte(sql) == "DELETE"


def _make_backend() -> PostgreSQLBackend:
    return PostgreSQLBackend(DatabaseConfig(backend_type=BackendType.POSTGRESQL))


def test_is_write_command_detects_insert_inside_cte():
    backend = _make_backend()
    sql = "WITH inserted AS (INSERT INTO demo VALUES (1)) SELECT * FROM inserted"
    assert backend._is_write_command("SELECT", sql)


def test_is_write_command_detects_update_inside_cte():
    backend = _make_backend()
    sql = "WITH updated AS (UPDATE demo SET col = 1 RETURNING *) SELECT * FROM updated"
    assert backend._is_write_command("SELECT", sql)


def test_is_write_command_false_for_readonly_cte():
    backend = _make_backend()
    sql = "WITH data AS (SELECT 1) SELECT * FROM data"
    assert backend._is_write_command("SELECT", sql) is False
