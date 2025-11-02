import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseConfig, BackendType
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.DB_Management.backends.pg_rls_policies import ensure_prompt_studio_rls


pytestmark = pytest.mark.integration


def test_apply_rls_policies_smoke(pg_eval_params):
    # Build DatabaseConfig from shared params; skip if backend not available
    try:
        cfg = DatabaseConfig(
            backend=BackendType.POSTGRESQL,
            pg_host=pg_eval_params["host"],
            pg_port=int(pg_eval_params["port"]),
            pg_database=pg_eval_params["database"],
            pg_user=pg_eval_params["user"],
            pg_password=pg_eval_params.get("password"),
        )
        backend = DatabaseBackendFactory.create_backend(cfg)
    except Exception:
        pytest.skip("Postgres not configured or backend creation failed")
    applied = ensure_prompt_studio_rls(backend)
    assert applied in (True, False)
