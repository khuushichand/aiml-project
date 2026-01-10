import os
import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, QueryResult
from tldw_Server_API.app.core.DB_Management.backends.query_utils import prepare_backend_statement
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase


def test_prepare_backend_statement_insert_non_id_returning():
    """
    Verify Postgres insert on a table without 'id' uses RETURNING * when requested.
    This guards against failures where a generic helper appends RETURNING id.
    """
    sql = "INSERT INTO workflow_runs(run_id, tenant_id) VALUES (?, ?)"
    prepared_sql, prepared_params = prepare_backend_statement(
        BackendType.POSTGRESQL,
        sql,
        params=("run_123", "tenantA"),
        apply_default_transform=True,
        ensure_returning=True,
    )

    # Placeholders converted and RETURNING * appended
    assert prepared_sql.upper().startswith("INSERT INTO WORKFLOW_RUNS")
    assert "%s" in prepared_sql  # converted placeholders
    assert "RETURNING *" in prepared_sql.upper()
    # Params normalized to tuple
    assert isinstance(prepared_params, tuple)


def test_workflows_insert_returning_row_id_adapter():
    """
    Simulate an INSERT ... RETURNING * for workflows and ensure the helper can
    read back the 'id' from a QueryResult.
    """
    # Build a synthetic result row
    result = QueryResult(rows=[{"id": 42, "name": "wf"}], rowcount=1, description=[("id",), ("name",)])
    # WorkflowsDatabase._row_from_result is static and returns a row adapter
    row = WorkflowsDatabase._row_from_result(result)
    assert row is not None
    assert int(row["id"]) == 42


@pytest.mark.skipif(
    os.getenv("TLDW_CONTENT_DB_BACKEND", "").strip().lower() not in {"postgres", "postgresql"},
    reason="PostgreSQL content backend not configured in this environment",
)
def test_validate_postgres_content_backend_smoke():
    """
    Smoke test for RLS validation when a Postgres content backend is configured.
    This test is skipped unless TLDW_CONTENT_DB_BACKEND=postgres and a configured
    Postgres instance is available.
    """
    from tldw_Server_API.app.core.DB_Management.DB_Manager import validate_postgres_content_backend

    # Should not raise when backend and policies are provisioned correctly.
    validate_postgres_content_backend()
