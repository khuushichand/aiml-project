import re

from tldw_Server_API.app.core.DB_Management.backends.pg_rls_policies import build_prompt_studio_rls_sql


def test_build_rls_sql_contains_expected_policies():
    stmts = "\n".join(build_prompt_studio_rls_sql())
    # Ensure core tables are covered
    for table in [
        "prompt_studio_projects",
        "prompt_studio_prompts",
        "prompt_studio_signatures",
        "prompt_studio_test_cases",
        "prompt_studio_test_runs",
        "prompt_studio_evaluations",
        "prompt_studio_optimizations",
        "prompt_studio_optimization_iterations",
        "prompt_studio_job_queue",
        "prompt_studio_idempotency",
    ]:
        assert f"ALTER TABLE IF EXISTS {table} ENABLE ROW LEVEL SECURITY;" in stmts

    # Ensure projects policy references current_setting
    assert "CREATE POLICY ps_projects_tenant_isolation" in stmts
    assert "current_setting('app.current_user_id', true)" in stmts
