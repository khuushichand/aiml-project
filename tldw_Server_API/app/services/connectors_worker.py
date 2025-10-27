from __future__ import annotations

import asyncio
import os
from typing import Optional

from loguru import logger
import hashlib
import tempfile
from pathlib import Path
from typing import Dict, Any, List
import aiohttp

try:
    from tldw_Server_API.app.core.Jobs.manager import JobManager
except Exception:  # pragma: no cover - optional
    JobManager = None  # type: ignore


DOMAIN = "connectors"


async def run_connectors_worker(stop_event: Optional[asyncio.Event] = None) -> None:
    """Minimal worker that acknowledges and completes connector jobs.

    Scaffold behavior: picks up jobs with domain 'connectors' and completes them
    immediately. Real ingestion/sync logic will be implemented later.
    """
    if JobManager is None:
        logger.warning("Jobs manager unavailable; connectors worker disabled")
        return
    jm = JobManager()
    worker_id = "connectors-worker"
    poll_sleep = float(os.getenv("CONNECTORS_POLL_INTERVAL_SECONDS", "1.0") or "1.0")
    logger.info("Starting connectors worker (scaffold import processor)")
    while True:
        if stop_event and stop_event.is_set():
            logger.info("Stopping connectors worker on shutdown signal")
            return
        try:
            job = jm.acquire_next_job(domain=DOMAIN, queue="default", lease_seconds=120, worker_id=worker_id)
            if not job:
                await asyncio.sleep(poll_sleep)
                continue
            jid = int(job["id"]) if job.get("id") is not None else None
            lease_id = str(job.get("lease_id")) if job.get("lease_id") else None
            try:
                # Process import job
                payload: Dict[str, Any] = job.get("payload") or {}
                source_id = int(payload.get("source_id")) if payload.get("source_id") is not None else None
                user_id = int(payload.get("user_id")) if payload.get("user_id") is not None else None
                if not source_id or not user_id:
                    raise ValueError("invalid job payload")
                await _process_import_job(jm, jid, lease_id, worker_id, source_id, user_id)
            except Exception as _e:
                jm.fail_job(jid, error=str(_e), retryable=False, worker_id=worker_id, lease_id=lease_id, completion_token=lease_id)
        except Exception:
            await asyncio.sleep(poll_sleep)


