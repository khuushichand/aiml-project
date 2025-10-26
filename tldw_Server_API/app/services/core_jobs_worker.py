from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Chatbooks.chatbook_service import ChatbookService
from tldw_Server_API.app.core.Chatbooks.chatbook_models import ExportStatus, ImportStatus, ContentType, ConflictResolution
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.Metrics import get_metrics_registry


def _build_chacha_db_for_user(user_id: str) -> CharactersRAGDB:
    # Use the same logic as the dependency util to locate per-user DB
    try:
        uid_int = int(str(user_id))
    except (TypeError, ValueError) as e:
        logger.debug(f"Core Jobs Worker: non-int user_id {user_id}, fallback to 1: {e}")
        try:
            get_metrics_registry().increment(
                "app_warning_events_total",
                labels={"component": "core_jobs_worker", "event": "non_int_user_id"},
            )
        except Exception:
            logger.debug("metrics increment failed for non_int_user_id")
        uid_int = 1  # fallback for non-int ids
    try:
        from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import _get_chacha_db_path_for_user  # type: ignore
        db_path = _get_chacha_db_path_for_user(uid_int)
        return CharactersRAGDB(db_path=str(db_path), client_id=str(user_id))
    except Exception as e:
        logger.warning(f"Core Jobs Worker: fallback path for user {user_id} due to: {e}")
        # Fallback path inside project-root Databases/user_databases
        try:
            from tldw_Server_API.app.core.Utils.Utils import get_project_root
            base = Path(get_project_root()) / "Databases" / "user_databases" / str(user_id)
        except Exception:
            # Last resort: anchor to this file's package root to avoid CWD effects
            base = Path(__file__).resolve().parents[3] / "Databases" / "user_databases" / str(user_id)
        base.mkdir(parents=True, exist_ok=True)
        return CharactersRAGDB(db_path=str(base / "ChaChaNotes.db"), client_id=str(user_id))


