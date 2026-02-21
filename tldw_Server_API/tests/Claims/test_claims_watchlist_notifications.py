import json
import shutil
import tempfile

from tldw_Server_API.app.core.AuthNZ.permissions import CLAIMS_REVIEW
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.Claims_Extraction import claims_service
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


def test_watchlist_cluster_notifications():


    from tldw_Server_API.app.core.config import settings as app_settings

    base_dir = tempfile.mkdtemp(prefix="claims_watchlist_notify_")
    orig_user_db = app_settings.get("USER_DB_BASE_DIR")
    app_settings["USER_DB_BASE_DIR"] = base_dir

    db = None
    try:
        db_path = DatabasePaths.get_media_db_path(1)
        db = MediaDatabase(db_path=str(db_path), client_id="1")
        db.initialize_db()
        media_id, _, _ = db.add_media_with_keywords(
            title="Doc",
            media_type="text",
            content="A. B.",
            keywords=None,
        )
        db.upsert_claims(
            [
                {
                    "media_id": media_id,
                    "chunk_index": 0,
                    "span_start": None,
                    "span_end": None,
                    "claim_text": "A.",
                    "confidence": 0.8,
                    "extractor": "heuristic",
                    "extractor_version": "v1",
                    "chunk_hash": "hash",
                }
            ]
        )
        db.rebuild_claim_clusters_exact(user_id="1", min_size=1)
        clusters = db.list_claim_clusters("1", limit=10, offset=0)
        cluster_id = int(clusters[0]["id"])

        watch_db = WatchlistsDatabase.for_user(1)
        job = watch_db.create_job(
            name="Watchlist",
            description=None,
            scope_json="{}",
            schedule_expr=None,
            schedule_timezone="UTC",
            active=True,
            max_concurrency=None,
            per_host_delay_ms=None,
            retry_policy_json=None,
            output_prefs_json=None,
            job_filters_json=None,
        )
        watch_db.add_watchlist_cluster(int(job.id), cluster_id)

        class _User:
            def __init__(self) -> None:
                self.id = 1
                self.username = "reviewer"
                self.is_admin = False

        principal = AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="reviewer",
            token_type="access",
            jti=None,
            roles=["reviewer"],
            permissions=[CLAIMS_REVIEW],
            is_admin=False,
            org_ids=[],
            team_ids=[],
        )

        result = claims_service.evaluate_watchlist_cluster_notifications(
            user_id=None,
            principal=principal,
            current_user=_User(),
            db=db,
        )
        assert result.get("status") == "ok"
        notifications = db.list_claim_notifications(
            user_id="1",
            kind="watchlist_cluster_update",
            delivered=False,
        )
        assert notifications
        payload = json.loads(notifications[0]["payload_json"] or "{}")
        assert int(payload.get("cluster_id") or 0) == cluster_id
    finally:
        if db is not None:
            try:
                db.close_connection()
            except Exception:
                _ = None
        if orig_user_db is not None:
            app_settings["USER_DB_BASE_DIR"] = orig_user_db
        try:
            shutil.rmtree(base_dir, ignore_errors=True)
        except Exception:
            _ = None
