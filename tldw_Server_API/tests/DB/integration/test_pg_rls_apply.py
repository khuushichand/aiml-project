import os
import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseConfig, BackendType
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.DB_Management.backends.pg_rls_policies import ensure_prompt_studio_rls


pytestmark = pytest.mark.integration


def _pg_available() -> bool:
    try:
        cfg = DatabaseConfig.from_env()
        return cfg.backend == BackendType.POSTGRESQL
    except Exception:
        return False


@pytest.mark.skipif(not _pg_available(), reason="Postgres not configured via env")
def test_apply_rls_policies_smoke():
    cfg = DatabaseConfig.from_env()
    backend = DatabaseBackendFactory.create_backend(cfg)
    applied = ensure_prompt_studio_rls(backend)
    # idempotent: may return True even if policies exist; should not raise
    assert applied in (True, False)