async def run_chatbooks_core_jobs_worker(stop_event: Optional[asyncio.Event] = None) -> None:
    """Shared background worker for Chatbooks when using core Jobs backend.

    Processes jobs for all users by acquiring next job from the global Jobs table.
    """
    logger.info("Starting Core Jobs worker for Chatbooks domain")
    jm = JobManager()
    worker_id = f"cb-core-worker"
    poll_sleep = float(os.getenv("JOBS_POLL_INTERVAL_SECONDS", "1.0") or "1.0")
    import random
    while True:
        if stop_event and stop_event.is_set():
            logger.info("Stopping Core Jobs worker on shutdown signal")
            return
        try:
            lease_seconds = int(os.getenv("JOBS_LEASE_SECONDS", "60") or "60")
            renew_interval = int(os.getenv("JOBS_LEASE_RENEW_SECONDS", "30") or "30")
            renew_jitter = int(os.getenv("JOBS_LEASE_RENEW_JITTER_SECONDS", "5") or "5")
            job = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=lease_seconds, worker_id=worker_id)
            if not job:
                await asyncio.sleep(poll_sleep)
                continue

            owner = job.get("owner_user_id") or (job.get("payload") or {}).get("user_id")
            if not owner:
                jm.fail_job(int(job["id"]), error="missing owner_user_id", retryable=False, worker_id=worker_id, lease_id=str(job.get("lease_id")))
                continue
            # Build a per-user service
            db = _build_chacha_db_for_user(str(owner))
            owner_int: Optional[int] = None
            try:
                owner_int = int(owner)
            except (TypeError, ValueError):
                owner_int = None
            svc = ChatbookService(owner, db, user_id_int=owner_int)

            payload: Dict = job.get("payload") or {}
            action = payload.get("action")
            chatbooks_job_id = payload.get("chatbooks_job_id")
            lease_id = job.get("lease_id")
            async def _start_renewal(job_id: int):
                async def _loop():
                    while True:
                        try:
                            if stop_event and stop_event.is_set():
                                return
                            jm.renew_job_lease(int(job_id), seconds=lease_seconds, worker_id=worker_id, lease_id=str(lease_id))
                        except Exception as e:
                            logger.debug(f"Core Jobs Worker: lease renew failed for job {job_id}: {e}")
                            try:
                                get_metrics_registry().increment(
                                    "app_warning_events_total",
                                    labels={"component": "core_jobs_worker", "event": "lease_renew_failed"},
                                )
                            except Exception:
                                logger.debug("metrics increment failed for lease_renew_failed")
                        # Apply jitter to renewal interval to avoid thundering herd
                        slp = renew_interval + random.uniform(-float(renew_jitter), float(renew_jitter))
                        await asyncio.sleep(max(1.0, slp))
                return asyncio.create_task(_loop())

            if action == "export":
                try:
                    ej = svc._get_export_job(chatbooks_job_id)
                except Exception as e:
                    logger.debug(f"Core Jobs Worker: get export job failed {chatbooks_job_id}: {e}")
                    try:
                        get_metrics_registry().increment(
                            "app_warning_events_total",
                            labels={"component": "core_jobs_worker", "event": "get_export_job_failed"},
                        )
                    except Exception:
                        logger.debug("metrics increment failed for get_export_job_failed")
                    ej = None
                if ej:
                    ej.status = ExportStatus.IN_PROGRESS
                    ej.started_at = datetime.utcnow()
                    svc._save_export_job(ej)
                # Pre-flight cancel check
                cur = jm.get_job(int(job["id"])) or {}
                if cur.get("cancel_requested_at"):
                    if ej:
                        ej.status = ExportStatus.CANCELLED
                        ej.completed_at = datetime.utcnow()
                        svc._save_export_job(ej)
                    jm.finalize_cancelled(int(job["id"]), reason="cancel requested before start")
                    continue
                # Build selections
                cs = {}
                for k, v in (payload.get("content_selections") or {}).items():
                    try:
                        cs[ContentType(k)] = v
                    except Exception:
                        pass
                # Start periodic lease renewal during heavy processing
                _renew_task = await _start_renewal(int(job["id"]))
                ok, msg, file_path = await svc._create_chatbook_sync_wrapper(
                    name=payload.get("name"),
                    description=payload.get("description"),
                    content_selections=cs,
                    author=payload.get("author"),
                    include_media=bool(payload.get("include_media")),
                    media_quality=str(payload.get("media_quality", "compressed")),
                    include_embeddings=bool(payload.get("include_embeddings")),
                    include_generated_content=bool(payload.get("include_generated_content", True)),
                    tags=payload.get("tags") or [],
                    categories=payload.get("categories") or [],
                )
                if ok:
                    # Mid-flight cancel check (honor cancellation request or terminal state)
                    cur = jm.get_job(int(job["id"])) or {}
                    if cur.get("cancel_requested_at") or (cur.get("status") and str(cur.get("status")).lower() != "processing"):
                        if ej:
                            ej.status = ExportStatus.CANCELLED
                            ej.completed_at = datetime.utcnow()
                            svc._save_export_job(ej)
                        jm.finalize_cancelled(int(job["id"]), reason="cancel requested during processing")
                        continue
                    try:
                        ej = svc._get_export_job(chatbooks_job_id)
                    except Exception:
                        ej = None
                    if ej and ej.status != ExportStatus.CANCELLED:
                        ej.status = ExportStatus.COMPLETED
                        ej.completed_at = datetime.utcnow()
                        ej.output_path = file_path
                        try:
                            ej.file_size_bytes = Path(file_path).stat().st_size if file_path else None
                        except Exception as e:
                            logger.debug(f"Core Jobs Worker: stat exported file failed: {e}")
                            try:
                                get_metrics_registry().increment(
                                    "app_warning_events_total",
                                    labels={"component": "core_jobs_worker", "event": "export_stat_failed"},
                                )
                            except Exception:
                                logger.debug("metrics increment failed for export_stat_failed")
                        ttl_seconds = int(os.getenv("CHATBOOKS_URL_TTL_SECONDS", "86400") or "86400")
                        ej.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
                        ej.download_url = svc._build_download_url(ej.job_id, ej.expires_at)
                        svc._save_export_job(ej)
                    jm.complete_job(int(job["id"]), result={"path": file_path}, worker_id=worker_id, lease_id=str(lease_id), completion_token=str(lease_id))
                else:
                    try:
                        ej = svc._get_export_job(chatbooks_job_id)
                    except Exception as e:
                        logger.debug(f"Core Jobs Worker: get export job (post-fail) failed {chatbooks_job_id}: {e}")
                        ej = None
                    if ej:
                        ej.status = ExportStatus.FAILED
                        ej.completed_at = datetime.utcnow()
                        ej.error_message = msg
                        svc._save_export_job(ej)
                    jm.fail_job(int(job["id"]), error=str(msg), retryable=False, worker_id=worker_id, lease_id=str(lease_id), completion_token=str(lease_id))
                # Stop renewal
                try:
                    _renew_task.cancel()
                except Exception as e:
                    logger.debug(f"Core Jobs Worker: failed to cancel renew task: {e}")
                    try:
                        get_metrics_registry().increment(
                            "app_warning_events_total",
                            labels={"component": "core_jobs_worker", "event": "renew_task_cancel_failed"},
                        )
                    except Exception:
                        logger.debug("metrics increment failed for renew_task_cancel_failed")
            elif action == "import":
                ij = svc._get_import_job(chatbooks_job_id)
                if ij:
                    ij.status = ImportStatus.IN_PROGRESS
                    ij.started_at = datetime.utcnow()
                    svc._save_import_job(ij)
                # Pre-flight cancel check
                cur = jm.get_job(int(job["id"])) or {}
                if cur.get("cancel_requested_at"):
                    if ij:
                        ij.status = ImportStatus.CANCELLED
                        ij.completed_at = datetime.utcnow()
                        svc._save_import_job(ij)
                    jm.finalize_cancelled(int(job["id"]), reason="cancel requested before start")
                    continue
                cs = {}
                for k, v in (payload.get("content_selections") or {}).items():
                    try:
                        cs[ContentType(k)] = v
                    except Exception as e:
                        logger.debug(f"Core Jobs Worker: invalid content type {k}: {e}")
                        try:
                            get_metrics_registry().increment(
                                "app_warning_events_total",
                                labels={"component": "core_jobs_worker", "event": "invalid_content_type"},
                            )
                        except Exception:
                            logger.debug("metrics increment failed for invalid_content_type")
                conf_val = payload.get("conflict_resolution", "skip")
                try:
                    conf = ConflictResolution(conf_val)
                except Exception as e:
                    logger.debug(f"Core Jobs Worker: invalid conflict_resolution {conf_val}: {e}; defaulting to SKIP")
                    conf = ConflictResolution.SKIP
                _renew_task = await _start_renewal(int(job["id"]))
                ok, msg, _ = await asyncio.to_thread(
                    svc._import_chatbook_sync,
                    payload.get("file_path"), cs,
                    conf,
                    bool(payload.get("prefix_imported", False)),
                    bool(payload.get("import_media", True)),
                    bool(payload.get("import_embeddings", False)),
                )
                ij = svc._get_import_job(chatbooks_job_id)
                if ok:
                    # Mid-flight cancel check (honor cancellation request or terminal state)
                    cur = jm.get_job(int(job["id"])) or {}
                    if cur.get("cancel_requested_at") or (cur.get("status") and str(cur.get("status")).lower() != "processing"):
                        if ij:
                            ij.status = ImportStatus.CANCELLED
                            ij.completed_at = datetime.utcnow()
                            svc._save_import_job(ij)
                        jm.finalize_cancelled(int(job["id"]), reason="cancel requested during processing")
                        continue
                    if ij and ij.status != ImportStatus.CANCELLED:
                        ij.status = ImportStatus.COMPLETED
                        ij.completed_at = datetime.utcnow()
                        svc._save_import_job(ij)
                    jm.complete_job(int(job["id"]), worker_id=worker_id, lease_id=str(lease_id), completion_token=str(lease_id))
                else:
                    if ij:
                        ij.status = ImportStatus.FAILED
                        ij.completed_at = datetime.utcnow()
                        ij.error_message = msg
                        svc._save_import_job(ij)
                    jm.fail_job(int(job["id"]), error=str(msg), retryable=False, worker_id=worker_id, lease_id=str(lease_id), completion_token=str(lease_id))
                try:
                    _renew_task.cancel()
                except Exception as e:
                    logger.debug(f"Core Jobs Worker: failed to cancel renew task (import): {e}")
                    try:
                        get_metrics_registry().increment(
                            "app_warning_events_total",
                            labels={"component": "core_jobs_worker", "event": "renew_task_cancel_failed"},
                        )
                    except Exception:
                        logger.debug("metrics increment failed for renew_task_cancel_failed")
            else:
                jm.fail_job(int(job["id"]), error="unknown action", retryable=False, worker_id=worker_id, lease_id=str(lease_id), completion_token=str(lease_id))
        except Exception as e:
            logger.error(f"Core Jobs worker loop error: {e}")
            try:
                get_metrics_registry().increment(
                    "app_exception_events_total",
                    labels={"component": "core_jobs_worker", "event": "worker_loop_error"},
                )
            except Exception:
                logger.debug("metrics increment failed for worker_loop_error")
            await asyncio.sleep(poll_sleep)