async def start_connectors_worker() -> Optional[asyncio.Task]:
    enabled = os.getenv("CONNECTORS_WORKER_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return None
    stop = asyncio.Event()
    task = asyncio.create_task(run_connectors_worker(stop), name="connectors-worker")
    return task


async def _process_import_job(jm, jid: int, lease_id: Optional[str], worker_id: str, source_id: int, user_id: int) -> None:
    """Fetch source/account, enumerate items, and ingest into Media DB."""
    # DB access
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    from tldw_Server_API.app.core.External_Sources.connectors_service import (
        get_account_tokens,
        get_source_by_id,
        should_ingest_item,
        record_ingested_item,
        update_account_tokens,
    )
    from tldw_Server_API.app.core.External_Sources import get_connector_by_name
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase

    pool = await get_db_pool()
    async with pool.transaction() as db:
        src = await get_source_by_id(db, user_id, source_id)
        if not src:
            raise ValueError("source not found or not owned by user")
        provider = str(src.get("provider"))
        account_id = int(src.get("account_id"))
        options = src.get("options") or {}
        remote_id = str(src.get("remote_id"))
        tokens = await get_account_tokens(db, user_id, account_id)
        acct = {"tokens": tokens, "email": src.get("email")}
        # Load org policy for this user (best-effort)
        try:
            from tldw_Server_API.app.core.AuthNZ.orgs_teams import list_memberships_for_user
            from tldw_Server_API.app.core.External_Sources.policy import get_default_policy_from_env
            from tldw_Server_API.app.core.External_Sources.connectors_service import get_policy as get_org_policy
            memberships = await list_memberships_for_user(user_id)
            org_id = int((memberships[0] or {}).get("org_id") if memberships else 1)
            policy = await get_org_policy(db, org_id)
            if not policy:
                policy = get_default_policy_from_env(org_id)
        except Exception:
            from tldw_Server_API.app.core.External_Sources.policy import get_default_policy_from_env
            policy = get_default_policy_from_env(1)

    # Prepare connector
    conn = get_connector_by_name(provider)
    # Helper to detect 401-like unauthorized errors from provider responses
    def _is_unauthorized(err: Exception) -> bool:
        try:
            if isinstance(err, aiohttp.ClientResponseError) and getattr(err, 'status', None) == 401:
                return True
        except Exception:
            pass
        # Fallback: inspect message
        msg = str(err).lower()
        return '401' in msg or 'unauthorized' in msg

    async def _attempt_with_refresh(call_coro, *args, **kwargs):
        nonlocal acct
        try:
            return await call_coro(*args, **kwargs)
        except Exception as e:
            if not _is_unauthorized(e):
                raise
            # Try refresh if possible
            rtok = (acct.get('tokens') or {}).get('refresh_token')
            if not rtok:
                raise
            try:
                new_toks = None
                if provider == 'drive' and hasattr(conn, 'refresh_access_token'):
                    new_toks = await conn.refresh_access_token(rtok)
                elif provider == 'notion' and hasattr(conn, 'refresh_access_token'):
                    new_toks = await conn.refresh_access_token(rtok)
                if not new_toks or not new_toks.get('access_token'):
                    raise e
                # Persist and update local token cache
                async with pool.transaction() as db:
                    await update_account_tokens(db, user_id, account_id, new_toks)
                acct['tokens'].update(new_toks)
                # Retry once
                return await call_coro(*args, **kwargs)
            except Exception:
                raise
    # Determine listing function
    async def _enumerate_items() -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        page_size = 100
        recursive = bool(options.get("recursive", True))
        if provider == "drive":
            # BFS traversal when recursive; otherwise single level
            queue: List[str] = [remote_id or "root"]
            visited: set[str] = set()
            while queue:
                parent = queue.pop(0)
                if parent in visited:
                    continue
                visited.add(parent)
                cursor = None
                while True:
                    batch, cursor = await _attempt_with_refresh(conn.list_files, acct, parent, page_size=page_size, cursor=cursor)
                    for f in (batch or []):
                        items.append(f)
                        if recursive and f.get("is_folder"):
                            fid2 = str(f.get("id")) if f.get("id") else None
                            if fid2:
                                queue.append(fid2)
                    if not recursive or not cursor:
                        break
        elif provider == "notion":
            typ = str(src.get("type"))
            if typ == "page":
                items = [{"id": remote_id, "name": src.get("path") or remote_id, "mimeType": "text/markdown", "last_edited_time": None, "size": None}]
            elif typ == "database":
                cursor = None
                while True:
                    batch, cursor = await _attempt_with_refresh(conn.list_sources, acct, parent_remote_id=remote_id, page_size=page_size, cursor=cursor)
                    items.extend(batch or [])
                    if not cursor:
                        break
            else:
                cursor = None
                while True:
                    batch, cursor = await _attempt_with_refresh(conn.list_sources, acct, parent_remote_id=None, page_size=page_size, cursor=cursor)
                    items.extend(batch or [])
                    if not cursor:
                        break
        return items

    items = await _enumerate_items()
    total = max(1, len(items))

    # Prepare DB instance
    media_db_path = str(DatabasePaths.get_media_db_path(user_id))
    mdb = MediaDatabase(db_path=media_db_path, client_id=str(user_id))

    processed = 0
    # Policy helpers
    from fnmatch import fnmatch
    from tldw_Server_API.app.core.External_Sources.policy import is_file_type_allowed
    allowed_export_formats = [str(f).lower() for f in (policy.get("allowed_export_formats") or [])]
    allowed_file_types = [str(t).lower() for t in (policy.get("allowed_file_types") or [])]
    max_file_size_mb = int(policy.get("max_file_size_mb") or 0)
    max_bytes = max_file_size_mb * 1024 * 1024 if max_file_size_mb > 0 else None
    include_types = [str(x).lower() for x in (options.get("include_types") or [])]
    exclude_patterns = [str(x) for x in (options.get("exclude_patterns") or [])]
    export_overrides = {str(k): str(v).lower() for k, v in (options.get("export_format_overrides") or {}).items()}
    for idx, it in enumerate(items):
        try:
            # Renew lease with progress
            pct = int((idx / total) * 100)
            jm.renew_job_lease(jid, seconds=120, worker_id=worker_id, lease_id=lease_id, progress_percent=pct)
        except Exception:
            pass
        # Skip folders
        if (it.get("is_folder") is True) or (str(it.get("mimeType") or "").startswith("application/vnd.google-apps.folder")):
            continue
        fid = str(it.get("id"))
        name = str(it.get("name") or fid)
        modified_at = it.get("modifiedTime") or it.get("last_edited_time")
        size = it.get("size")
        mime = it.get("mimeType") or ("text/markdown" if provider == "notion" else None)
        version = it.get("md5Checksum") or None

        # Enforce include/exclude on name
        try:
            if exclude_patterns and any(fnmatch(name, pat) for pat in exclude_patterns):
                continue
            if include_types:
                ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
                if ext not in include_types:
                    continue
        except Exception:
            pass

        # Enforce policy: file type and size
        if not is_file_type_allowed(name=name, mime=mime, allowed=allowed_file_types):
            continue
        if max_bytes is not None and size is not None:
            try:
                if int(size) > max_bytes:
                    continue
            except Exception:
                pass

        # Determine desired export for Drive Google types according to policy/overrides
        export_mime = None
        if provider == "drive" and (mime or "").startswith("application/vnd.google-apps."):
            override_key = mime or ""
            ov = export_overrides.get(override_key) or export_overrides.get(override_key.split(".")[-1])
            if ov in {"pdf", "txt", "md"}:
                export_mime = "application/pdf" if ov == "pdf" else "text/plain"
            else:
                if mime == "application/vnd.google-apps.presentation":
                    export_mime = "application/pdf" if "pdf" in allowed_export_formats else "text/plain"
                elif mime == "application/vnd.google-apps.document":
                    export_mime = "text/plain" if ("txt" in allowed_export_formats or "md" in allowed_export_formats) else ("application/pdf" if "pdf" in allowed_export_formats else "text/plain")
                elif mime == "application/vnd.google-apps.spreadsheet":
                    export_mime = "text/csv" if "txt" in allowed_export_formats else ("application/pdf" if "pdf" in allowed_export_formats else "text/csv")

        # Download/export
        try:
            if provider == "drive":
                raw = await _attempt_with_refresh(conn.download_file, acct, fid, mime_type=mime, export_mime=export_mime)
            else:
                raw = await _attempt_with_refresh(conn.download_file, acct, fid) if provider == "notion" else await _attempt_with_refresh(conn.download_file, acct, fid, mime_type=mime)
        except Exception as e:
            logger.warning(f"download failed for {provider}:{fid}: {e}")
            raw = b""

        # Convert to text content
        content_text = ""
        effective_mime = (export_mime or mime or "").lower()
        try:
            if effective_mime == "application/pdf" or (not effective_mime and name.lower().endswith(".pdf")):
                # PDF pipeline with docling preferred
                try:
                    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import process_pdf
                    res = process_pdf(file_input=raw, filename=name, parser="docling")
                except Exception:
                    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import process_pdf
                    res = process_pdf(file_input=raw, filename=name, parser="pymupdf4llm")
                if isinstance(res, dict):
                    content_text = (res.get("content") or "").strip()
            else:
                if raw:
                    content_text = raw.decode("utf-8", errors="replace")
        except Exception as _e:
            logger.warning(f"content conversion failed for {provider}:{fid}: {_e}")
        # Hash for dedup
        content_hash = hashlib.sha256(content_text.encode()).hexdigest() if content_text else None
        # Dedup check
        async with pool.transaction() as db:
            should = await should_ingest_item(db, source_id=source_id, provider=provider, external_id=fid, version=version, modified_at=modified_at, content_hash=content_hash)
        if not should:
            continue
        # Ingest minimal record
        title = name
        url = f"{provider}://{fid}"
        try:
            mid, m_uuid, msg = mdb.add_media_with_keywords(
                url=url,
                title=title,
                media_type="document",
                content=content_text or f"[empty content for {provider}:{fid}]",
                keywords=[],
                overwrite=False,
            )
            processed += 1
        except Exception as e:
            logger.warning(f"add_media_with_keywords failed: {e}")
        # Record ingestion cache
        async with pool.transaction() as db:
            await record_ingested_item(db, source_id=source_id, provider=provider, external_id=fid, name=name, mime=mime, size=size, version=version, modified_at=modified_at, content_hash=content_hash)
    # Complete job
    jm.complete_job(jid, result={"processed": processed, "total": total}, worker_id=worker_id, lease_id=lease_id, completion_token=lease_id)
