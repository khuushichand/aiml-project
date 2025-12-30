import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import get_user_media_db_path
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.services.claims_alerts_scheduler import run_claims_alerts_once


@pytest.mark.asyncio
async def test_claims_alerts_scheduler_scans_sqlite_users(tmp_path, monkeypatch):
    base_dir = tmp_path / "user_dbs"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    settings["USER_DB_BASE_DIR"] = str(base_dir)

    for user_id in (1, 2):
        db_path = get_user_media_db_path(user_id)
        db = MediaDatabase(db_path=db_path, client_id="test")
        db.initialize_db()
        db.close_connection()

    called: list[str] = []

    def _evaluator(*, target_user_id: str, window_sec: int, baseline_sec: int, db: MediaDatabase):
        called.append(str(target_user_id))
        return {"status": "ok"}

    processed = await run_claims_alerts_once(
        evaluator=_evaluator,
        window_sec=60,
        baseline_sec=120,
    )
    assert processed == 2
    assert set(called) == {"1", "2"}
