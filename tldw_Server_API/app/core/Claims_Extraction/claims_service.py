from __future__ import annotations

import csv
import io
import json
import math
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.permissions import (
    CLAIMS_ADMIN,
    CLAIMS_REVIEW,
    SYSTEM_CONFIGURE,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo
from tldw_Server_API.app.core.Claims_Extraction.claims_rebuild_service import get_claims_rebuild_service
from tldw_Server_API.app.core.Claims_Extraction.monitoring import record_claims_review_metrics
from tldw_Server_API.app.core.Claims_Extraction.claims_clustering import rebuild_claim_clusters_embeddings
from tldw_Server_API.app.core.Claims_Extraction.claims_embeddings import claim_embedding_id
from tldw_Server_API.app.core.Claims_Extraction.claims_notifications import (
    record_watchlist_cluster_notifications,
)
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.db_path_utils import get_user_media_db_path
from tldw_Server_API.app.core.Setup import setup_manager
from tldw_Server_API.app.core.config import settings


_ROLE_HIERARCHY = {
    "owner": 4,
    "admin": 3,
    "lead": 2,
    "member": 1,
}
_ACTIVE_MEMBERSHIP_STATUSES = {"active"}
_REVIEW_TRANSITIONS = {
    "pending": {"approved", "flagged", "rejected", "reassigned"},
    "reassigned": {"pending", "approved", "flagged", "rejected"},
    "flagged": {"pending", "approved", "rejected"},
    "rejected": {"pending"},
    "approved": {"pending"},
}


def _role_at_least(user_role: str, required_role: str) -> bool:
    user_level = _ROLE_HIERARCHY.get(str(user_role).lower(), 0)
    required_level = _ROLE_HIERARCHY.get(str(required_role).lower(), 0)
    return user_level >= required_level


def _is_membership_active(membership: Optional[dict]) -> bool:
    if not membership:
        return False
    status_val = membership.get("status")
    if status_val is None:
        return False
    return str(status_val).strip().lower() in _ACTIVE_MEMBERSHIP_STATUSES


def _is_review_transition_allowed(current_status: str, new_status: str) -> bool:
    """Return True when a review status transition is allowed."""
    return new_status in _REVIEW_TRANSITIONS.get(current_status, {new_status})


def _normalize_claim_row(row: Dict[str, Any]) -> Dict[str, Any]:
    row.pop("media_owner_user_id", None)
    row.pop("media_client_id", None)
    return row


def _parse_email_recipients(raw_value: Optional[str]) -> List[str]:
    if raw_value is None:
        return []
    text = str(raw_value).strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
        if isinstance(payload, list):
            return [str(v).strip() for v in payload if str(v).strip()]
    except Exception:
        pass
    return [item.strip() for item in text.split(",") if item.strip()]


def _normalize_alert_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    normalized["email_recipients"] = _parse_email_recipients(row.get("email_recipients"))
    return normalized


def _normalize_review_rule(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    raw = normalized.get("predicate_json")
    try:
        normalized["predicate_json"] = json.loads(raw) if raw else {}
    except Exception:
        normalized["predicate_json"] = {}
    return normalized


def _normalize_notification_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    raw = normalized.get("payload_json")
    try:
        normalized["payload"] = json.loads(raw) if raw else {}
    except Exception:
        normalized["payload"] = {}
    normalized.pop("payload_json", None)
    return normalized


def _get_watchlists_db(user_id: str) -> Optional[WatchlistsDatabase]:
    try:
        return WatchlistsDatabase.for_user(user_id=int(user_id))
    except Exception:
        return None


def _load_watchlist_cluster_counts(user_id: str, cluster_ids: Optional[List[int]] = None) -> Dict[int, int]:
    watch_db = _get_watchlists_db(user_id)
    if not watch_db:
        return {}
    try:
        return watch_db.list_watchlist_cluster_counts(cluster_ids=cluster_ids)
    except Exception:
        return {}


def _extract_request_metadata(request: Any) -> tuple[Optional[str], Optional[str]]:
    """Extract IP and user-agent for audit logging."""
    action_ip = None
    action_user_agent = None
    if request is None:
        return action_ip, action_user_agent
    try:
        if request.client:
            action_ip = request.client.host
    except Exception:
        action_ip = None
    try:
        action_user_agent = request.headers.get("user-agent")
    except Exception:
        action_user_agent = None
    return action_ip, action_user_agent


def _enqueue_claim_rebuild_if_needed(*, media_id: int, db_path: str) -> None:
    """Best-effort enqueue of a claims rebuild task for a media item."""
    try:
        svc = get_claims_rebuild_service()
        svc.submit(media_id=int(media_id), db_path=str(db_path))
    except Exception:
        pass


def _format_ratio(value: Optional[float]) -> str:
    """Return a human-friendly ratio string for alert messages."""
    if value is None:
        return "n/a"
    try:
        return f"{float(value) * 100:.2f}%"
    except Exception:
        return "n/a"


def _send_claims_alert_webhook(url: str, payload: Dict[str, Any]) -> None:
    """Send a claims alert payload to a webhook endpoint."""
    try:
        from tldw_Server_API.app.core.http_client import create_client, fetch
    except Exception:
        return
    try:
        with create_client(timeout=5.0) as client:
            fetch(
                method="POST",
                url=url,
                client=client,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=5.0,
            )
    except Exception:
        return


def _dispatch_claims_alert_notifications(config_row: Dict[str, Any], payload: Dict[str, Any]) -> None:
    """Dispatch best-effort notifications for a claims alert."""
    slack_url = config_row.get("slack_webhook_url")
    webhook_url = config_row.get("webhook_url")
    if slack_url:
        slack_payload = {
            "text": (
                "Claims alert: unsupported ratio "
                f"{_format_ratio(payload.get('window_ratio'))} "
                f"(threshold {_format_ratio(payload.get('threshold'))}, "
                f"baseline {_format_ratio(payload.get('baseline_ratio'))})"
            )
        }
        threading.Thread(
            target=_send_claims_alert_webhook,
            args=(str(slack_url), slack_payload),
            daemon=True,
        ).start()
    if webhook_url:
        threading.Thread(
            target=_send_claims_alert_webhook,
            args=(str(webhook_url), payload),
            daemon=True,
        ).start()


def _refresh_claim_embedding(
    *,
    claim_id: int,
    media_id: int,
    chunk_index: int,
    old_text: str,
    new_text: str,
    user_id: str,
) -> None:
    """Best-effort re-embed updated claim text into the claims collection."""
    if not bool(settings.get("CLAIMS_EMBED", False)):
        return
    if not new_text or new_text == old_text:
        return
    try:
        from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import (
            ChromaDBManager,
            create_embeddings_batch,
        )
    except Exception:
        return
    embedding_config = dict(settings.get("EMBEDDING_CONFIG") or {})
    embedding_config["USER_DB_BASE_DIR"] = settings.get("USER_DB_BASE_DIR")
    if not embedding_config.get("USER_DB_BASE_DIR"):
        return
    try:
        manager = ChromaDBManager(user_id=str(user_id), user_embedding_config=embedding_config)
    except Exception:
        return
    collection_name = f"claims_for_{user_id}"
    try:
        collection = manager.get_or_create_collection(collection_name)
    except Exception:
        return

    old_id = claim_embedding_id(media_id, chunk_index, old_text)
    new_id = claim_embedding_id(media_id, chunk_index, new_text)
    try:
        collection.delete(ids=[old_id])
    except Exception:
        try:
            collection.delete(where={"media_id": str(media_id), "claim_text": str(old_text)})
        except Exception:
            pass

    model_id = (
        settings.get("CLAIMS_EMBED_MODEL_ID")
        or embedding_config.get("default_model_id")
        or embedding_config.get("embedding_model")
    )
    try:
        embeddings = create_embeddings_batch(
            texts=[new_text],
            user_app_config=embedding_config,
            model_id_override=model_id,
        )
    except Exception:
        return

    metadata = {
        "source": "claim",
        "media_id": str(media_id),
        "chunk_index": int(chunk_index),
        "claim_text": str(new_text),
        "claim_id": str(claim_id),
    }
    try:
        collection.upsert(
            documents=[new_text],
            embeddings=embeddings,
            ids=[new_id],
            metadatas=[metadata],
        )
    except Exception:
        return


def _claims_settings_snapshot() -> Dict[str, Any]:
    return {
        "enable_ingestion_claims": bool(settings.get("ENABLE_INGESTION_CLAIMS", False)),
        "claim_extractor_mode": str(settings.get("CLAIM_EXTRACTOR_MODE", "heuristic")),
        "claims_max_per_chunk": int(settings.get("CLAIMS_MAX_PER_CHUNK", 3)),
        "claims_embed": bool(settings.get("CLAIMS_EMBED", False)),
        "claims_embed_model_id": str(settings.get("CLAIMS_EMBED_MODEL_ID", "")),
        "claims_cluster_method": str(settings.get("CLAIMS_CLUSTER_METHOD", "embeddings")),
        "claims_cluster_similarity_threshold": float(settings.get("CLAIMS_CLUSTER_SIMILARITY_THRESHOLD", 0.85)),
        "claims_cluster_batch_size": int(settings.get("CLAIMS_CLUSTER_BATCH_SIZE", 200)),
        "claims_llm_provider": str(settings.get("CLAIMS_LLM_PROVIDER", "")),
        "claims_llm_temperature": float(settings.get("CLAIMS_LLM_TEMPERATURE", 0.1)),
        "claims_llm_model": str(settings.get("CLAIMS_LLM_MODEL", "")),
        "claims_rebuild_enabled": bool(settings.get("CLAIMS_REBUILD_ENABLED", False)),
        "claims_rebuild_interval_sec": int(settings.get("CLAIMS_REBUILD_INTERVAL_SEC", 3600)),
        "claims_rebuild_policy": str(settings.get("CLAIMS_REBUILD_POLICY", "missing")),
        "claims_stale_days": int(settings.get("CLAIMS_STALE_DAYS", 7)),
    }


def _claims_monitoring_settings_snapshot() -> Dict[str, Any]:
    return {
        "claims_monitoring_enabled": bool(settings.get("CLAIMS_MONITORING_ENABLED", False)),
        "claims_alert_threshold_default": float(settings.get("CLAIMS_ALERT_THRESHOLD_DEFAULT", 0.2)),
        "claims_rebuild_max_queue_alert": int(settings.get("CLAIMS_REBUILD_MAX_QUEUE_ALERT", 1000)),
        "claims_rebuild_heartbeat_warn_sec": int(settings.get("CLAIMS_REBUILD_HEARTBEAT_WARN_SEC", 600)),
        "claims_provider_cost_multipliers": dict(settings.get("CLAIMS_PROVIDER_COST_MULTIPLIERS") or {}),
    }


async def _ensure_claim_edit_access(
    *,
    principal: AuthPrincipal,
    claim_row: Dict[str, Any],
) -> None:
    if principal.is_admin:
        return

    visibility = str(claim_row.get("media_visibility") or "personal").lower()
    owner_user_id = claim_row.get("media_owner_user_id")
    media_client_id = claim_row.get("media_client_id")
    if visibility == "personal":
        try:
            if owner_user_id is not None and int(owner_user_id) == int(principal.user_id):
                return
        except Exception:
            pass
        if media_client_id is not None and str(media_client_id) == str(principal.user_id):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")

    org_id = claim_row.get("media_org_id")
    team_id = claim_row.get("media_team_id")
    db_pool = await get_db_pool()
    repo = AuthnzOrgsTeamsRepo(db_pool=db_pool)

    if visibility == "org":
        if org_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")
        membership = await repo.get_org_member(int(org_id), int(principal.user_id))
        if not _is_membership_active(membership):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")
        role = str(membership.get("role", "member"))
        if _role_at_least(role, "admin"):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")

    if visibility == "team":
        if team_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")
        org_membership = None
        if org_id is not None:
            org_membership = await repo.get_org_member(int(org_id), int(principal.user_id))
        if _is_membership_active(org_membership):
            org_role = str(org_membership.get("role", "member"))
            if _role_at_least(org_role, "admin"):
                return
        team_membership = await repo.get_team_member(int(team_id), int(principal.user_id))
        if _is_membership_active(team_membership):
            team_role = str(team_membership.get("role", "member"))
            if _role_at_least(team_role, "lead"):
                return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")


def _can_review_claim(principal: AuthPrincipal, claim_row: Dict[str, Any]) -> bool:
    if principal.is_admin:
        return True
    reviewer_id = claim_row.get("reviewer_id")
    review_group = claim_row.get("review_group")
    if reviewer_id is not None:
        try:
            if int(reviewer_id) == int(principal.user_id):
                return True
        except Exception:
            pass
    if review_group:
        try:
            return str(review_group) in [str(r) for r in (principal.roles or [])]
        except Exception:
            return False
    return False


def _ensure_claims_admin(principal: AuthPrincipal) -> None:
    if principal.is_admin or CLAIMS_ADMIN in (principal.permissions or []):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


def _ensure_claims_review(principal: AuthPrincipal) -> None:
    if principal.is_admin:
        return
    perms = set(principal.permissions or [])
    if CLAIMS_ADMIN in perms or CLAIMS_REVIEW in perms:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


def _filter_notifications_for_principal(
    principal: AuthPrincipal,
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if principal.is_admin:
        return rows
    allowed_roles = {str(r) for r in (principal.roles or [])}
    allowed_user = str(principal.user_id) if principal.user_id is not None else ""
    filtered: List[Dict[str, Any]] = []
    for row in rows:
        target_user_id = row.get("target_user_id")
        target_group = row.get("target_review_group")
        if target_user_id and str(target_user_id) == allowed_user:
            filtered.append(row)
            continue
        if target_group and str(target_group) in allowed_roles:
            filtered.append(row)
            continue
    return filtered


def _percentile_value(values: List[int], percentile: float) -> Optional[int]:
    if not values:
        return None
    ordered = sorted(values)
    idx = int(math.ceil(percentile * len(ordered))) - 1
    idx = max(0, min(idx, len(ordered) - 1))
    return int(ordered[idx])


def _build_review_latency_stats(db: MediaDatabase) -> Dict[str, Optional[float]]:
    avg_latency_sec = None
    if db.backend_type == BackendType.POSTGRESQL:
        avg_row = db.execute_query(
            "SELECT AVG(EXTRACT(EPOCH FROM (reviewed_at - created_at))) AS avg_sec "
            "FROM claims WHERE reviewed_at IS NOT NULL AND deleted = 0"
        ).fetchone()
    else:
        avg_row = db.execute_query(
            "SELECT AVG((julianday(reviewed_at) - julianday(created_at)) * 86400.0) AS avg_sec "
            "FROM Claims WHERE reviewed_at IS NOT NULL AND deleted = 0"
        ).fetchone()
    if avg_row:
        try:
            avg_latency_sec = float(avg_row[0]) if avg_row[0] is not None else None
        except Exception:
            avg_latency_sec = None

    total_rows = db.execute_query(
        "SELECT COUNT(*) AS count FROM Claims WHERE reviewed_at IS NOT NULL AND deleted = 0"
    ).fetchone()
    total = int(total_rows[0]) if total_rows and total_rows[0] is not None else 0
    p95_latency = None
    if total > 0:
        offset = max(0, int(math.ceil(total * 0.95)) - 1)
        if db.backend_type == BackendType.POSTGRESQL:
            latency_expr = "EXTRACT(EPOCH FROM (reviewed_at - created_at))"
            sql = (
                "SELECT "
                + latency_expr
                + " AS latency FROM claims "
                "WHERE reviewed_at IS NOT NULL AND deleted = 0 "
                f"ORDER BY {latency_expr} LIMIT 1 OFFSET %s"
            )
            row = db.execute_query(sql, (offset,)).fetchone()
        else:
            latency_expr = "(julianday(reviewed_at) - julianday(created_at)) * 86400.0"
            sql = (
                "SELECT "
                + latency_expr
                + " AS latency FROM Claims "
                "WHERE reviewed_at IS NOT NULL AND deleted = 0 "
                f"ORDER BY {latency_expr} LIMIT 1 OFFSET ?"
            )
            row = db.execute_query(sql, (offset,)).fetchone()
        if row:
            try:
                p95_latency = float(row[0]) if row[0] is not None else None
            except Exception:
                p95_latency = None
    return {
        "avg_review_latency_sec": avg_latency_sec,
        "p95_review_latency_sec": p95_latency,
    }


def _build_review_throughput(db: MediaDatabase, window_days: int) -> Dict[str, Any]:
    window_days = max(1, int(window_days))
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=window_days - 1)
    since_dt = datetime.combine(start_date, datetime.min.time())
    if db.backend_type == BackendType.POSTGRESQL:
        sql = (
            "SELECT DATE(created_at) AS day, COUNT(*) AS count "
            "FROM claims_review_log WHERE created_at >= %s "
            "GROUP BY day ORDER BY day"
        )
        rows = db.execute_query(sql, (since_dt,)).fetchall()
    else:
        sql = (
            "SELECT DATE(created_at) AS day, COUNT(*) AS count "
            "FROM claims_review_log WHERE created_at >= ? "
            "GROUP BY day ORDER BY day"
        )
        rows = db.execute_query(sql, (since_dt.strftime("%Y-%m-%d %H:%M:%S"),)).fetchall()

    counts_by_day: Dict[str, int] = {}
    for row in rows:
        day_val = row[0]
        if day_val is None:
            continue
        day_str = str(day_val)
        counts_by_day[day_str] = int(row[1]) if row[1] is not None else 0

    series: List[Dict[str, Any]] = []
    total = 0
    for i in range(window_days):
        day = start_date + timedelta(days=i)
        day_str = day.isoformat()
        count = int(counts_by_day.get(day_str, 0))
        total += count
        series.append({"date": day_str, "count": count})
    return {"window_days": window_days, "total": total, "daily": series}


def _build_claims_per_media_stats(db: MediaDatabase) -> Tuple[List[Dict[str, int]], Dict[str, Optional[float]]]:
    media_rows = db.execute_query(
        "SELECT media_id, COUNT(*) AS count FROM Claims WHERE deleted = 0 GROUP BY media_id"
    ).fetchall()
    media_counts = [{"media_id": int(r[0]), "count": int(r[1])} for r in media_rows if r]
    counts = [row["count"] for row in media_counts]
    mean_val = float(sum(counts) / len(counts)) if counts else None
    p95_val = _percentile_value(counts, 0.95) if counts else None
    max_val = max(counts) if counts else None
    top = sorted(media_counts, key=lambda row: row["count"], reverse=True)[:50]
    return top, {"mean": mean_val, "p95": p95_val, "max": max_val}


def _build_cluster_stats(db: MediaDatabase, owner_user_id: Optional[str]) -> Dict[str, Any]:
    conditions: List[str] = []
    params: List[Any] = []
    if owner_user_id:
        conditions.append("c.user_id = ?")
        params.append(str(owner_user_id))

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = (
        "SELECT c.id, c.canonical_claim_text, c.watchlist_count, c.updated_at, "
        "COALESCE(m.member_count, 0) AS member_count "
        "FROM claim_clusters c "
        "LEFT JOIN (SELECT cluster_id, COUNT(*) AS member_count "
        "FROM claim_cluster_membership GROUP BY cluster_id) m "
        "ON m.cluster_id = c.id "
        f"{where_clause}"
    )
    rows = db.execute_query(sql, tuple(params)).fetchall()
    cluster_rows = [dict(row) for row in rows if row]
    member_counts = [int(row.get("member_count") or 0) for row in cluster_rows]
    total_clusters = len(cluster_rows)
    clusters_with_members = sum(1 for count in member_counts if count > 0)
    total_members = sum(member_counts)
    avg_member_count = (
        float(total_members) / float(clusters_with_members) if clusters_with_members > 0 else None
    )
    p95_member_count = _percentile_value(member_counts, 0.95) if member_counts else None
    max_member_count = max(member_counts) if member_counts else None

    orphan_row = db.execute_query(
        "SELECT COUNT(*) AS count FROM Claims WHERE deleted = 0 AND claim_cluster_id IS NULL"
    ).fetchone()
    orphan_claims = int(orphan_row[0]) if orphan_row and orphan_row[0] is not None else 0

    top_clusters = sorted(cluster_rows, key=lambda row: int(row.get("member_count") or 0), reverse=True)[:20]
    top_payload = []
    for row in top_clusters:
        top_payload.append(
            {
                "cluster_id": int(row.get("id") or 0),
                "member_count": int(row.get("member_count") or 0),
                "watchlist_count": int(row.get("watchlist_count") or 0),
                "canonical_claim_text": row.get("canonical_claim_text"),
                "updated_at": row.get("updated_at"),
            }
        )

    return {
        "total_clusters": total_clusters,
        "clusters_with_members": clusters_with_members,
        "total_members": total_members,
        "avg_member_count": avg_member_count,
        "p95_member_count": p95_member_count,
        "max_member_count": max_member_count,
        "orphan_claims": orphan_claims,
        "top_clusters": top_payload,
    }


def _build_claims_analytics(db: MediaDatabase, owner_user_id: Optional[str], window_days: int) -> Dict[str, Any]:
    status_rows = db.execute_query(
        "SELECT review_status, COUNT(*) AS count FROM Claims WHERE deleted = 0 GROUP BY review_status"
    ).fetchall()
    status_counts = {str(r[0]): int(r[1]) for r in status_rows if r and r[0] is not None}
    total_claims = sum(status_counts.values())
    backlog = int(status_counts.get("pending", 0)) + int(status_counts.get("reassigned", 0))

    latency_stats = _build_review_latency_stats(db)
    top_media, media_stats = _build_claims_per_media_stats(db)
    review_throughput = _build_review_throughput(db, window_days)
    cluster_stats = _build_cluster_stats(db, owner_user_id)

    return {
        "total_claims": total_claims,
        "status_counts": status_counts,
        "avg_review_latency_sec": latency_stats.get("avg_review_latency_sec"),
        "p95_review_latency_sec": latency_stats.get("p95_review_latency_sec"),
        "review_backlog": backlog,
        "claims_per_media_top": top_media,
        "claims_per_media_stats": media_stats,
        "review_throughput": review_throughput,
        "clusters": cluster_stats,
    }


def _compute_unsupported_ratios(window_sec: int, baseline_sec: int) -> Dict[str, Optional[float]]:
    try:
        from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
    except Exception:
        return {"window_ratio": None, "baseline_ratio": None}

    reg = get_metrics_registry()
    now = time.time()

    def _sum_since(metric_name: str, since_ts: float) -> float:
        values = reg.values.get(metric_name) or []
        total = 0.0
        for sample in values:
            try:
                if float(sample.timestamp) >= since_ts:
                    total += float(sample.value)
            except Exception:
                continue
        return total

    window_since = now - max(1, int(window_sec))
    baseline_since = now - max(1, int(baseline_sec))

    total_window = _sum_since("rag_total_claims_checked_total", window_since)
    unsupported_window = _sum_since("rag_unsupported_claims_total", window_since)
    total_baseline = _sum_since("rag_total_claims_checked_total", baseline_since)
    unsupported_baseline = _sum_since("rag_unsupported_claims_total", baseline_since)

    window_ratio = unsupported_window / total_window if total_window > 0 else None
    baseline_ratio = unsupported_baseline / total_baseline if total_baseline > 0 else None

    return {"window_ratio": window_ratio, "baseline_ratio": baseline_ratio}


@contextmanager
def _resolve_media_db(
    *,
    db: MediaDatabase,
    current_user: User,
    user_id: Optional[int],
    admin_required: bool,
    owner_filter: bool = False,
) -> Tuple[MediaDatabase, Optional[int]]:
    override_db: Optional[MediaDatabase] = None
    owner_user_id: Optional[int] = None
    try:
        if user_id is not None:
            if not getattr(current_user, "is_admin", False) and admin_required:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
            if db.backend_type == BackendType.POSTGRESQL:
                owner_user_id = int(user_id) if owner_filter else None
                target_db = db
            else:
                db_path = get_user_media_db_path(int(user_id))
                override_db = MediaDatabase(
                    db_path=db_path,
                    client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
                )
                target_db = override_db
        else:
            target_db = db
        yield target_db, owner_user_id
    finally:
        if override_db is not None:
            try:
                override_db.close_connection()
            except Exception:
                pass


def list_all_claims(
    *,
    media_id: Optional[int],
    review_status: Optional[str],
    reviewer_id: Optional[int],
    review_group: Optional[str],
    claim_cluster_id: Optional[int],
    limit: int,
    offset: int,
    include_deleted: bool,
    user_id: Optional[int],
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=True,
    ) as (target_db, owner_filter):
        claims = target_db.list_claims(
            media_id=media_id,
            owner_user_id=owner_filter,
            review_status=review_status,
            reviewer_id=reviewer_id,
            review_group=review_group,
            claim_cluster_id=claim_cluster_id,
            limit=limit,
            offset=offset,
            include_deleted=include_deleted,
        )
        return [_normalize_claim_row(dict(row)) for row in claims]


def list_claim_notifications(
    *,
    kind: Optional[str],
    target_user_id: Optional[str],
    target_review_group: Optional[str],
    resource_type: Optional[str],
    resource_id: Optional[str],
    delivered: Optional[bool],
    limit: int,
    offset: int,
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_review(principal)
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        target_user = str(user_id) if user_id is not None else str(current_user.id)
        if not principal.is_admin and target_user_id is not None and str(target_user_id) != str(principal.user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        rows = target_db.list_claim_notifications(
            user_id=target_user,
            kind=kind,
            target_user_id=str(target_user_id) if target_user_id is not None else None,
            target_review_group=str(target_review_group) if target_review_group else None,
            resource_type=str(resource_type) if resource_type else None,
            resource_id=str(resource_id) if resource_id else None,
            delivered=delivered,
            limit=limit,
            offset=offset,
        )
        filtered = _filter_notifications_for_principal(principal, rows)
        return [_normalize_notification_row(row) for row in filtered]


def mark_claim_notifications_delivered(
    *,
    ids: List[int],
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    if not ids:
        return {"status": "ok", "updated": 0}
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        rows = target_db.get_claim_notifications_by_ids(ids)
        filtered = _filter_notifications_for_principal(principal, rows)
        allowed_ids = [int(row.get("id")) for row in filtered if row.get("id") is not None]
        updated = target_db.mark_claim_notifications_delivered(allowed_ids)
        return {"status": "ok", "updated": int(updated)}


def claim_notifications_digest(
    *,
    kind: Optional[str],
    target_user_id: Optional[str],
    target_review_group: Optional[str],
    resource_type: Optional[str],
    resource_id: Optional[str],
    delivered: Optional[bool],
    limit: int,
    offset: int,
    include_items: bool,
    ack: bool,
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        target_user = str(user_id) if user_id is not None else str(current_user.id)
        rows = target_db.list_claim_notifications(
            user_id=target_user,
            kind=kind,
            target_user_id=str(target_user_id) if target_user_id is not None else None,
            target_review_group=str(target_review_group) if target_review_group else None,
            resource_type=str(resource_type) if resource_type else None,
            resource_id=str(resource_id) if resource_id else None,
            delivered=delivered,
            limit=limit,
            offset=offset,
        )
        filtered = _filter_notifications_for_principal(principal, rows)
        counts_by_kind: Dict[str, int] = {}
        counts_by_target_user: Dict[str, int] = {}
        counts_by_review_group: Dict[str, int] = {}
        normalized = [_normalize_notification_row(row) for row in filtered]
        for row in normalized:
            kind_val = str(row.get("kind") or "unknown")
            counts_by_kind[kind_val] = counts_by_kind.get(kind_val, 0) + 1
            target_user = row.get("target_user_id")
            if target_user:
                key = str(target_user)
                counts_by_target_user[key] = counts_by_target_user.get(key, 0) + 1
            target_group = row.get("target_review_group")
            if target_group:
                key = str(target_group)
                counts_by_review_group[key] = counts_by_review_group.get(key, 0) + 1
        if ack:
            allowed_ids = [int(row.get("id")) for row in normalized if row.get("id") is not None]
            target_db.mark_claim_notifications_delivered(allowed_ids)
        payload: Dict[str, Any] = {
            "total": len(normalized),
            "counts_by_kind": counts_by_kind,
            "counts_by_target_user": counts_by_target_user,
            "counts_by_review_group": counts_by_review_group,
        }
        if include_items:
            payload["notifications"] = normalized
        return payload


def get_claims_settings(principal: AuthPrincipal) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    return _claims_settings_snapshot()


def update_claims_settings(
    *,
    payload: Dict[str, Any],
    principal: AuthPrincipal,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    updates: Dict[str, Any] = {}
    if payload.get("enable_ingestion_claims") is not None:
        updates["ENABLE_INGESTION_CLAIMS"] = bool(payload["enable_ingestion_claims"])
    if payload.get("claim_extractor_mode") is not None:
        updates["CLAIM_EXTRACTOR_MODE"] = str(payload["claim_extractor_mode"]).strip()
    if payload.get("claims_max_per_chunk") is not None:
        updates["CLAIMS_MAX_PER_CHUNK"] = int(payload["claims_max_per_chunk"])
    if payload.get("claims_embed") is not None:
        updates["CLAIMS_EMBED"] = bool(payload["claims_embed"])
    if payload.get("claims_embed_model_id") is not None:
        updates["CLAIMS_EMBED_MODEL_ID"] = str(payload["claims_embed_model_id"])
    if payload.get("claims_cluster_method") is not None:
        updates["CLAIMS_CLUSTER_METHOD"] = str(payload["claims_cluster_method"]).strip()
    if payload.get("claims_cluster_similarity_threshold") is not None:
        updates["CLAIMS_CLUSTER_SIMILARITY_THRESHOLD"] = float(payload["claims_cluster_similarity_threshold"])
    if payload.get("claims_cluster_batch_size") is not None:
        updates["CLAIMS_CLUSTER_BATCH_SIZE"] = int(payload["claims_cluster_batch_size"])
    if payload.get("claims_llm_provider") is not None:
        updates["CLAIMS_LLM_PROVIDER"] = str(payload["claims_llm_provider"])
    if payload.get("claims_llm_temperature") is not None:
        updates["CLAIMS_LLM_TEMPERATURE"] = float(payload["claims_llm_temperature"])
    if payload.get("claims_llm_model") is not None:
        updates["CLAIMS_LLM_MODEL"] = str(payload["claims_llm_model"])
    if payload.get("claims_rebuild_enabled") is not None:
        updates["CLAIMS_REBUILD_ENABLED"] = bool(payload["claims_rebuild_enabled"])
    if payload.get("claims_rebuild_interval_sec") is not None:
        updates["CLAIMS_REBUILD_INTERVAL_SEC"] = int(payload["claims_rebuild_interval_sec"])
    if payload.get("claims_rebuild_policy") is not None:
        updates["CLAIMS_REBUILD_POLICY"] = str(payload["claims_rebuild_policy"])
    if payload.get("claims_stale_days") is not None:
        updates["CLAIMS_STALE_DAYS"] = int(payload["claims_stale_days"])

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided")

    for key, value in updates.items():
        settings[key] = value

    if payload.get("persist"):
        try:
            setup_manager.update_config({"Claims": updates})
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _claims_settings_snapshot()


def get_claims_monitoring_config(principal: AuthPrincipal) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    return _claims_monitoring_settings_snapshot()


def update_claims_monitoring_config(
    *,
    payload: Dict[str, Any],
    principal: AuthPrincipal,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    updates: Dict[str, Any] = {}
    if payload.get("claims_monitoring_enabled") is not None:
        updates["CLAIMS_MONITORING_ENABLED"] = bool(payload["claims_monitoring_enabled"])
    if payload.get("claims_alert_threshold_default") is not None:
        updates["CLAIMS_ALERT_THRESHOLD_DEFAULT"] = float(payload["claims_alert_threshold_default"])
    if payload.get("claims_rebuild_max_queue_alert") is not None:
        updates["CLAIMS_REBUILD_MAX_QUEUE_ALERT"] = int(payload["claims_rebuild_max_queue_alert"])
    if payload.get("claims_rebuild_heartbeat_warn_sec") is not None:
        updates["CLAIMS_REBUILD_HEARTBEAT_WARN_SEC"] = int(payload["claims_rebuild_heartbeat_warn_sec"])
    if payload.get("claims_provider_cost_multipliers") is not None:
        updates["CLAIMS_PROVIDER_COST_MULTIPLIERS"] = dict(payload["claims_provider_cost_multipliers"])

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided")

    for key, value in updates.items():
        settings[key] = value

    if payload.get("persist"):
        persist_updates = dict(updates)
        if "CLAIMS_PROVIDER_COST_MULTIPLIERS" in persist_updates:
            persist_updates["CLAIMS_PROVIDER_COST_MULTIPLIERS"] = json.dumps(
                persist_updates["CLAIMS_PROVIDER_COST_MULTIPLIERS"]
            )
        try:
            setup_manager.update_config({"ClaimsMonitoring": persist_updates})
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _claims_monitoring_settings_snapshot()


def list_claims_alerts(
    *,
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))
    rows = db.list_claims_monitoring_configs(target_user_id)
    return [_normalize_alert_row(dict(r)) for r in rows]


def create_claims_alert(
    *,
    payload: Dict[str, Any],
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))
    email_json = None
    if payload.get("email_recipients") is not None:
        email_json = json.dumps(payload["email_recipients"])
    config = db.create_claims_monitoring_config(
        user_id=target_user_id,
        threshold_ratio=payload.get("threshold_ratio"),
        baseline_ratio=payload.get("baseline_ratio"),
        slack_webhook_url=payload.get("slack_webhook_url"),
        webhook_url=payload.get("webhook_url"),
        email_recipients=email_json,
        enabled=payload.get("enabled") if payload.get("enabled") is not None else True,
    )
    if not config:
        raise HTTPException(status_code=500, detail="Failed to create alert config")
    return _normalize_alert_row(config)


def update_claims_alert(
    *,
    config_id: int,
    payload: Dict[str, Any],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    existing = db.get_claims_monitoring_config(int(config_id))
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert config not found")
    if not principal.is_admin and str(existing.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    email_json = None
    if payload.get("email_recipients") is not None:
        email_json = json.dumps(payload["email_recipients"])
    updated = db.update_claims_monitoring_config(
        int(config_id),
        threshold_ratio=payload.get("threshold_ratio"),
        baseline_ratio=payload.get("baseline_ratio"),
        slack_webhook_url=payload.get("slack_webhook_url"),
        webhook_url=payload.get("webhook_url"),
        email_recipients=email_json,
        enabled=payload.get("enabled"),
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update alert config")
    return _normalize_alert_row(updated)


def delete_claims_alert(
    *,
    config_id: int,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    existing = db.get_claims_monitoring_config(int(config_id))
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert config not found")
    if not principal.is_admin and str(existing.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    db.delete_claims_monitoring_config(int(config_id))
    return {"status": "deleted", "id": int(config_id)}


def evaluate_claims_alerts(
    *,
    window_sec: int,
    baseline_sec: int,
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))

    monitoring_enabled = bool(settings.get("CLAIMS_MONITORING_ENABLED", False))
    ratios = _compute_unsupported_ratios(window_sec, baseline_sec)
    configs = db.list_claims_monitoring_configs(target_user_id)
    results: List[Dict[str, Any]] = []
    for cfg in configs:
        enabled = bool(cfg.get("enabled", True))
        threshold = cfg.get("threshold_ratio")
        if threshold is None:
            threshold = settings.get("CLAIMS_ALERT_THRESHOLD_DEFAULT", 0.2)
        try:
            threshold_val = float(threshold)
        except Exception:
            threshold_val = 0.2
        drift_threshold_val = None
        drift_threshold = cfg.get("baseline_ratio")
        if drift_threshold is not None:
            try:
                drift_threshold_val = float(drift_threshold)
            except Exception:
                drift_threshold_val = None
        window_ratio = ratios.get("window_ratio")
        baseline_ratio = ratios.get("baseline_ratio")
        drift = None
        if window_ratio is not None and baseline_ratio is not None:
            drift = window_ratio - baseline_ratio
        triggered = (
            monitoring_enabled
            and enabled
            and window_ratio is not None
            and (
                window_ratio > threshold_val
                or (drift_threshold_val is not None and drift is not None and drift > drift_threshold_val)
            )
        )
        if triggered:
            payload = {
                "window_ratio": window_ratio,
                "baseline_ratio": baseline_ratio,
                "threshold": threshold_val,
                "drift_threshold": drift_threshold_val,
                "drift": drift,
                "user_id": target_user_id,
                "window_sec": window_sec,
                "baseline_sec": baseline_sec,
            }
            db.insert_claims_monitoring_event(
                user_id=str(target_user_id),
                event_type="unsupported_ratio",
                severity="warning",
                payload_json=json.dumps(payload),
            )
            _dispatch_claims_alert_notifications(dict(cfg), payload)
        results.append(
            {
                "config_id": cfg.get("id"),
                "enabled": enabled,
                "threshold": threshold_val,
                "baseline_ratio": baseline_ratio,
                "drift_threshold": drift_threshold_val,
                "drift": drift,
                "triggered": triggered,
                "window_ratio": window_ratio,
            }
        )
    return {"monitoring_enabled": monitoring_enabled, "ratios": ratios, "results": results}


def claims_rebuild_status(*, rebuild_service: Any = None) -> Dict[str, Any]:
    """Return statistics about the claims rebuild worker."""
    try:
        svc = rebuild_service or get_claims_rebuild_service()
        try:
            stats = svc.get_stats()
        except Exception:
            stats = {}
        try:
            qlen = svc.get_queue_length()
        except Exception:
            qlen = 0
        try:
            workers = svc.get_worker_count()
        except Exception:
            workers = None
        return {"status": "ok", "stats": stats, "queue_length": qlen, "workers": workers}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def claims_rebuild_health(principal: AuthPrincipal) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    svc = get_claims_rebuild_service()
    health = svc.get_health()
    now_ts = datetime.utcnow().timestamp()
    heartbeat_ts = float(health.get("last_heartbeat_ts") or 0.0)
    age_sec = now_ts - heartbeat_ts if heartbeat_ts > 0 else None
    warn_threshold = int(settings.get("CLAIMS_REBUILD_HEARTBEAT_WARN_SEC", 600))
    stale = age_sec is not None and age_sec > warn_threshold
    return {
        "status": "ok",
        "queue_length": int(health.get("queue_length") or 0),
        "workers": int(health.get("workers") or 0),
        "last_heartbeat_ts": heartbeat_ts,
        "heartbeat_age_sec": age_sec,
        "last_processed_ts": health.get("last_processed_ts"),
        "last_failure": health.get("last_failure"),
        "stale": stale,
    }


def get_review_queue(
    *,
    status_filter: Optional[str],
    reviewer_id: Optional[int],
    review_group: Optional[str],
    media_id: Optional[int],
    extractor: Optional[str],
    limit: int,
    offset: int,
    include_deleted: bool,
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_review(principal)
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=not principal.is_admin,
        owner_filter=True,
    ) as (target_db, owner_filter):
        if status_filter is None:
            status_filter = "pending"
        if not principal.is_admin:
            if reviewer_id is not None and int(reviewer_id) != int(principal.user_id or 0):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
            if review_group is not None:
                if str(review_group) not in [str(r) for r in (principal.roles or [])]:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
            if reviewer_id is None and review_group is None:
                reviewer_id = int(principal.user_id or 0)

        rows = target_db.list_review_queue(
            status=status_filter,
            reviewer_id=reviewer_id,
            review_group=review_group,
            media_id=media_id,
            extractor=extractor,
            owner_user_id=owner_filter,
            limit=limit,
            offset=offset,
            include_deleted=include_deleted,
        )
        record_claims_review_metrics(queue_size=len(rows))
        return [_normalize_claim_row(dict(r)) for r in rows]


async def review_claim(
    *,
    claim_id: int,
    payload: Dict[str, Any],
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
    request: Any = None,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=not principal.is_admin,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        claim_row = target_db.get_claim_with_media(int(claim_id), include_deleted=True)
        if not claim_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

        current_status = str(claim_row.get("review_status") or "pending").lower()
        new_status = str(payload.get("status")).lower()
        if not _is_review_transition_allowed(current_status, new_status):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid review transition")
        if new_status == "reassigned" and not (payload.get("reviewer_id") or payload.get("review_group")):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reassigned requires reviewer or group")

        reviewer_id = payload.get("reviewer_id")
        if not principal.is_admin:
            if reviewer_id is not None and int(reviewer_id) != int(principal.user_id or 0):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
            reviewer_id = int(principal.user_id or 0)
            if payload.get("review_group") is not None:
                if str(payload.get("review_group")) not in [str(r) for r in (principal.roles or [])]:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        if not principal.is_admin and not _can_review_claim(principal, claim_row):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        action_ip, action_user_agent = _extract_request_metadata(request)

        updated = target_db.update_claim_review(
            int(claim_id),
            review_status=new_status,
            reviewer_id=reviewer_id,
            review_group=payload.get("review_group"),
            review_notes=payload.get("notes"),
            review_reason_code=payload.get("reason_code"),
            corrected_text=payload.get("corrected_text"),
            expected_version=int(payload.get("review_version")),
            action_ip=action_ip,
            action_user_agent=action_user_agent,
        )
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
        if isinstance(updated, dict) and updated.get("conflict"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "version_conflict",
                    "current": updated.get("current"),
                },
            )
        latency_s = None
        try:
            created_at_raw = claim_row.get("created_at")
            if created_at_raw:
                created_at = datetime.fromisoformat(str(created_at_raw).replace("Z", "+00:00"))
                latency_s = (datetime.utcnow().replace(tzinfo=created_at.tzinfo) - created_at).total_seconds()
        except Exception:
            latency_s = None
        record_claims_review_metrics(processed=1, latency_s=latency_s)
        if new_status in {"flagged", "reassigned"} and new_status != current_status:
            _enqueue_claim_rebuild_if_needed(
                media_id=int(claim_row.get("media_id") or 0),
                db_path=str(target_db.db_path_str),
            )
        if payload.get("corrected_text"):
            target_user_id = str(user_id) if user_id is not None else str(current_user.id)
            _refresh_claim_embedding(
                claim_id=int(claim_id),
                media_id=int(claim_row.get("media_id") or 0),
                chunk_index=int(claim_row.get("chunk_index") or 0),
                old_text=str(claim_row.get("claim_text") or ""),
                new_text=str(payload.get("corrected_text")),
                user_id=target_user_id,
            )
        return _normalize_claim_row(dict(updated))


def get_claim_review_history(
    *,
    claim_id: int,
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_review(principal)
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=not principal.is_admin,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        claim_row = target_db.get_claim_with_media(int(claim_id), include_deleted=True)
        if not claim_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
        if not principal.is_admin and not _can_review_claim(principal, claim_row):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        return target_db.list_claim_review_history(int(claim_id))


def bulk_review_claims(
    *,
    payload: Dict[str, Any],
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
    request: Any = None,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    if str(payload.get("status")).lower() == "reassigned" and not (
        payload.get("reviewer_id") or payload.get("review_group")
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reassigned requires reviewer or group")
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=not principal.is_admin,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        updated_ids: List[int] = []
        conflicts: List[int] = []
        missing: List[int] = []
        invalid: List[int] = []
        rebuild_media_ids: set[int] = set()
        action_ip, action_user_agent = _extract_request_metadata(request)
        desired_status = str(payload.get("status")).lower()
        for cid in payload.get("claim_ids") or []:
            claim_row = target_db.get_claim_with_media(int(cid), include_deleted=True)
            if not claim_row:
                missing.append(int(cid))
                continue
            current_status = str(claim_row.get("review_status") or "pending").lower()
            if not _is_review_transition_allowed(current_status, desired_status):
                invalid.append(int(cid))
                continue
            updated = target_db.update_claim_review(
                int(cid),
                review_status=desired_status,
                reviewer_id=payload.get("reviewer_id"),
                review_group=payload.get("review_group"),
                review_notes=payload.get("notes"),
                review_reason_code=payload.get("reason_code"),
                expected_version=int(claim_row.get("review_version") or 1),
                action_ip=action_ip,
                action_user_agent=action_user_agent,
            )
            if isinstance(updated, dict) and updated.get("conflict"):
                conflicts.append(int(cid))
            elif updated is None:
                missing.append(int(cid))
            else:
                updated_ids.append(int(cid))
                if desired_status in {"flagged", "reassigned"} and desired_status != current_status:
                    try:
                        rebuild_media_ids.add(int(claim_row.get("media_id") or 0))
                    except Exception:
                        pass

        if updated_ids:
            record_claims_review_metrics(processed=len(updated_ids))
        if rebuild_media_ids:
            for media_id in rebuild_media_ids:
                if media_id > 0:
                    _enqueue_claim_rebuild_if_needed(
                        media_id=media_id,
                        db_path=str(target_db.db_path_str),
                    )
        return {
            "updated": updated_ids,
            "conflicts": conflicts,
            "missing": missing,
            "invalid": invalid,
        }


def list_review_rules(
    *,
    user_id: Optional[int],
    active_only: bool,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))
    rows = db.list_claim_review_rules(target_user_id, active_only=active_only)
    return [_normalize_review_rule(r) for r in rows]


def create_review_rule(
    *,
    payload: Dict[str, Any],
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))
    rule = db.create_claim_review_rule(
        user_id=target_user_id,
        priority=payload.get("priority"),
        predicate_json=json.dumps(payload.get("predicate_json")),
        reviewer_id=payload.get("reviewer_id"),
        review_group=payload.get("review_group"),
        active=payload.get("active") if payload.get("active") is not None else True,
    )
    if not rule:
        raise HTTPException(status_code=500, detail="Failed to create rule")
    return _normalize_review_rule(rule)


def update_review_rule(
    *,
    rule_id: int,
    payload: Dict[str, Any],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    existing = db.get_claim_review_rule(int(rule_id))
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    if not principal.is_admin and str(existing.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    updated = db.update_claim_review_rule(
        int(rule_id),
        priority=payload.get("priority"),
        predicate_json=json.dumps(payload.get("predicate_json")) if payload.get("predicate_json") is not None else None,
        reviewer_id=payload.get("reviewer_id"),
        review_group=payload.get("review_group"),
        active=payload.get("active"),
    )
    return _normalize_review_rule(updated)


def delete_review_rule(
    *,
    rule_id: int,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    existing = db.get_claim_review_rule(int(rule_id))
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    if not principal.is_admin and str(existing.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    db.delete_claim_review_rule(int(rule_id))
    return {"status": "deleted", "id": int(rule_id)}


def review_analytics(principal: AuthPrincipal, db: MediaDatabase) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    owner_user_id = str(principal.user_id) if principal.user_id is not None else None
    return _build_claims_analytics(db, owner_user_id, window_days=7)


def claims_dashboard_analytics(
    *,
    window_days: int,
    window_sec: int,
    baseline_sec: int,
    principal: AuthPrincipal,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    owner_user_id = str(principal.user_id) if principal.user_id is not None else None
    payload = _build_claims_analytics(db, owner_user_id, window_days=window_days)
    ratios = _compute_unsupported_ratios(window_sec, baseline_sec)
    payload["unsupported_ratios"] = {
        "window_sec": int(window_sec),
        "baseline_sec": int(baseline_sec),
        "window_ratio": ratios.get("window_ratio"),
        "baseline_ratio": ratios.get("baseline_ratio"),
    }
    try:
        payload["rebuild_health"] = claims_rebuild_health(principal)
    except Exception:
        payload["rebuild_health"] = None
    return payload


def export_claims_analytics(
    *,
    payload: Dict[str, Any],
    principal: AuthPrincipal,
    db: MediaDatabase,
) -> Any:
    _ensure_claims_admin(principal)
    window_days = int(payload.get("window_days") or 7)
    window_sec = int(payload.get("window_sec") or 3600)
    baseline_sec = int(payload.get("baseline_sec") or 86400)
    data = claims_dashboard_analytics(
        window_days=window_days,
        window_sec=window_sec,
        baseline_sec=baseline_sec,
        principal=principal,
        db=db,
    )
    if payload.get("format") == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["section", "metric", "dimension", "value"])
        writer.writerow(["summary", "total_claims", "", data.get("total_claims")])
        writer.writerow(["summary", "avg_review_latency_sec", "", data.get("avg_review_latency_sec")])
        writer.writerow(["summary", "p95_review_latency_sec", "", data.get("p95_review_latency_sec")])
        writer.writerow(["summary", "review_backlog", "", data.get("review_backlog")])

        for status_key, count in (data.get("status_counts") or {}).items():
            writer.writerow(["status_counts", "count", str(status_key), count])

        media_stats = data.get("claims_per_media_stats") or {}
        writer.writerow(["claims_per_media_stats", "mean", "", media_stats.get("mean")])
        writer.writerow(["claims_per_media_stats", "p95", "", media_stats.get("p95")])
        writer.writerow(["claims_per_media_stats", "max", "", media_stats.get("max")])
        for row in data.get("claims_per_media_top") or []:
            writer.writerow(
                [
                    "claims_per_media_top",
                    "count",
                    f"media_id={row.get('media_id')}",
                    row.get("count"),
                ]
            )

        review_throughput = data.get("review_throughput") or {}
        for point in review_throughput.get("daily") or []:
            writer.writerow(["review_throughput", "count", str(point.get("date")), point.get("count")])

        clusters = data.get("clusters") or {}
        writer.writerow(["clusters", "total_clusters", "", clusters.get("total_clusters")])
        writer.writerow(["clusters", "clusters_with_members", "", clusters.get("clusters_with_members")])
        writer.writerow(["clusters", "total_members", "", clusters.get("total_members")])
        writer.writerow(["clusters", "avg_member_count", "", clusters.get("avg_member_count")])
        writer.writerow(["clusters", "p95_member_count", "", clusters.get("p95_member_count")])
        writer.writerow(["clusters", "max_member_count", "", clusters.get("max_member_count")])
        writer.writerow(["clusters", "orphan_claims", "", clusters.get("orphan_claims")])
        for row in clusters.get("top_clusters") or []:
            cluster_id = row.get("cluster_id")
            writer.writerow(
                [
                    "clusters_top",
                    "member_count",
                    f"cluster_id={cluster_id}",
                    row.get("member_count"),
                ]
            )
            writer.writerow(
                [
                    "clusters_top",
                    "watchlist_count",
                    f"cluster_id={cluster_id}",
                    row.get("watchlist_count"),
                ]
            )
            if row.get("canonical_claim_text") is not None:
                writer.writerow(
                    [
                        "clusters_top",
                        "canonical_claim_text",
                        f"cluster_id={cluster_id}",
                        row.get("canonical_claim_text"),
                    ]
                )

        ratios = data.get("unsupported_ratios") or {}
        writer.writerow(["unsupported_ratios", "window_sec", "", ratios.get("window_sec")])
        writer.writerow(["unsupported_ratios", "baseline_sec", "", ratios.get("baseline_sec")])
        writer.writerow(["unsupported_ratios", "window_ratio", "", ratios.get("window_ratio")])
        writer.writerow(["unsupported_ratios", "baseline_ratio", "", ratios.get("baseline_ratio")])

        rebuild = data.get("rebuild_health") or {}
        if isinstance(rebuild, dict):
            for key, value in rebuild.items():
                if key == "last_failure" and value is not None:
                    value = json.dumps(value)
                writer.writerow(["rebuild_health", key, "", value])
        return output.getvalue()
    return data


def list_claim_clusters(
    *,
    limit: int,
    offset: int,
    updated_since: Optional[str],
    keyword: Optional[str],
    min_size: Optional[int],
    watchlisted: Optional[bool],
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_review(principal)
    target_user_id = str(current_user.id)
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))
    clusters = db.list_claim_clusters(
        target_user_id,
        limit=limit,
        offset=offset,
        updated_since=updated_since,
        keyword=keyword,
        min_size=min_size,
        watchlisted=None,
    )
    counts = _load_watchlist_cluster_counts(target_user_id, [int(c.get("id")) for c in clusters if c.get("id")])
    if counts:
        for cluster in clusters:
            try:
                cluster_id = int(cluster.get("id"))
            except Exception:
                continue
            cluster["watchlist_count"] = int(counts.get(cluster_id, 0))
    if watchlisted is not None:
        clusters = [
            c for c in clusters if (int(c.get("watchlist_count") or 0) > 0) == bool(watchlisted)
        ]
    return clusters


def rebuild_claim_clusters(
    *,
    min_size: int,
    user_id: Optional[int],
    method: Optional[str],
    similarity_threshold: Optional[float],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))
    cluster_method = (method or settings.get("CLAIMS_CLUSTER_METHOD", "embeddings") or "embeddings").strip().lower()
    if cluster_method not in {"embeddings", "exact"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid clustering method")

    if user_id is not None and db.backend_type != BackendType.POSTGRESQL:
        db_path = get_user_media_db_path(int(user_id))
        override_db = MediaDatabase(
            db_path=db_path,
            client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
        )
        try:
            if cluster_method == "exact":
                return override_db.rebuild_claim_clusters_exact(user_id=target_user_id, min_size=min_size)
            return rebuild_claim_clusters_embeddings(
                db=override_db,
                user_id=target_user_id,
                min_size=min_size,
                similarity_threshold=similarity_threshold,
            )
        finally:
            try:
                override_db.close_connection()
            except Exception:
                pass

    if cluster_method == "exact":
        result = db.rebuild_claim_clusters_exact(user_id=target_user_id, min_size=min_size)
    else:
        result = rebuild_claim_clusters_embeddings(
            db=db,
            user_id=target_user_id,
            min_size=min_size,
            similarity_threshold=similarity_threshold,
        )

    try:
        watchlist_result = _evaluate_watchlist_cluster_notifications(db, target_user_id)
        result["watchlist_notifications"] = watchlist_result
    except Exception:
        pass
    return result


def _evaluate_watchlist_cluster_notifications(db: MediaDatabase, user_id: str) -> Dict[str, Any]:
    watch_db = _get_watchlists_db(user_id)
    if not watch_db:
        return {"status": "skipped", "reason": "watchlists_unavailable"}
    rows = watch_db.list_watchlist_cluster_subscriptions()
    if not rows:
        return {"status": "skipped", "reason": "no_subscriptions"}
    subscriptions: Dict[int, List[int]] = {}
    for row in rows:
        try:
            cluster_id = int(row.get("cluster_id"))
            job_id = int(row.get("job_id"))
        except Exception:
            continue
        subscriptions.setdefault(cluster_id, []).append(job_id)
    cluster_ids = list(subscriptions.keys())
    clusters = db.get_claim_clusters_by_ids(cluster_ids)
    cluster_map = {int(c.get("id")): c for c in clusters if c.get("id") is not None}
    member_counts = db.get_claim_cluster_member_counts(cluster_ids)
    counts = watch_db.list_watchlist_cluster_counts(cluster_ids=cluster_ids)
    if counts:
        try:
            db.update_claim_clusters_watchlist_counts(counts)
        except Exception:
            pass
    inserted = record_watchlist_cluster_notifications(
        db=db,
        owner_user_id=str(user_id),
        clusters=cluster_map,
        member_counts=member_counts,
        subscriptions=subscriptions,
    )
    return {
        "status": "ok",
        "subscriptions": len(subscriptions),
        "notifications": inserted,
    }


def get_claim_cluster(
    *,
    cluster_id: int,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    cluster = db.get_claim_cluster(int(cluster_id))
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    if not principal.is_admin and str(cluster.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    count_row = db.execute_query(
        "SELECT COUNT(*) AS total FROM claim_cluster_membership WHERE cluster_id = ?",
        (int(cluster_id),),
    ).fetchone()
    size = int(count_row[0]) if count_row else 0
    payload = dict(cluster)
    counts = _load_watchlist_cluster_counts(str(cluster.get("user_id") or current_user.id), [int(cluster_id)])
    if counts:
        payload["watchlist_count"] = int(counts.get(int(cluster_id), payload.get("watchlist_count") or 0))
    payload["member_count"] = size
    return payload


def list_claim_cluster_members(
    *,
    cluster_id: int,
    limit: int,
    offset: int,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_review(principal)
    cluster = db.get_claim_cluster(int(cluster_id))
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    if not principal.is_admin and str(cluster.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    rows = db.list_claim_cluster_members(int(cluster_id), limit=limit, offset=offset)
    return [_normalize_claim_row(dict(r)) for r in rows]


def evaluate_watchlist_cluster_notifications(
    *,
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        target_user_id = str(user_id) if user_id is not None else str(current_user.id)
        return _evaluate_watchlist_cluster_notifications(target_db, target_user_id)


def claim_cluster_timeline(
    *,
    cluster_id: int,
    limit: int,
    offset: int,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    cluster = db.get_claim_cluster(int(cluster_id))
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    if not principal.is_admin and str(cluster.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    rows = db.execute_query(
        "SELECT DATE(cluster_joined_at) AS day, COUNT(*) AS count "
        "FROM claim_cluster_membership WHERE cluster_id = ? "
        "GROUP BY day ORDER BY day ASC LIMIT ? OFFSET ?",
        (int(cluster_id), int(limit), int(offset)),
    ).fetchall()
    timeline = [{"day": r[0], "count": int(r[1])} for r in rows if r]
    return {"cluster_id": int(cluster_id), "timeline": timeline}


def claim_cluster_evidence(
    *,
    cluster_id: int,
    limit: int,
    offset: int,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    cluster = db.get_claim_cluster(int(cluster_id))
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    if not principal.is_admin and str(cluster.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    members = db.list_claim_cluster_members(int(cluster_id), limit=limit, offset=offset)
    buckets = {"supported": [], "refuted": [], "nei": []}
    for row in members:
        status_val = str(row.get("review_status") or "pending").lower()
        if status_val == "approved":
            buckets["supported"].append(_normalize_claim_row(dict(row)))
        elif status_val == "rejected":
            buckets["refuted"].append(_normalize_claim_row(dict(row)))
        else:
            buckets["nei"].append(_normalize_claim_row(dict(row)))

    counts = {k: len(v) for k, v in buckets.items()}
    return {
        "cluster_id": int(cluster_id),
        "counts": counts,
        "evidence": buckets,
    }


def list_claims_by_media(
    *,
    media_id: int,
    limit: int,
    offset: int,
    envelope: bool,
    absolute_links: bool,
    user_id: Optional[int],
    current_user: User,
    db: MediaDatabase,
    request: Any = None,
) -> Any:
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        claims = target_db.get_claims_by_media(media_id, limit=limit, offset=offset)
        if not envelope:
            return claims
        try:
            cur = target_db.execute_query(
                "SELECT COUNT(*) AS c FROM Claims WHERE media_id = ? AND deleted = 0",
                (media_id,),
            )
            row = cur.fetchone()
            total = int(row[0]) if row else 0
        except Exception:
            total = offset + len(claims)
        next_off: Optional[int] = None
        if offset + len(claims) < total:
            next_off = offset + len(claims)
        next_link: Optional[str] = None
        if next_off is not None:
            if request and absolute_links:
                base = f"{request.url.scheme}://{request.url.netloc}{request.url.path}"
            else:
                base = request.url.path if request else f"/api/v1/claims/{media_id}"
            params = f"limit={limit}&offset={next_off}&envelope=true"
            if user_id is not None and getattr(current_user, "is_admin", False):
                params += f"&user_id={int(user_id)}"
            if absolute_links:
                params += "&absolute_links=true"
            next_link = f"{base}?{params}"
        total_pages = int((total + int(limit) - 1) // int(limit)) if int(limit) > 0 else 0
        return {
            "items": claims,
            "next_offset": next_off,
            "total": total,
            "total_pages": total_pages,
            "next_link": next_link,
        }


def get_claim_item(
    *,
    claim_id: int,
    include_deleted: bool,
    user_id: Optional[int],
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        row = target_db.get_claim_with_media(int(claim_id), include_deleted=include_deleted)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
        return _normalize_claim_row(dict(row))


async def update_claim_item(
    *,
    claim_id: int,
    payload: Dict[str, Any],
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        claim_row = target_db.get_claim_with_media(int(claim_id), include_deleted=True)
        if not claim_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

        await _ensure_claim_edit_access(principal=principal, claim_row=claim_row)

        updated = target_db.update_claim(
            int(claim_id),
            claim_text=payload.get("claim_text"),
            span_start=payload.get("span_start"),
            span_end=payload.get("span_end"),
            confidence=payload.get("confidence"),
            extractor=payload.get("extractor"),
            extractor_version=payload.get("extractor_version"),
            deleted=payload.get("deleted"),
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
        if payload.get("claim_text") is not None:
            old_text = str(claim_row.get("claim_text") or "")
            new_text = str(payload.get("claim_text"))
            if new_text != old_text:
                target_user_id = str(user_id) if user_id is not None else str(current_user.id)
                _refresh_claim_embedding(
                    claim_id=int(claim_id),
                    media_id=int(claim_row.get("media_id") or 0),
                    chunk_index=int(claim_row.get("chunk_index") or 0),
                    old_text=old_text,
                    new_text=new_text,
                    user_id=target_user_id,
                )
        return _normalize_claim_row(dict(updated))


def rebuild_claims(
    *,
    media_id: int,
    user_id: Optional[int],
    current_user: User,
    db: MediaDatabase,
    rebuild_service: Any = None,
) -> Dict[str, Any]:
    if user_id is not None and getattr(current_user, "is_admin", False):
        db_path = get_user_media_db_path(int(user_id))
    else:
        db_path = db.db_path_str
    svc = rebuild_service or get_claims_rebuild_service()
    svc.submit(media_id=media_id, db_path=db_path)
    return {"status": "accepted", "media_id": media_id}


def rebuild_all_media(
    *,
    policy: str,
    user_id: Optional[int],
    current_user: User,
    db: MediaDatabase,
    rebuild_service: Any = None,
) -> Dict[str, Any]:
    override_db: Optional[MediaDatabase] = None
    try:
        if user_id is not None and getattr(current_user, "is_admin", False):
            db_path = get_user_media_db_path(int(user_id))
            override_db = MediaDatabase(
                db_path=db_path,
                client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
            )
            query_db = override_db
        else:
            db_path = db.db_path_str
            query_db = db

            svc = rebuild_service or get_claims_rebuild_service()

        policy = str(policy or "missing").lower()
        if policy == "all":
            sql = "SELECT id FROM Media WHERE deleted=0 AND is_trash=0"
            rows = query_db.execute_query(sql).fetchall()
        elif policy == "stale":
            sql = (
                "SELECT m.id FROM Media m "
                "LEFT JOIN (SELECT media_id, MAX(last_modified) AS lastc FROM Claims WHERE deleted=0 GROUP BY media_id) c ON c.media_id = m.id "
                "WHERE m.deleted=0 AND m.is_trash=0 AND (c.lastc IS NULL OR c.lastc < m.last_modified)"
            )
            rows = query_db.execute_query(sql).fetchall()
        else:
            sql = (
                "SELECT m.id FROM Media m "
                "WHERE m.deleted = 0 AND m.is_trash = 0 AND NOT EXISTS ("
                "  SELECT 1 FROM Claims c WHERE c.media_id = m.id AND c.deleted = 0"
                ")"
            )
            rows = query_db.execute_query(sql).fetchall()
        mids: list[int] = []
        for r in rows:
            try:
                mids.append(int(r["id"]))
            except Exception:
                try:
                    mids.append(int(r[0]))
                except Exception:
                    try:
                        if isinstance(r, dict):
                            first_val = next(iter(r.values()))
                            mids.append(int(first_val))
                    except Exception:
                        continue
        for mid in mids:
            svc.submit(media_id=mid, db_path=db_path)
        return {"status": "accepted", "enqueued": len(mids), "policy": policy}
    finally:
        if override_db is not None:
            try:
                override_db.close_connection()
            except Exception:
                pass


def rebuild_claims_fts(
    *,
    user_id: Optional[int],
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    override_db: Optional[MediaDatabase] = None
    try:
        if user_id is not None and getattr(current_user, "is_admin", False):
            db_path = get_user_media_db_path(int(user_id))
            override_db = MediaDatabase(
                db_path=db_path,
                client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
            )
            count = override_db.rebuild_claims_fts()
        else:
            count = db.rebuild_claims_fts()
    finally:
        if override_db is not None:
            try:
                override_db.close_connection()
            except Exception:
                pass
    return {"status": "ok", "indexed": count}
