from pathlib import Path

from tldw_Server_API.app.core.DB_Management.Workflows_Scheduler_DB import WorkflowsSchedulerDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


def _close_scheduler_backend(db: WorkflowsSchedulerDB) -> None:
    try:
        pool = db.backend.get_pool()
        pool.close_all()
    except Exception:
        _ = None


def test_scheduler_uses_dedicated_default_sqlite_path_when_global_database_url_is_set(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_databases"))
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./Databases/users.db")
    monkeypatch.delenv("WORKFLOWS_SCHEDULER_DATABASE_URL", raising=False)
    monkeypatch.delenv("WORKFLOWS_SCHEDULER_SQLITE_PATH", raising=False)

    db = WorkflowsSchedulerDB(user_id=1)
    try:
        actual = Path(db.backend.config.sqlite_path).resolve()  # type: ignore[arg-type]
        expected = DatabasePaths.get_workflows_scheduler_db_path(1).resolve()
        assert actual == expected
    finally:
        _close_scheduler_backend(db)

